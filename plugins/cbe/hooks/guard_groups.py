#!/usr/bin/env python3
"""PreToolUse hook: ask before commands and file edits that delete, move, or
overwrite data under protected storage (by default /groups) on CBE.next.

Reads the hook event as JSON on stdin. When a Bash command, or a Write, Edit,
or NotebookEdit call, would touch a protected path, it prints a PreToolUse
decision of "ask" with the affected paths and what they contain, so the user
confirms exactly those paths. Anything else exits 0 with no output.

Commands sent to another host with `ssh <host> <command>` are checked too, so
the hook also protects the cluster when the agent runs on a laptop. Remote
paths can't be inspected, so any remote command that would delete, move, or
overwrite a protected path asks.

The parse is deliberately conservative: when a target can't be resolved
(unset variables, command substitution, inline interpreter code) and the
command runs in or names a protected path, it asks.

Environment:
  CBE_PROTECTED_PATHS  colon-separated roots to protect (default: /groups)
  CBE_GROUPS_GUARD     set to "off" to disable the hook
"""

import datetime
import glob
import json
import os
import re
import shlex
import sys
import time

DEFAULT_ROOTS = "/groups"

# Commands whose path arguments are deleted, moved, or overwritten.
REMOVE_CMDS = {"rm", "rmdir", "unlink", "shred"}
MOVE_CMDS = {"mv"}
OVERWRITE_LAST_CMDS = {"cp"}       # destination overwritten if it exists
OVERWRITE_ALL_CMDS = {"truncate", "tee"}
# Prefixes that run another command from their arguments.
WRAPPERS = {
    "sudo", "env", "nice", "nohup", "time", "command", "builtin", "exec",
    "timeout", "srun", "stdbuf", "ionice", "xargs", "parallel", "chronic",
}
STDIN_WRAPPERS = {"xargs", "parallel"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
INTERPRETERS = {"python", "python3", "perl", "Rscript", "ruby", "node"}
KEYWORDS = {"do", "then", "else", "elif", "{", "(", "!", "if", "while", "until"}
SEPARATOR_CHARS = set(";&|()\n")
REDIRECTS = {">", ">|", "&>"}
# ssh options that take a value (ssh(1)).
SSH_VALUE_OPTS = set("BbcDEeFIiJLlmOoPpQRSWw")
# git subcommands that discard files or uncommitted changes.
GIT_DISCARD = re.compile(
    r"^(clean\b.*-\w*f|reset\b.*--hard|checkout\b.*(\s--(\s|$)|\s-f\b|\s\.(\s|$))|"
    r"restore\b|switch\b.*(--discard-changes|\s-f\b)|stash\s+(drop|clear)\b)"
)

RAW_DESTRUCTIVE = re.compile(
    r"\b(rm|rmdir|unlink|shred|truncate|mv)\b|-delete\b|--delete|"
    r"rclone\s+(sync|move|moveto|delete|deletefile|purge|rmdirs?)\b|"
    r"rmtree|os\.(remove|unlink|rename|replace)|file\.remove|unlink\(|"
    r"--delete-destination|\bsed\s+(-\w*i|--in-place)|\bperl\s+-\w*i"
)

# Limits for describing what a path contains, so the hook stays fast.
SCAN_MAX_ENTRIES = 20000
SCAN_MAX_SECONDS = 2.0
COLLISION_MAX_ENTRIES = 5000


class Ctx:
    def __init__(self, cwd, roots, env, remote=None):
        self.cwd = cwd
        self.roots = roots
        self.env = dict(env)
        self.remote = remote    # host name for commands run through ssh
        self.hits = []          # (action, path, remote host or None)
        self.unsure = []        # reasons we couldn't resolve a target
        self.runtime = set()    # variables assigned at run time, e.g. d=$(mktemp -d)
        self.text = ""          # the whole command, heredoc data removed

    def for_host(self, host):
        # The remote shell starts in the user's home with an unknown environment.
        sub = Ctx("~", self.roots, {}, remote=host)
        sub.hits = self.hits
        sub.unsure = self.unsure
        sub.text = self.text
        return sub


def under(path, root):
    path = path.rstrip("/") or "/"
    root = root.rstrip("/") or "/"
    return path == root or path.startswith(root + "/") or root.startswith(path + "/") or path == "/"


def inside(path, root):
    """path is root or below it (not an ancestor of it)."""
    path = path.rstrip("/") or "/"
    root = root.rstrip("/") or "/"
    return path == root or path.startswith(root + "/")


def protected(path, ctx):
    candidates = {os.path.normpath(path)}
    if not ctx.remote:
        try:
            candidates.add(os.path.realpath(path))
        except OSError:
            pass
    return any(under(c, r) for c in candidates for r in ctx.roots)


def expand(arg, ctx):
    """Return (paths, unresolved) for one shell word."""
    unresolved = False
    lead = re.match(r"\$\{?(\w+)", arg)
    if lead and lead.group(1) in ctx.runtime:
        # Starts with a value computed at run time (d=$(mktemp -d); rm -rf "$d"): the
        # path is unknown, not "/". Ask only if the command names a protected root.
        named = [r for r in ctx.roots if r in ctx.text]
        return named, True

    def sub(m):
        nonlocal unresolved
        name = m.group(1) or m.group(2)
        if name in ctx.env and name not in ctx.runtime:
            return ctx.env[name]
        unresolved = True
        return ""

    s = re.sub(r"\$\{(\w+)[^}]*\}|\$(\w+)", sub, arg)
    if "$(" in s or "`" in s:
        unresolved = True
        s = re.sub(r"\$\(.*?\)|`.*?`", "", s)
    if ctx.remote:
        # Remote paths can't be expanded or checked; the shell starts in the remote home.
        if s.startswith("~"):
            return [s], unresolved
        if not s.startswith("/"):
            if not ctx.cwd.startswith("/"):
                return [os.path.join(ctx.cwd, s)], unresolved
            s = os.path.join(ctx.cwd, s)
        return [os.path.normpath(s)], unresolved
    s = os.path.expanduser(s)
    if not os.path.isabs(s):
        s = os.path.join(ctx.cwd, s)
    s = os.path.normpath(s)
    if any(c in s for c in "*?["):
        matches = glob.glob(s)
        return (matches or [s]), unresolved
    return [s], unresolved


def hit(ctx, action, path):
    ctx.hits.append((action, path, ctx.remote))


def check(action, args, ctx, must_exist=True):
    for a in args:
        paths, unresolved = expand(a, ctx)
        for p in paths:
            if not protected(p, ctx):
                continue
            if unresolved:
                hit(ctx, action, p + "  (contains unset variable or substitution: %s)" % a)
            elif ctx.remote or not must_exist or os.path.lexists(p):
                hit(ctx, action, p)


def positional(args, value_opts=()):
    out, skip, end = [], False, False
    for a in args:
        if skip:
            skip = False
            continue
        if not end and a == "--":
            end = True
            continue
        if not end and a.startswith("-") and a != "-":
            if a in value_opts:
                skip = True
            continue
        out.append(a)
    return out


def is_remote(a):
    return bool(re.match(r"^[\w.@-]+:", a)) and not a.startswith("/")


def remote_path(a):
    """Split 'host:path' into (host, path)."""
    host, _, path = a.partition(":")
    return host.split("@")[-1], path


def split_segments(tokens):
    seg = []
    for t in tokens:
        if t and set(t) <= SEPARATOR_CHARS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def analyse(command, ctx, whole):
    try:
        # Newlines separate commands, so make them punctuation, not whitespace.
        lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>\n")
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        ctx.unsure.append("could not parse command")
        return
    for seg in split_segments(tokens):
        segment(seg, ctx, whole)


def collisions(sources, dest, ctx, contents=False):
    """Files under the existing local directory dest that copying sources would overwrite."""
    found, seen = [], 0
    for src in sources:
        paths, _ = expand(src, ctx)
        for s in paths:
            if not os.path.exists(s):
                continue
            into = dest if contents and os.path.isdir(s) else os.path.join(dest, os.path.basename(s.rstrip("/")))
            if os.path.isfile(s):
                if os.path.isfile(into):
                    found.append(into)
                continue
            for root, _, files in os.walk(s):
                for f in files:
                    seen += 1
                    if seen > COLLISION_MAX_ENTRIES:
                        return found
                    target = os.path.join(into, os.path.relpath(os.path.join(root, f), s))
                    if os.path.isfile(target):
                        found.append(target)
    return found


def overwrite_into(action, sources, dest_arg, ctx, contents=False):
    """Ask when copying sources into dest would replace existing files."""
    dest = expand(dest_arg, ctx)[0][0]
    if not protected(dest, ctx):
        return
    if ctx.remote:
        return  # existence of remote files is unknown; plain copies don't delete
    if os.path.isdir(dest):
        clash = collisions(sources, dest, ctx, contents)
        if clash:
            extra = "" if len(clash) == 1 else "  (and %d more files)" % (len(clash) - 1)
            hit(ctx, action, clash[0] + extra)
    elif os.path.isfile(dest):
        hit(ctx, action, dest)


def nonempty_dir(path):
    try:
        return os.path.isdir(path) and any(True for _ in os.scandir(path))
    except OSError:
        return False


def extract_into(action, dest_arg, ctx):
    """Extracting an archive into a protected directory can replace existing files."""
    dest = expand(dest_arg, ctx)[0][0]
    if protected(dest, ctx) and (ctx.remote or nonempty_dir(dest)):
        hit(ctx, action, dest)


def segment(seg, ctx, whole):
    # Redirections: '>' onto an existing file overwrites it.
    words, i = [], 0
    while i < len(seg):
        t = seg[i]
        if t.isdigit() and i + 1 < len(seg) and seg[i + 1] in REDIRECTS | {">>", ">&", "<", "<&"}:
            i += 1
            continue
        if t in REDIRECTS and i + 1 < len(seg):
            check("overwrite (redirect)", [seg[i + 1]], ctx)
            i += 2
            continue
        if t in {">>", "<", "<<", "<<<", ">&", "<&"}:
            i += 2
            continue
        words.append(t)
        i += 1

    while words and words[0] in KEYWORDS:
        words = words[1:]
    # Plain variable assignments: remember them for later segments.
    while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
        name, _, value = words[0].partition("=")
        if len(words) == 1:
            # "d=$(cmd)" reaches us as "d=$" because "(" separates tokens.
            if value.endswith("$") or "$(" in value or "`" in value or any(
                    v in ctx.runtime for v in re.findall(r"\$\{?(\w+)", value)):
                ctx.runtime.add(name)
                ctx.env.pop(name, None)
            else:
                ctx.runtime.discard(name)
                ctx.env[name] = re.sub(r"\$\{?(\w+)\}?", lambda m: ctx.env.get(m.group(1), ""), value)
        words = words[1:]
    if not words:
        return

    cmd = os.path.basename(words[0])
    args = words[1:]

    if cmd == "cd":
        target = args[0] if args else "~"
        paths, _ = expand(target, ctx)
        # No path: a directory computed at run time (cd "$(mktemp -d)") that names no protected root.
        ctx.cwd = paths[0] if paths else "(directory computed at run time)"
        return

    if cmd == "ssh":
        host, j = None, 0
        while j < len(args):
            a = args[j]
            if a.startswith("-") and len(a) > 1:
                if a[-1] in SSH_VALUE_OPTS and len(a) == 2:
                    j += 1
                j += 1
                continue
            host = a
            break
        rest = args[j + 1:]
        if host and rest:
            remote_cmd = " ".join(rest)
            analyse(remote_cmd, ctx.for_host(host.split("@")[-1]), remote_cmd)
        return

    if cmd in WRAPPERS:
        for j, a in enumerate(args):
            if os.path.basename(a) in (REMOVE_CMDS | MOVE_CMDS | OVERWRITE_LAST_CMDS
                                       | OVERWRITE_ALL_CMDS | SHELLS | INTERPRETERS
                                       | {"find", "rsync", "rclone", "azcopy", "dd", "ssh",
                                          "sed", "tar", "unzip", "git"}):
                if cmd in STDIN_WRAPPERS and os.path.basename(a) in REMOVE_CMDS | MOVE_CMDS:
                    stdin_targets(os.path.basename(a), ctx, whole)
                segment(args[j:], ctx, whole)
                return
        return

    if cmd in SHELLS and "-c" in args:
        idx = args.index("-c")
        if idx + 1 < len(args):
            analyse(args[idx + 1], ctx, whole)
        return
    if cmd in SHELLS:
        # bash -lc '...' and similar combined flags.
        for j, a in enumerate(args):
            if re.match(r"^-\w*c$", a) and j + 1 < len(args):
                analyse(args[j + 1], ctx, whole)
                return
        return
    if cmd == "eval":
        analyse(" ".join(args), ctx, whole)
        return
    if cmd == "sbatch":
        for j, a in enumerate(args):
            if a.startswith("--wrap="):
                analyse(a[len("--wrap="):], ctx, whole)
            elif a == "--wrap" and j + 1 < len(args):
                analyse(args[j + 1], ctx, whole)
        return
    if cmd == "perl" and any(re.match(r"^-\w*i", a) for a in args):
        files, skip, script = [], False, any(re.match(r"^-\w*[eE]$", a) for a in args)
        for a in args:
            if skip:
                skip = False
                continue
            if re.match(r"^-\w*[eEMI]$", a):
                skip = True
                continue
            if not a.startswith("-"):
                files.append(a)
        check("edit in place (perl -i)", files if script else files[1:], ctx)
        return
    if cmd in INTERPRETERS or re.match(r"^python3(\.\d+)?$", cmd):
        if any(a in ("-c", "-e") for a in args) and RAW_DESTRUCTIVE.search(" ".join(args)):
            context_targets("inline code may delete or move files", ctx, whole)
        return

    if cmd in REMOVE_CMDS:
        check("delete", positional(args), ctx)
    elif cmd in MOVE_CMDS:
        check("move/overwrite", positional(args, {"-t", "-S"}), ctx)
    elif cmd in OVERWRITE_LAST_CMDS:
        pos = positional(args, {"-t", "-S"})
        no_clobber = any(a in ("-n", "--no-clobber", "--update=none") for a in args)
        if len(pos) >= 2 and not no_clobber:
            overwrite_into("overwrite (cp)", pos[:-1], pos[-1], ctx)
    elif cmd == "truncate":
        check("truncate", positional(args, {"-s", "-r"}), ctx)
    elif cmd == "tee":
        if not any(a in ("-a", "--append") for a in args):
            check("overwrite (tee)", positional(args), ctx)
    elif cmd == "dd":
        check("overwrite (dd)", [a[3:] for a in args if a.startswith("of=")], ctx)
    elif cmd == "sed":
        if any(re.match(r"^-\w*i", a) or a.startswith("--in-place") for a in args):
            files, skip, script = [], False, False
            for a in args:
                if skip:
                    skip = False
                    continue
                if a in ("-e", "-f", "--expression", "--file"):
                    script, skip = True, True
                    continue
                if a.startswith(("--expression=", "--file=")):
                    script = True
                    continue
                if not a.startswith("-"):
                    files.append(a)
            check("edit in place (sed -i)", files if script else files[1:], ctx)
    elif cmd == "tar":
        first = args[0] if args else ""
        extracting = ("--extract" in args or "--get" in args or
                      any(re.match(r"^-\w*x", a) for a in args) or
                      (first and not first.startswith("-") and "x" in first))
        keep = any(a in ("--keep-old-files", "--skip-old-files") or re.match(r"^-[a-zA-Z]*k[a-zA-Z]*$", a)
                   for a in args) or (first and not first.startswith("-") and "k" in first)
        if extracting and not keep:
            dest = ctx.cwd
            for j, a in enumerate(args):
                if a in ("-C", "--directory") and j + 1 < len(args):
                    dest = args[j + 1]
                elif a.startswith("--directory="):
                    dest = a.split("=", 1)[1]
            extract_into("extract over existing files (tar -x)", dest, ctx)
    elif cmd == "unzip":
        if "-o" in args:
            dest = args[args.index("-d") + 1] if "-d" in args[:-1] else ctx.cwd
            extract_into("extract over existing files (unzip -o)", dest, ctx)
    elif cmd == "git":
        repo, j = ctx.cwd, 0
        while j < len(args) and args[j].startswith("-"):
            if args[j] == "-C" and j + 1 < len(args):
                repo = args[j + 1]
                j += 1
            j += 1
        rest = " ".join(args[j:])
        if GIT_DISCARD.match(rest):
            path = expand(repo, ctx)[0][0]
            if protected(path, ctx):
                hit(ctx, "discard files or changes (git %s)" % args[j], path)
    elif cmd == "find":
        destructive = "-delete" in args or any(
            a in ("-exec", "-execdir", "-ok", "-okdir") and j + 1 < len(args)
            and os.path.basename(args[j + 1]) in REMOVE_CMDS | MOVE_CMDS
            for j, a in enumerate(args))
        if destructive:
            starts = []
            for a in args:
                if a.startswith("-") or a in ("(", "!"):
                    break
                starts.append(a)
            check("delete (find)", starts or ["."], ctx)
    elif cmd == "rsync":
        pos_all = positional(args, {"-e", "--rsh"})
        local = [a for a in pos_all if not is_remote(a)]
        delete = any(a.startswith("--delete") for a in args)
        if pos_all and is_remote(pos_all[-1]):
            host, path = remote_path(pos_all[-1])
            if delete:
                check("delete (rsync --delete destination)", [path], ctx.for_host(host))
        elif delete and local:
            check("delete (rsync --delete destination)", local[-1:], ctx, must_exist=False)
        elif len(pos_all) >= 2 and not any(
                a in ("--ignore-existing", "-b", "--backup") or a.startswith("--backup-dir")
                for a in args):
            sources = [a for a in pos_all[:-1] if not is_remote(a)]
            contents = all(a.endswith("/") for a in sources)
            overwrite_into("overwrite (rsync)", sources, pos_all[-1], ctx, contents=contents)
        if "--remove-source-files" in args:
            for a in pos_all[:-1]:
                if is_remote(a):
                    host, path = remote_path(a)
                    check("delete (rsync --remove-source-files)", [path], ctx.for_host(host))
                else:
                    check("delete (rsync --remove-source-files)", [a], ctx)
    elif cmd == "rclone":
        pos = positional(args)
        if pos and pos[0] in ("sync", "move", "moveto", "bisync") and len(pos) >= 3:
            local = [a for a in pos[1:] if not is_remote(a)]
            check("delete/move (rclone %s)" % pos[0], local, ctx, must_exist=False)
        elif pos and pos[0] in ("delete", "deletefile", "purge", "rmdir", "rmdirs"):
            check("delete (rclone %s)" % pos[0], [a for a in pos[1:] if not is_remote(a)], ctx)
    elif cmd == "azcopy":
        pos = positional(args)
        if pos and pos[0] == "sync" and any("--delete-destination" in a and not a.endswith("=false") for a in args):
            local = [a for a in pos[1:] if not a.startswith("http")]
            check("delete (azcopy sync --delete-destination)", local[-1:], ctx, must_exist=False)
        elif pos and pos[0] in ("remove", "rm"):
            check("delete (azcopy remove)", [a for a in pos[1:] if not a.startswith("http")], ctx)


def stdin_targets(cmd, ctx, whole):
    context_targets("%s reads its targets from a pipe" % cmd, ctx, whole)


def context_targets(reason, ctx, whole):
    """Targets we can't see: ask if the command names or runs in a protected path."""
    named = {}
    for t in re.findall(r"[~\w./${}:\"'-]+", whole):
        t = t.replace('"', "").replace("'", "")  # "$d"/ is one word
        if "/" not in t or "://" in t or t.startswith("//") or is_remote(t):
            continue  # URLs, comments, and host:path aren't local paths
        paths, unresolved = expand(t, ctx)
        for p in paths:
            if not protected(p, ctx):
                continue
            # A path that only became an ancestor of a root, such as "/", because a
            # variable was dropped ("$d/") says nothing about where the command writes.
            if ("$" in t or "`" in t or unresolved) and not any(inside(p, r) for r in ctx.roots):
                continue
            named.setdefault(p, t)
    if named or protected(ctx.cwd, ctx):
        where = sorted(named.items()) or [(ctx.cwd, None)]
        for p, t in where:
            label = "  (working directory)" if t is None else ("" if t == p else "  (written as %s)" % t)
            # A path named in a command that also uses ssh may be on either host.
            maybe_remote = t is not None and not ctx.remote and re.search(r"(^|[\s;&|(])ssh\s", whole)
            ctx.hits.append(("possible delete/move: " + reason, p + label, "?" if maybe_remote else ctx.remote))


HEREDOC = re.compile(r"(?<!<)<<(-?)[ \t]*(['\"]?)([A-Za-z_][\w.-]*)\2")


def split_heredocs(command):
    """Remove heredoc bodies, which shlex can't parse and which are data for
    most commands. Returns the command without them and a list of
    (command line, body) for heredocs fed to a shell or ssh, which run the
    body as commands. A heredoc without its end marker is left in place."""
    lines = command.split("\n")
    out, fed, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in HEREDOC.finditer(line):
            strip_tabs, word = m.group(1) == "-", m.group(3)
            end = next((j for j in range(i, len(lines))
                        if (lines[j].lstrip("\t") if strip_tabs else lines[j]) == word), None)
            if end is None:
                return command, []
            body = "\n".join(lines[i:end])
            first = re.split(r"[\s;&|()]+", line[:m.start()].strip())
            if any(os.path.basename(w) in SHELLS | {"ssh"} for w in first if w):
                fed.append((line[:m.start()], body))
            i = end + 1
    return "\n".join(out), fed


def analyse_fed(fed, ctx):
    """Analyse heredoc bodies that a shell or ssh runs as commands."""
    for line, body in fed:
        words = line.split()
        host = None
        if "ssh" in [os.path.basename(w) for w in words]:
            rest = words[[os.path.basename(w) for w in words].index("ssh") + 1:]
            j = 0
            while j < len(rest) and rest[j].startswith("-"):
                j += 2 if rest[j][-1] in SSH_VALUE_OPTS and len(rest[j]) == 2 else 1
            host = rest[j].split("@")[-1] if j < len(rest) else "ssh host"
        analyse(body, ctx.for_host(host) if host else ctx, body)


def latest_snapshot(root):
    """Name and time of the newest snapshot in <root>/.snapshot, if readable."""
    best = None
    try:
        names = os.listdir(os.path.join(root, ".snapshot"))
    except OSError:
        return None
    for name in names:
        m = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{4})", name)
        if not m:
            continue
        try:
            t = datetime.datetime.strptime(m.group(1) + m.group(2), "%Y-%m-%d%H%M").timestamp()
        except ValueError:
            continue
        if best is None or t > best[1]:
            best = (name, t)
    return best


def describe(path, roots, deadline):
    """Short summary of a local path: size, files, owner, newest change."""
    try:
        st = os.lstat(path)
    except OSError:
        return None
    try:
        import pwd
        owner = pwd.getpwuid(st.st_uid).pw_name
    except (ImportError, KeyError):
        owner = str(st.st_uid)
    files, size, newest, partial = 0, 0, st.st_mtime, False
    if os.path.isdir(path) and not os.path.islink(path):
        for root, dirs, names in os.walk(path):
            for n in names + dirs:
                try:
                    s = os.lstat(os.path.join(root, n))
                except OSError:
                    continue
                if n in names:
                    files += 1
                    size += s.st_size
                newest = max(newest, s.st_mtime)
            if files > SCAN_MAX_ENTRIES or time.monotonic() > deadline:
                partial = True
                break
    else:
        files, size = 1, st.st_size
    parts = ["%s%d file%s" % ("at least " if partial else "", files, "" if files == 1 else "s"),
             human(size) + ("+" if partial else ""), "owner " + owner,
             "newest change " + datetime.datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M")]
    text = ", ".join(parts)
    root = next((r for r in roots if under(path, r) and path != r), None)
    snap = latest_snapshot(root) if root else None
    if snap and newest > snap[1]:
        text += "; changed after the latest snapshot %s, so those changes can't be restored" % snap[0]
    return text


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%d %s" if unit == "B" else "%.1f %s") % (n, unit)
        n /= 1024.0


def file_tool_hits(event, ctx):
    """Write, Edit, and NotebookEdit change an existing file in place."""
    tool = event.get("tool_name")
    inp = event.get("tool_input") or {}
    path = inp.get("notebook_path") if tool == "NotebookEdit" else inp.get("file_path")
    if not path:
        return
    path = os.path.normpath(os.path.join(ctx.cwd, os.path.expanduser(path)))
    if protected(path, ctx) and os.path.lexists(path):
        hit(ctx, "overwrite (%s tool)" % tool, path)


def decide(event):
    if os.environ.get("CBE_GROUPS_GUARD", "").lower() == "off":
        return None
    tool = event.get("tool_name")
    if tool not in ("Bash", "Write", "Edit", "MultiEdit", "NotebookEdit"):
        return None
    roots = [r.rstrip("/") or "/" for r in
             os.environ.get("CBE_PROTECTED_PATHS", DEFAULT_ROOTS).split(":") if r]
    cwd = event.get("cwd") or os.getcwd()
    ctx = Ctx(cwd, roots, os.environ)

    if tool == "Bash":
        command = (event.get("tool_input") or {}).get("command", "")
        if not command:
            return None
        command, fed = split_heredocs(command)
        ctx.text = command + "".join("\n" + body for _, body in fed)
        analyse(command, ctx, command)
        analyse_fed(fed, ctx)
        if ctx.unsure and RAW_DESTRUCTIVE.search(ctx.text):
            context_targets(ctx.unsure[0], ctx, ctx.text)
        # Command substitution, heredocs, and loops can hide targets from the parse.
        if not ctx.hits and re.search(r"\$\(|`|<<", ctx.text) and RAW_DESTRUCTIVE.search(ctx.text):
            context_targets("targets are computed at run time", ctx, ctx.text)
    else:
        file_tool_hits(event, ctx)

    if not ctx.hits:
        return None
    deadline = time.monotonic() + SCAN_MAX_SECONDS
    seen, lines = set(), []
    for action, path, host in ctx.hits:
        if (action, path, host) in seen:
            continue
        seen.add((action, path, host))
        if host == "?":
            lines.append("  - %s: %s  (may be on the ssh host; contents not checked)" % (action, path))
            continue
        if host:
            lines.append("  - %s: %s:%s  (on %s; contents not checked)" % (action, host, path, host))
            continue
        line = "  - %s: %s" % (action, path)
        bare = path.split("  (")[0]
        # Describe only what is really inside an existing root, never an ancestor such as "/".
        local = [r for r in roots if inside(bare, r) and os.path.isdir(r)]
        info = describe(bare, roots, deadline) if local and time.monotonic() < deadline else None
        if info:
            line += "\n      " + info
        lines.append(line)
    reason = (
        "cbe: this would delete, move, or overwrite group data under %s:\n%s\n"
        "Group data belongs to the whole group, and /groups snapshots are only hourly, "
        "so recent files may not be recoverable. Approve only if exactly these paths "
        "should change." % (", ".join(roots), "\n".join(lines[:20]))
    )
    if len(lines) > 20:
        reason += "\n  ... and %d more" % (len(lines) - 20)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    out = decide(event)
    if out:
        json.dump(out, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

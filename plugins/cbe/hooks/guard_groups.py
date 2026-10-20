#!/usr/bin/env python3
"""PreToolUse hook: ask before Bash commands that delete, move, or overwrite
data under protected storage (by default /groups) on CBE.next.

Reads the hook event as JSON on stdin. When a command would touch a protected
path, it prints a PreToolUse decision of "ask" with the affected paths, so the
user confirms exactly those paths. Anything else exits 0 with no output.

The parse is deliberately conservative: when a target can't be resolved
(unset variables, command substitution, inline interpreter code) and the
command runs in or names a protected path, it asks.

Environment:
  CBE_PROTECTED_PATHS  colon-separated roots to protect (default: /groups)
  CBE_GROUPS_GUARD     set to "off" to disable the hook
"""

import glob
import json
import os
import re
import shlex
import sys

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

RAW_DESTRUCTIVE = re.compile(
    r"\b(rm|rmdir|unlink|shred|truncate|mv)\b|-delete\b|--delete|"
    r"rclone\s+(sync|move|moveto|delete|deletefile|purge|rmdirs?)\b|"
    r"rmtree|os\.(remove|unlink|rename|replace)|file\.remove|unlink\(|"
    r"--delete-destination"
)


class Ctx:
    def __init__(self, cwd, roots, env):
        self.cwd = cwd
        self.roots = roots
        self.env = dict(env)
        self.hits = []          # (action, path)
        self.unsure = []        # reasons we couldn't resolve a target


def under(path, root):
    path = path.rstrip("/") or "/"
    root = root.rstrip("/") or "/"
    return path == root or path.startswith(root + "/") or root.startswith(path + "/") or path == "/"


def protected(path, ctx):
    candidates = {os.path.normpath(path)}
    try:
        candidates.add(os.path.realpath(path))
    except OSError:
        pass
    return any(under(c, r) for c in candidates for r in ctx.roots)


def expand(arg, ctx):
    """Return (paths, unresolved) for one shell word."""
    unresolved = False

    def sub(m):
        nonlocal unresolved
        name = m.group(1) or m.group(2)
        if name in ctx.env:
            return ctx.env[name]
        unresolved = True
        return ""

    s = re.sub(r"\$\{(\w+)[^}]*\}|\$(\w+)", sub, arg)
    if "$(" in s or "`" in s:
        unresolved = True
        s = re.sub(r"\$\(.*?\)|`.*?`", "", s)
    s = os.path.expanduser(s)
    if not os.path.isabs(s):
        s = os.path.join(ctx.cwd, s)
    s = os.path.normpath(s)
    if any(c in s for c in "*?["):
        matches = glob.glob(s)
        return (matches or [s]), unresolved
    return [s], unresolved


def check(action, args, ctx, must_exist=True):
    for a in args:
        paths, unresolved = expand(a, ctx)
        for p in paths:
            if not protected(p, ctx):
                continue
            if unresolved:
                ctx.hits.append((action, p + "  (contains unset variable or substitution: %s)" % a))
            elif not must_exist or os.path.lexists(p):
                ctx.hits.append((action, p))


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
            ctx.env[name] = re.sub(r"\$\{?(\w+)\}?", lambda m: ctx.env.get(m.group(1), ""), value)
        words = words[1:]
    if not words:
        return

    cmd = os.path.basename(words[0])
    args = words[1:]

    if cmd == "cd":
        target = args[0] if args else os.path.expanduser("~")
        paths, _ = expand(target, ctx)
        ctx.cwd = paths[0]
        return

    if cmd in WRAPPERS:
        for j, a in enumerate(args):
            if os.path.basename(a) in (REMOVE_CMDS | MOVE_CMDS | OVERWRITE_LAST_CMDS
                                       | OVERWRITE_ALL_CMDS | SHELLS | INTERPRETERS
                                       | {"find", "rsync", "rclone", "azcopy", "dd"}):
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
        if len(pos) >= 2:
            dest, _ = expand(pos[-1], ctx)
            if os.path.isfile(dest[0]):
                check("overwrite", pos[-1:], ctx)
    elif cmd == "truncate":
        check("truncate", positional(args, {"-s", "-r"}), ctx)
    elif cmd == "tee":
        if not any(a in ("-a", "--append") for a in args):
            check("overwrite (tee)", positional(args), ctx)
    elif cmd == "dd":
        check("overwrite (dd)", [a[3:] for a in args if a.startswith("of=")], ctx)
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
        if any(a.startswith("--delete") or a.startswith("--remove-source-files") for a in args):
            pos = [a for a in positional(args, {"-e", "--rsh"}) if not is_remote(a)]
            if any(a.startswith("--delete") for a in args) and pos:
                check("delete (rsync --delete destination)", pos[-1:], ctx, must_exist=False)
            if "--remove-source-files" in args and len(pos) > 1:
                check("delete (rsync --remove-source-files)", pos[:-1], ctx)
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
    named = []
    for t in re.findall(r"[~\w./${}-]+", whole):
        if "/" in t:
            paths, _ = expand(t, ctx)
            named += [p for p in paths if protected(p, ctx)]
    if named or protected(ctx.cwd, ctx):
        where = sorted(set(named)) or [ctx.cwd + "  (working directory)"]
        for p in where:
            ctx.hits.append(("possible delete/move: " + reason, p))


def decide(event):
    if os.environ.get("CBE_GROUPS_GUARD", "").lower() == "off":
        return None
    if event.get("tool_name") != "Bash":
        return None
    command = (event.get("tool_input") or {}).get("command", "")
    if not command:
        return None
    roots = [r.rstrip("/") or "/" for r in
             os.environ.get("CBE_PROTECTED_PATHS", DEFAULT_ROOTS).split(":") if r]
    cwd = event.get("cwd") or os.getcwd()
    ctx = Ctx(cwd, roots, os.environ)

    analyse(command, ctx, command)
    if ctx.unsure and RAW_DESTRUCTIVE.search(command):
        context_targets(ctx.unsure[0], ctx, command)
    # Command substitution, heredocs, and loops can hide targets from the parse.
    if not ctx.hits and re.search(r"\$\(|`|<<", command) and RAW_DESTRUCTIVE.search(command):
        context_targets("targets are computed at run time", ctx, command)

    if not ctx.hits:
        return None
    seen, lines = set(), []
    for action, path in ctx.hits:
        if (action, path) not in seen:
            seen.add((action, path))
            lines.append("  - %s: %s" % (action, path))
    reason = (
        "cbe: this command would delete, move, or overwrite group data under %s:\n%s\n"
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

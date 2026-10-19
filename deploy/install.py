#!/usr/bin/env python3
"""Stage a managed Unix Claude Code and Codex deployment from this reviewed checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MARKER = "Managed by CLIP-HPC deploy/install.py."
SNAPSHOTS = Path("/usr/local/share/clip-hpc")
# Both host catalogs and the shared plugin tree; only cbe is installed automatically.
CONTENT = (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json", "plugins/cbe")
CLAUDE_MANAGED = Path("/Library/Application Support/ClaudeCode" if sys.platform == "darwin"
                      else "/etc/claude-code")
# A drop-in has no comment syntax; this file name is the ownership marker.
CLAUDE_DROPIN = "managed-settings.d/50-clip-hpc.json"


def ensure_directory(path):
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        directory.chmod(0o755)


def owned(target):
    if not target.is_file():
        return False
    return target.suffix == ".json" or any(
        MARKER in line for line in target.read_text().splitlines()[:2])


def check_binary(binary, name):
    if not binary.is_absolute() or binary == Path("/usr/local/bin") / name:
        raise ValueError(f"--{name}-bin must be absolute and distinct from /usr/local/bin/{name}")


def snapshot(destdir):
    """Publish an immutable, content-addressed snapshot; return its host path."""
    with tempfile.TemporaryDirectory(prefix="clip-hpc-") as temporary:
        source = Path(temporary) / "marketplace"
        for relative in CONTENT:
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if (REPO / relative).is_dir():
                shutil.copytree(REPO / relative, target)
            else:
                shutil.copyfile(REPO / relative, target)
        digest = hashlib.sha256()
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(source)).encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
        host_root = SNAPSHOTS / digest.hexdigest()
        deployed = destdir / host_root.relative_to("/")
        if not deployed.exists():
            ensure_directory(deployed.parent)
            # Publish only complete snapshots, including after an interrupted run.
            with tempfile.TemporaryDirectory(prefix=".stage-", dir=deployed.parent) as staging:
                ready = Path(staging) / "marketplace"
                shutil.copytree(source, ready)
                for path in [ready, *ready.rglob("*")]:
                    path.chmod(0o755 if path.is_dir() else 0o644)
                ready.rename(deployed)
    return host_root


def install(destdir, codex_bin=None, claude_bin=None, claude_managed=CLAUDE_MANAGED):
    if not (codex_bin or claude_bin):
        raise ValueError("Pass --codex-bin, --claude-bin, or both")
    outputs = {}  # target -> (template, mode)
    if codex_bin:
        check_binary(codex_bin, "codex")
        for name in ("config.toml", "requirements.toml"):
            outputs[destdir / "etc/codex" / name] = (HERE / "codex" / name, 0o644)
        outputs[destdir / "usr/local/bin/codex"] = (HERE / "codex/codex.sh", 0o755)
    if claude_bin:
        check_binary(claude_bin, "claude")
        outputs[destdir / claude_managed.relative_to("/") / CLAUDE_DROPIN] = (
            HERE / "claude/managed-settings.json", 0o644)
        outputs[destdir / "usr/local/bin/claude"] = (HERE / "claude/claude.sh", 0o755)
    # Refuse to clobber files owned by another deployment mechanism.
    for target in outputs:
        if target.is_symlink() or (target.exists() and not owned(target)):
            raise ValueError(f"Merge or relocate the existing file before deployment: {target}")

    host_root = snapshot(destdir)
    values = {
        "@MARKETPLACE_ROOT@": json.dumps(str(host_root)),
        "@CODEX_BIN@": shlex.quote(str(codex_bin)),
        "@CLAUDE_BIN@": shlex.quote(str(claude_bin)),
        "@MARKETPLACE_CONFIG@": shlex.quote(
            "marketplaces.clip-hpc.source=" + json.dumps(str(host_root))),
    }
    for target, (template, mode) in outputs.items():
        content = template.read_text()
        if template.suffix == ".sh":
            # Shell needs shell quoting; TOML and JSON take the JSON string.
            values_here = {**values, "@MARKETPLACE_ROOT@": shlex.quote(str(host_root))}
        else:
            values_here = values
        for placeholder, value in values_here.items():
            content = content.replace(placeholder, value)
        ensure_directory(target.parent)
        target.write_text(content)
        target.chmod(mode)
    print(f"Staged {host_root} and {len(outputs)} host files under {destdir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", type=Path,
                        help="absolute path to the centrally installed real Codex binary")
    parser.add_argument("--claude-bin", type=Path,
                        help="absolute path to the centrally installed real Claude Code binary")
    parser.add_argument("--claude-managed-dir", type=Path, default=CLAUDE_MANAGED,
                        help=f"Claude Code managed-settings directory on the host (default: {CLAUDE_MANAGED})")
    parser.add_argument("--destdir", type=Path, default=Path("/"),
                        help="staging root; embedded paths remain host-absolute (default: /)")
    args = parser.parse_args()
    try:
        install(args.destdir.resolve(), args.codex_bin, args.claude_bin, args.claude_managed_dir)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

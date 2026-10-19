#!/usr/bin/env python3
"""Stage a managed Unix Codex deployment from this reviewed checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MARKER = "Managed by CLIP-HPC deploy/codex/install.py."


def ensure_directory(path):
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        directory.chmod(0o755)


def install(destdir, codex_bin):
    if not codex_bin.is_absolute() or codex_bin == Path("/usr/local/bin/codex"):
        raise ValueError("--codex-bin must be absolute and distinct from /usr/local/bin/codex")
    destinations = [destdir / "etc/codex" / name
                    for name in ("config.toml", "requirements.toml")]
    launcher = destdir / "usr/local/bin/codex"
    # Refuse to clobber configuration owned by another deployment mechanism.
    for target in [*destinations, launcher]:
        if target.is_symlink() or (target.exists() and (
                not target.is_file() or not any(
                    MARKER in line for line in target.read_text().splitlines()[:2]))):
            raise ValueError(f"Merge or relocate the existing file before deployment: {target}")

    # Immutable, content-addressed snapshots avoid stale files after removals.
    # Keep the common catalog intact; only cbe is automatically installed.
    with tempfile.TemporaryDirectory(prefix="clip-hpc-codex-") as temporary:
        snapshot = Path(temporary) / "marketplace"
        catalog = snapshot / ".agents/plugins/marketplace.json"
        catalog.parent.mkdir(parents=True)
        shutil.copyfile(REPO / ".agents/plugins/marketplace.json", catalog)
        shutil.copytree(REPO / "plugins/cbe", snapshot / "plugins/cbe")
        files = sorted(p for p in snapshot.rglob("*") if p.is_file())
        digest = hashlib.sha256()
        for path in files:
            digest.update(str(path.relative_to(snapshot)).encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
        host_root = Path("/usr/local/share/clip-hpc/codex") / digest.hexdigest()
        deployed = destdir / host_root.relative_to("/")
        if not deployed.exists():
            ensure_directory(deployed.parent)
            # Publish only complete snapshots, including after an interrupted run.
            with tempfile.TemporaryDirectory(prefix=".stage-", dir=deployed.parent) as staging:
                ready = Path(staging) / "marketplace"
                shutil.copytree(snapshot, ready)
                for path in [ready, *ready.rglob("*")]:
                    path.chmod(0o755 if path.is_dir() else 0o644)
                ready.rename(deployed)

    for target in destinations:
        ensure_directory(target.parent)
        content = (HERE / target.name).read_text().replace(
            "@MARKETPLACE_ROOT@", json.dumps(str(host_root)))
        target.write_text(content)
        target.chmod(0o644)
    ensure_directory(launcher.parent)
    launcher.write_text((HERE / "codex.sh").read_text().replace(
        "@CODEX_BIN@", shlex.quote(str(codex_bin))).replace(
        "@MARKETPLACE_CONFIG@", shlex.quote(
            "marketplaces.clip-hpc.source=" + json.dumps(str(host_root)))))
    launcher.chmod(0o755)
    print(f"Staged {host_root} and /usr/local/bin/codex under {destdir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", required=True, type=Path,
                        help="absolute path to the centrally installed real Codex binary")
    parser.add_argument("--destdir", type=Path, default=Path("/"),
                        help="staging root; embedded paths remain host-absolute (default: /)")
    args = parser.parse_args()
    try:
        install(args.destdir.resolve(), args.codex_bin)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

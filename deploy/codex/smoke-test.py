#!/usr/bin/env python3
"""Exercise the deployed launcher with real Codex and isolated user state."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def run(command, env, cwd):
    result = subprocess.run(command, env=env, cwd=cwd, capture_output=True,
                            text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"{' '.join(command)} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def main():
    binary = shutil.which("codex")
    if not binary:
        raise RuntimeError("Install Codex CLI 0.163.0 to run this check")
    with tempfile.TemporaryDirectory(prefix="codex-host-smoke-") as temporary:
        root = Path(temporary)
        # Exercise shell quoting as well as packaging.
        stage = root / "staged host"
        real_binary = root / "real codex"
        real_binary.symlink_to(Path(binary).resolve())
        env = dict(os.environ, CODEX_HOME=str(root / "user"))
        Path(env["CODEX_HOME"]).mkdir()
        env.pop("OPENAI_API_KEY", None)
        run(["python3", str(HERE / "install.py"), "--destdir", str(stage),
             "--codex-bin", str(real_binary)], env, root)
        # Remap final host paths for this test, without touching /etc or /usr.
        launcher = stage / "usr/local/bin/codex"
        snapshots = stage / "usr/local/share/clip-hpc/codex"
        snapshot = next(snapshots.iterdir())
        host_path = "/" + str(snapshot.relative_to(stage))
        launcher.write_text(launcher.read_text().replace(host_path, str(snapshot)))
        config = (stage / "etc/codex/config.toml").read_text().replace(host_path, str(snapshot))
        (Path(env["CODEX_HOME"]) / "config.toml").write_text(config)
        for _ in range(2):
            listing = json.loads(run([str(launcher), "plugin", "list", "--json",
                                      "--marketplace", "clip-hpc"], env, root))
            installed = listing["installed"]
            assert len(installed) == 1 and installed[0]["pluginId"] == "cbe@clip-hpc"
            assert installed[0]["enabled"] is True
        cache = Path(env["CODEX_HOME"]) / "plugins/cache/clip-hpc/cbe"
        manifests = list(cache.glob("*/skills/*/SKILL.md"))
        expected = list((REPO / "plugins/cbe/skills").glob("*/SKILL.md"))
        assert len(manifests) == len(expected) == 6
        for path in manifests:
            assert path.read_bytes() == (REPO / "plugins/cbe/skills" / path.parent.name / "SKILL.md").read_bytes()
        assert not list(cache.rglob("AGENTS.md"))
        assert not (Path(env["CODEX_HOME"]) / "plugins/cache/clip-hpc/ops").exists()
        assert run([str(launcher), "--version"], env, root) == run([binary, "--version"], env, root)
        # An installation error must prevent running the requested command.
        shutil.rmtree(snapshot)
        failed = subprocess.run([str(launcher), "--version"], env=env, cwd=root,
                                capture_output=True, text=True, timeout=60)
        assert failed.returncode != 0 and "codex-cli" not in failed.stdout
        print("Managed launcher: fresh-user install, repeat launch, six skills, argument forwarding, and failure handling passed.")


if __name__ == "__main__":
    main()

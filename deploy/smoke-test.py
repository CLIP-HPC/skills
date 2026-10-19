#!/usr/bin/env python3
"""Exercise the deployed launchers with real clients and isolated user state."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SKILLS = sorted(p.parent.name for p in (REPO / "plugins/cbe/skills").glob("*/SKILL.md"))


def run(command, env, cwd):
    result = subprocess.run(command, env=env, cwd=cwd, capture_output=True,
                            text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"{' '.join(command)} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def stage(root, binaries):
    """Install into a staging root and remap final host paths for this test."""
    stage = root / "staged host"  # Exercise shell quoting as well as packaging.
    links = {}
    for name, binary in binaries.items():
        links[name] = root / f"real {name}"
        links[name].symlink_to(Path(binary).resolve())
    run(["python3", str(HERE / "install.py"), "--destdir", str(stage),
         "--claude-managed-dir", "/etc/claude-code",
         *[arg for name in links for arg in (f"--{name}-bin", str(links[name]))]], os.environ, root)
    snapshot = next((stage / "usr/local/share/clip-hpc").iterdir())
    host_path = "/" + str(snapshot.relative_to(stage))
    for path in [*(stage / "usr/local/bin").iterdir(), *(p for p in (stage / "etc").rglob("*") if p.is_file())]:
        # The Claude launcher holds the bare path as a shell word; others embed it in strings.
        new = shlex.quote(str(snapshot)) if path.name == "claude" else str(snapshot)
        path.write_text(path.read_text().replace(host_path, new))
    return stage, snapshot


def check_launch_failure(launcher, env, root, real):
    # An installation error must prevent running the requested command.
    failed = subprocess.run([str(launcher), "--version"], env=env, cwd=root,
                            capture_output=True, text=True, timeout=60)
    assert failed.returncode != 0 and real not in failed.stdout, failed.stdout


def codex(root, stage, snapshot, binary):
    env = dict(os.environ, CODEX_HOME=str(root / "codex-user"))
    env.pop("OPENAI_API_KEY", None)
    Path(env["CODEX_HOME"]).mkdir()
    shutil.copyfile(stage / "etc/codex/config.toml", Path(env["CODEX_HOME"]) / "config.toml")
    launcher = stage / "usr/local/bin/codex"
    for _ in range(2):
        listing = json.loads(run([str(launcher), "plugin", "list", "--json",
                                  "--marketplace", "clip-hpc"], env, root))
        installed = listing["installed"]
        assert len(installed) == 1 and installed[0]["pluginId"] == "cbe@clip-hpc"
        assert installed[0]["enabled"] is True
    cache = Path(env["CODEX_HOME"]) / "plugins/cache/clip-hpc/cbe"
    manifests = list(cache.glob("*/skills/*/SKILL.md"))
    assert sorted(p.parent.name for p in manifests) == SKILLS
    for path in manifests:
        assert path.read_bytes() == (REPO / "plugins/cbe/skills" / path.parent.name / "SKILL.md").read_bytes()
    assert not list(cache.rglob("AGENTS.md"))
    assert not (Path(env["CODEX_HOME"]) / "plugins/cache/clip-hpc/ops").exists()
    version = run([binary, "--version"], env, root)
    assert run([str(launcher), "--version"], env, root) == version
    return env, launcher, version


def claude(root, stage, snapshot, binary):
    config = root / "claude-user"
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(config))
    for secret in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        env.pop(secret, None)
    config.mkdir()
    launcher = stage / "usr/local/bin/claude"
    settings = json.loads((stage / "etc/claude-code/managed-settings.d/50-clip-hpc.json").read_text())
    assert settings["extraKnownMarketplaces"]["clip-hpc"]["source"]["path"] == str(snapshot)
    for _ in range(2):
        listing = run([str(launcher), "plugin", "list"], env, root)
        assert "cbe@clip-hpc" in listing and "enabled" in listing, listing
        assert str(snapshot / "plugins/cbe") in listing, listing
    assert (config / "plugins/clip-hpc-snapshot").read_text().strip() == str(snapshot)
    version = run([binary, "--version"], env, root)
    assert run([str(launcher), "--version"], env, root) == version
    # Simulate a new deployment: the next launch must bootstrap again.
    (config / "plugins/clip-hpc-snapshot").write_text("/previous/snapshot\n")
    return env, launcher, version


def main():
    binaries = {name: shutil.which(name) for name in ("codex", "claude")}
    missing = [name for name, path in binaries.items() if not path]
    if missing:
        raise RuntimeError(f"Install {', '.join(missing)} to run this check")
    with tempfile.TemporaryDirectory(prefix="clip-hpc-host-smoke-") as temporary:
        root = Path(temporary)
        stage_root, snapshot = stage(root, binaries)
        launches = [codex(root, stage_root, snapshot, binaries["codex"]),
                    claude(root, stage_root, snapshot, binaries["claude"])]
        shutil.rmtree(snapshot)
        for env, launcher, version in launches:
            check_launch_failure(launcher, env, root, version.strip())
        print("Managed launchers (Codex, Claude Code): fresh-user install, repeat launch, "
              "six skills, argument forwarding, and failure handling passed.")


if __name__ == "__main__":
    main()

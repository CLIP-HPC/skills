#!/usr/bin/env python3
"""Test local CLI packaging in temporary client state, without account credentials."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, environment, cwd):
    result = subprocess.run(command, env=environment, cwd=cwd, capture_output=True,
                            text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"{' '.join(command)} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def local_plugins():
    catalog = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    return [entry["name"] for entry in catalog["plugins"] if isinstance(entry["source"], str)]


def verify_skills(cache, source):
    installed = sorted(cache.glob(f"clip-hpc/{source.name}/*/skills/*/SKILL.md"))
    expected = sorted((source / "skills").glob("*/SKILL.md"))
    if sorted(path.parent.name for path in installed) != [path.parent.name for path in expected]:
        raise RuntimeError(f"Incomplete installed skill bundle in {cache}")
    for manifest in cache.glob(f"clip-hpc/{source.name}/*/plugin.json"):
        if (manifest.parent / "AGENTS.md").exists():
            raise RuntimeError("Repository maintenance instructions leaked into the installed plugin")
    for path in installed:
        original = source / "skills" / path.parent.name
        for relative in ("SKILL.md", "agents/openai.yaml"):
            if (path.parent / relative).read_bytes() != (original / relative).read_bytes():
                raise RuntimeError(f"Installed skill differs from source: {path.parent.name}/{relative}")
    return len(installed)


def main():
    plugins = local_plugins()
    for executable in ("codex", "claude"):
        if not shutil.which(executable):
            raise RuntimeError(f"Install {executable} before running the CLI smoke test")
    with tempfile.TemporaryDirectory(prefix="clip-hpc-smoke-") as temporary:
        state = Path(temporary)
        environment = os.environ.copy()
        # Use each client's supported configuration-directory setting. Never
        # register or install this test bundle in the user's real client state.
        environment["CODEX_HOME"] = str(state / "codex-state")
        environment["CLAUDE_CONFIG_DIR"] = str(state / "claude-state")
        Path(environment["CODEX_HOME"]).mkdir()
        Path(environment["CLAUDE_CONFIG_DIR"]).mkdir()
        for secret in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
            environment.pop(secret, None)

        # Check the generated Claude manifests. Claude's validator does not
        # reject invalid SKILL.md frontmatter; scripts/validate.py covers that.
        run(["claude", "plugin", "validate", "--strict", str(ROOT)], environment, ROOT)
        for name in plugins:
            for folder in (ROOT / "plugins" / name, ROOT / "plugins" / name / "skills"):
                run(["claude", "plugin", "validate", "--strict", str(folder)], environment, ROOT)
        run(["claude", "plugin", "marketplace", "add", str(ROOT)], environment, ROOT)
        for name in plugins:
            run(["claude", "plugin", "install", f"{name}@clip-hpc", "--scope", "user"], environment, ROOT)
            count = verify_skills(state / "claude-state/plugins/cache", ROOT / "plugins" / name)
            print(f"Claude: validation passed; {name} installed with {count} skills and picker metadata.")

        # Deliberately omit the Claude manifest to prove that Codex can install
        # the portable manifest rather than succeeding through legacy fallback.
        portable = state / "portable-marketplace"
        for name in plugins:
            shutil.copytree(ROOT / "plugins" / name, portable / "plugins" / name,
                            ignore=shutil.ignore_patterns(".claude-plugin"))
        catalog = portable / ".agents/plugins/marketplace.json"
        catalog.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / ".agents/plugins/marketplace.json", catalog)
        run(["codex", "plugin", "marketplace", "add", str(portable), "--json"], environment, portable)
        for name in plugins:
            run(["codex", "plugin", "add", f"{name}@clip-hpc", "--json"], environment, portable)
        listing = json.loads(run(["codex", "plugin", "list", "--json", "--marketplace", "clip-hpc"],
                                 environment, portable))
        if len(listing.get("installed") or []) != len(plugins):
            raise RuntimeError(f"Codex did not report all of {', '.join(plugins)} as installed")
        for name in plugins:
            count = verify_skills(state / "codex-state/plugins/cache", portable / "plugins" / name)
            print(f"Codex: portable {name} installed with {count} skills and picker metadata.")


if __name__ == "__main__":
    main()

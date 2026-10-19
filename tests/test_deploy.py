"""Host configuration templates render to valid, stable settings."""
import json
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import unittest

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
CLONE = "/software/system/agents/skills"


def render(relative):
    text = (DEPLOY / relative).read_text()
    # The clone path is the only site-specific value; nothing else may vary per release.
    placeholders = set(re.findall(r"@[A-Z_]+@", text))
    assert placeholders <= {"@SKILLS_CLONE@"}, placeholders
    return text.replace("@SKILLS_CLONE@", CLONE)


class HostTemplateTests(unittest.TestCase):
    def test_claude_managed_settings(self):
        settings = json.loads(render("claude/50-clip-hpc.json"))
        self.assertEqual(settings["extraKnownMarketplaces"]["clip-hpc"]["source"],
                         {"source": "directory", "path": CLONE})
        self.assertEqual(settings["enabledPlugins"], {"cbe@clip-hpc": True})
        self.assertEqual(settings["env"], {"DISABLE_UPDATES": "1", "DISABLE_AUTOUPDATER": "1"})

    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11")
    def test_codex_config_and_requirements(self):
        config = tomllib.loads(render("codex/config.toml"))
        # Only git marketplaces make Codex install configured plugins at startup.
        self.assertEqual(config["marketplaces"]["clip-hpc"],
                         {"source_type": "git", "source": CLONE})
        self.assertEqual(config["plugins"], {"cbe@clip-hpc": {"enabled": True}})
        self.assertIs(config["check_for_update_on_startup"], False)
        requirements = tomllib.loads(render("codex/requirements.toml"))
        self.assertEqual(requirements, {"check_for_update_on_startup": False,
                                        "features": {"in_app_updates": False}})

    def test_marketplace_name_matches_catalogs(self):
        for catalog in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
            data = json.loads((ROOT / catalog).read_text())
            self.assertEqual(data["name"], "clip-hpc")
            self.assertIn("cbe", [plugin["name"] for plugin in data["plugins"]])


class InstallHostScriptTests(unittest.TestCase):
    """Run deploy/install-host.sh against a staging root, never the real /etc."""

    def run_script(self, root, *args, umask=-1):
        return subprocess.run(["sh", str(DEPLOY / "install-host.sh"), "--root", str(root), *args],
                              capture_output=True, text=True, cwd=root, umask=umask)

    def targets(self, root):
        claude = ("Library/Application Support/ClaudeCode" if platform.system() == "Darwin"
                  else "etc/claude-code")
        return [root / claude / "managed-settings.d/50-clip-hpc.json",
                root / "etc/codex/config.toml", root / "etc/codex/requirements.toml"]

    def test_install_is_idempotent_and_points_at_this_clone(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.run_script(root)
            self.assertEqual(first.returncode, 0, first.stderr)
            claude, config, requirements = self.targets(root)
            settings = json.loads(claude.read_text())
            self.assertEqual(settings["extraKnownMarketplaces"]["clip-hpc"]["source"]["path"], str(ROOT))
            self.assertIn(f'source = "{ROOT}"', config.read_text())
            for path in (claude, config, requirements):
                self.assertEqual(path.stat().st_mode & 0o777, 0o644)
                self.assertNotIn("@SKILLS_CLONE@", path.read_text())
            second = self.run_script(root)
            self.assertEqual(second.stdout.count("unchanged:"), 3, second.stdout)

    def test_foreign_file_stops_before_any_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claude, config, requirements = self.targets(root)
            requirements.parent.mkdir(parents=True)
            requirements.write_text('allowed_approval_policies = ["never"]\n')
            result = self.run_script(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("merge deploy/codex/requirements.toml by hand", result.stderr)
            self.assertFalse(claude.exists() or config.exists())
            self.assertEqual(requirements.read_text(), 'allowed_approval_policies = ["never"]\n')

    def test_private_umask_keeps_installed_configuration_readable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_script(root, umask=0o077)
            self.assertEqual(result.returncode, 0, result.stderr)
            for target in self.targets(root):
                self.assertEqual(target.stat().st_mode & 0o777, 0o644)
                directory = target.parent
                while directory != root:
                    self.assertEqual(directory.stat().st_mode & 0o777, 0o755, str(directory))
                    directory = directory.parent

    def test_reinstall_repairs_permissions_without_rewriting_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(self.run_script(root).returncode, 0)
            targets = self.targets(root)
            directories = {target.parent for target in targets}
            directories.add(targets[0].parent.parent)  # Claude's managed root.
            original = {target: (target.read_bytes(), target.stat().st_mtime_ns) for target in targets}
            for target in targets:
                target.chmod(0o600)
            for directory in directories:
                directory.chmod(0o700)

            dry_run = self.run_script(root, "--dry-run")
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            for target in targets:
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            for directory in directories:
                self.assertEqual(directory.stat().st_mode & 0o777, 0o700)

            result = self.run_script(root, umask=0o077)
            self.assertEqual(result.returncode, 0, result.stderr)
            for target in targets:
                self.assertEqual(target.stat().st_mode & 0o777, 0o644)
                self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), original[target])
            for directory in directories:
                self.assertEqual(directory.stat().st_mode & 0o777, 0o755)

    def test_remove_keeps_foreign_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(self.run_script(root).returncode, 0)
            claude, config, requirements = self.targets(root)
            requirements.write_text("model = \"x\"\n")
            result = self.run_script(root, "--remove")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(claude.exists() or config.exists())
            self.assertTrue(requirements.exists())

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_script(root, "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("write:"), 3)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

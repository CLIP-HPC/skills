"""Host deployment regressions; all writes stay inside temporary staging roots."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("host_deploy", ROOT / "deploy/install.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


CODEX = Path("/opt/codex/bin/codex")
CLAUDE = Path("/opt/claude/bin/claude")
MANAGED = Path("/etc/claude-code")


def install(stage):
    deploy.install(stage, CODEX, CLAUDE, MANAGED)


class DeploymentTests(unittest.TestCase):
    def test_redeployment_is_stable_and_world_readable_under_private_umask(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            previous = os.umask(0o077)
            try:
                install(stage)
            finally:
                os.umask(previous)
            initial = {p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}
            install(stage)
            self.assertEqual(initial, {p.relative_to(stage): p.read_bytes()
                                       for p in stage.rglob("*") if p.is_file()})
            for path in stage.rglob("*"):
                self.assertEqual(path.stat().st_mode & 0o777,
                                 0o755 if path.is_dir() or path.name in {"codex", "claude"} else 0o644)

    def test_existing_policy_or_symlink_is_preserved_before_any_deployment(self):
        cases = [("etc/codex/requirements.toml", False), ("etc/codex/requirements.toml", True),
                 ("usr/local/bin/claude", False), ("usr/local/bin/claude", True),
                 # The drop-in's file name marks ownership, so only a symlink is refused.
                 ("etc/claude-code/managed-settings.d/50-clip-hpc.json", True)]
        for relative, symlink in cases:
            with self.subTest(target=relative, symlink=symlink), \
                    tempfile.TemporaryDirectory() as temporary:
                stage = Path(temporary)
                target = stage / relative
                target.parent.mkdir(parents=True)
                original = stage / "policy.toml"
                original.write_text("allowed_approval_policies = []\n")
                if symlink:
                    target.symlink_to(original)
                else:
                    target.write_text(original.read_text())
                with self.assertRaises(ValueError):
                    install(stage)
                self.assertEqual(target.read_text(), original.read_text())
                self.assertFalse((stage / "usr/local/share").exists())

    def test_requires_a_client(self):
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(ValueError):
            deploy.install(Path(temporary))

    def test_changed_content_gets_a_clean_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            catalog = source / ".agents/plugins/marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text('{"name":"clip-hpc","plugins":[]}')
            (source / ".claude-plugin").mkdir()
            (source / ".claude-plugin/marketplace.json").write_text('{"name":"clip-hpc","plugins":[]}')
            plugin = source / "plugins/cbe"
            plugin.mkdir(parents=True)
            old_file = plugin / "removed.txt"
            old_file.write_text("old content")
            stage = base / "stage"
            with patch.object(deploy, "REPO", source):
                install(stage)
                old_config = (stage / "etc/codex/config.toml").read_text()
                old_file.unlink()
                (plugin / "new.txt").write_text("new content")
                install(stage)
            snapshots = list((stage / "usr/local/share/clip-hpc").iterdir())
            self.assertEqual(len(snapshots), 2)
            current = next(p for p in snapshots if (p / "plugins/cbe/new.txt").exists())
            self.assertFalse((current / "plugins/cbe/removed.txt").exists())
            self.assertNotEqual(old_config, (stage / "etc/codex/config.toml").read_text())

    def test_rejects_relative_or_recursive_binary(self):
        with tempfile.TemporaryDirectory() as temporary:
            for binary in ("codex", "/usr/local/bin/codex"):
                with self.subTest(binary=binary), self.assertRaises(ValueError):
                    deploy.install(Path(temporary), codex_bin=Path(binary))
            for binary in ("claude", "/usr/local/bin/claude"):
                with self.subTest(binary=binary), self.assertRaises(ValueError):
                    deploy.install(Path(temporary), claude_bin=Path(binary))

    def test_settings_and_launchers_point_at_the_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            install(stage)
            (snapshot,) = (stage / "usr/local/share/clip-hpc").iterdir()
            host_root = "/" + str(snapshot.relative_to(stage))
            settings = json.loads((stage / MANAGED.relative_to("/")
                                   / "managed-settings.d/50-clip-hpc.json").read_text())
            self.assertEqual(settings["extraKnownMarketplaces"]["clip-hpc"]["source"],
                             {"source": "directory", "path": host_root})
            self.assertEqual(settings["enabledPlugins"], {"cbe@clip-hpc": True})
            for relative in ("etc/codex/config.toml", "usr/local/bin/codex"):
                self.assertIn(host_root, (stage / relative).read_text())
            claude = (stage / "usr/local/bin/claude").read_text()
            self.assertIn(f"root={host_root}\n", claude)
            self.assertIn(f"exec {CLAUDE} ", claude)
            for relative in (".agents/plugins/marketplace.json",
                             ".claude-plugin/marketplace.json", "plugins/cbe/plugin.json"):
                self.assertTrue((snapshot / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()

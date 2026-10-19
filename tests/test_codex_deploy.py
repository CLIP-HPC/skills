"""Host deployment regressions; all writes stay inside temporary staging roots."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codex_deploy", ROOT / "deploy/codex/install.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class CodexDeploymentTests(unittest.TestCase):
    def test_redeployment_is_stable_and_world_readable_under_private_umask(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary)
            previous = os.umask(0o077)
            try:
                deploy.install(stage, Path("/opt/codex/bin/codex"))
            finally:
                os.umask(previous)
            initial = {p.relative_to(stage): p.read_bytes() for p in stage.rglob("*") if p.is_file()}
            deploy.install(stage, Path("/opt/codex/bin/codex"))
            self.assertEqual(initial, {p.relative_to(stage): p.read_bytes()
                                       for p in stage.rglob("*") if p.is_file()})
            for path in stage.rglob("*"):
                self.assertEqual(path.stat().st_mode & 0o777,
                                 0o755 if path.is_dir() or path.name == "codex" else 0o644)

    def test_existing_policy_or_symlink_is_preserved_before_any_deployment(self):
        for symlink in (False, True):
            with self.subTest(symlink=symlink), tempfile.TemporaryDirectory() as temporary:
                stage = Path(temporary)
                target = stage / "etc/codex/requirements.toml"
                target.parent.mkdir(parents=True)
                original = stage / "policy.toml"
                original.write_text("allowed_approval_policies = []\n")
                if symlink:
                    target.symlink_to(original)
                else:
                    target.write_text(original.read_text())
                with self.assertRaises(ValueError):
                    deploy.install(stage, Path("/opt/codex/bin/codex"))
                self.assertEqual(target.read_text(), original.read_text())
                self.assertFalse((stage / "usr").exists())

    def test_changed_content_gets_a_clean_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            catalog = source / ".agents/plugins/marketplace.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text('{"name":"clip-hpc","plugins":[]}')
            plugin = source / "plugins/cbe"
            plugin.mkdir(parents=True)
            old_file = plugin / "removed.txt"
            old_file.write_text("old content")
            stage = base / "stage"
            with patch.object(deploy, "REPO", source):
                deploy.install(stage, Path("/opt/codex/bin/codex"))
                old_config = (stage / "etc/codex/config.toml").read_text()
                old_file.unlink()
                (plugin / "new.txt").write_text("new content")
                deploy.install(stage, Path("/opt/codex/bin/codex"))
            snapshots = list((stage / "usr/local/share/clip-hpc/codex").iterdir())
            self.assertEqual(len(snapshots), 2)
            current = next(p for p in snapshots if (p / "plugins/cbe/new.txt").exists())
            self.assertFalse((current / "plugins/cbe/removed.txt").exists())
            self.assertNotEqual(old_config, (stage / "etc/codex/config.toml").read_text())

    def test_rejects_relative_or_recursive_binary(self):
        with tempfile.TemporaryDirectory() as temporary:
            for binary in ("codex", "/usr/local/bin/codex"):
                with self.subTest(binary=binary), self.assertRaises(ValueError):
                    deploy.install(Path(temporary), Path(binary))


if __name__ == "__main__":
    unittest.main()

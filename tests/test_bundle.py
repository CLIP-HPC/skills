import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bundle import generate, generated_files, inside
from validate import validate

spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install-skills.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


EXTERNAL = {"name": "external", "category": "Productivity", "description": "External plugin.",
            "source": {"source": "url", "url": "https://example.com/plugin.git"}}


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout"
        self.root.mkdir()
        for folder in ("plugins", "schemas"):
            shutil.copytree(ROOT / folder, self.root / folder)
        shutil.copyfile(ROOT / "marketplace.json", self.root / "marketplace.json")
        generate(self.root)

    def test_valid_bundle_and_idempotent_generation(self):
        self.assertEqual(validate(self.root), (1, 9))
        self.assertEqual(generate(self.root), [])

    def test_version_changes_reach_both_hosts_and_check_never_writes(self):
        path = self.root / "plugins/cbe/plugin.json"
        data = json.loads(path.read_text())
        data["version"] = "1.2.3"
        path.write_text(json.dumps(data))
        target = self.root / "plugins/cbe/.claude-plugin/plugin.json"
        before = target.read_bytes()
        with self.assertRaisesRegex(ValueError, "stale"):
            generate(self.root, check=True)
        self.assertEqual(target.read_bytes(), before)
        generate(self.root)
        self.assertEqual(json.loads(target.read_text())["version"], "1.2.3")
        self.assertEqual(validate(self.root), (1, 9))

    def test_missing_or_modified_generated_files_fail_validation(self):
        for target in generated_files(self.root):
            with self.subTest(target=target):
                before = target.read_bytes()
                target.unlink()
                with self.assertRaisesRegex(ValueError, "stale"):
                    validate(self.root)
                target.write_bytes(before + b"\n")
                with self.assertRaisesRegex(ValueError, "stale"):
                    validate(self.root)
                target.write_bytes(before)

    def test_invalid_portable_field_is_rejected(self):
        path = self.root / "plugins/cbe/plugin.json"
        data = json.loads(path.read_text())
        data["versoin"] = "1.2.3"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "versoin"):
            validate(self.root)

    def test_skill_name_must_match_its_directory(self):
        path = self.root / "plugins/cbe/skills/cbe-next/SKILL.md"
        path.write_text(path.read_text().replace("name: cbe-next", "name: other-skill", 1))
        with self.assertRaisesRegex(ValueError, "must match"):
            validate(self.root)

    def test_catalog_paths_cannot_escape_repository(self):
        for path in ("../other", "./../other", "/tmp/other"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                inside(self.root, path)

    def test_symlink_cannot_escape_repository(self):
        (self.root / "outside").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            inside(self.root, "./outside")

    def test_both_hosts_expose_the_same_plugins_and_sources(self):
        claude = json.loads((self.root / ".claude-plugin/marketplace.json").read_text())
        codex = json.loads((self.root / ".agents/plugins/marketplace.json").read_text())
        catalog = json.loads((self.root / "marketplace.json").read_text())
        codex_shared = [{key: value for key, value in entry.items() if key != "policy"}
                        for entry in codex["plugins"]]
        self.assertEqual(codex_shared, claude["plugins"])
        self.assertEqual(len(claude["plugins"]), len(catalog["plugins"]))
        self.assertEqual(claude["plugins"][0]["source"], "./plugins/cbe")
        self.assertEqual(codex["plugins"][0]["source"], "./plugins/cbe")

    def test_duplicate_remote_plugin_name_is_rejected(self):
        path = self.root / "marketplace.json"
        catalog = json.loads(path.read_text())
        catalog["plugins"].append({**EXTERNAL, "name": "cbe"})
        path.write_text(json.dumps(catalog))
        with self.assertRaisesRegex(ValueError, "duplicate plugin name"):
            validate(self.root)

    def test_remote_source_must_not_contain_credentials(self):
        path = self.root / "marketplace.json"
        catalog = json.loads(path.read_text())
        catalog["plugins"].append({**EXTERNAL, "source": {
            "source": "url", "url": "https://example:secret@example.com/plugin.git"}})
        path.write_text(json.dumps(catalog))
        with self.assertRaisesRegex(ValueError, "without credentials"):
            validate(self.root)

    def add_local_plugin(self, name, skill):
        """Add a minimal second local plugin with one skill to the catalog."""
        folder = self.root / "plugins" / name
        manifest = json.loads((self.root / "plugins/cbe/plugin.json").read_text())
        (folder / "skills" / skill).mkdir(parents=True)
        (folder / "plugin.json").write_text(json.dumps({**manifest, "name": name}))
        (folder / "skills" / skill / "SKILL.md").write_text(
            f"---\nname: {skill}\ndescription: Test skill.\nmetadata:\n"
            "  display-name: Test\n  short-description: A test skill for a second plugin\n"
            "  example-task: test.\n---\n\nBody.\n")
        path = self.root / "marketplace.json"
        catalog = json.loads(path.read_text())
        catalog["plugins"].append({"source": f"./plugins/{name}", "category": "Productivity"})
        path.write_text(json.dumps(catalog))

    def test_second_local_plugin_is_generated_and_validated(self):
        self.add_local_plugin("other", "other-skill")
        generate(self.root)
        self.assertEqual(validate(self.root), (2, 10))
        claude = json.loads((self.root / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual([entry["name"] for entry in claude["plugins"]], ["cbe", "other"])
        self.assertTrue((self.root / "plugins/other/.claude-plugin/plugin.json").is_file())
        self.assertTrue((self.root / "plugins/other/skills/other-skill/agents/openai.yaml").is_file())

    def test_skill_names_are_unique_across_plugins(self):
        self.add_local_plugin("other", "cbe-next")
        generate(self.root)
        with self.assertRaisesRegex(ValueError, "Duplicate skill name"):
            validate(self.root)

    def test_install_all_skills_and_repeat_without_changes(self):
        self.add_local_plugin("other", "other-skill")
        sources = installer.plugin_skills(self.root)
        self.assertEqual(sources, [self.root / "plugins/cbe/skills", self.root / "plugins/other/skills"])
        destination = self.root.parent / "destination with spaces"
        self.assertEqual(installer.install(sources, destination), 10)
        for skill in (path for source in sources for path in source.iterdir()):
            self.assertTrue((destination / skill.name).is_symlink())
            self.assertEqual((destination / skill.name).resolve(), skill.resolve())
        self.assertEqual(installer.install(sources, destination), 0)

    def test_install_selected_plugin_only(self):
        self.add_local_plugin("other", "other-skill")
        self.assertEqual(installer.plugin_skills(self.root, ["other"]),
                         [self.root / "plugins/other/skills"])
        with self.assertRaisesRegex(ValueError, "Unknown plugin"):
            installer.plugin_skills(self.root, ["missing"])

    def test_install_conflict_leaves_whole_destination_unchanged(self):
        source = self.root / "plugins/cbe/skills"
        for dangling in (False, True):
            destination = self.root.parent / f"conflict-{dangling}"
            destination.mkdir()
            conflict = destination / "cbe-triage"
            if dangling:
                conflict.symlink_to(destination / "missing")
            else:
                conflict.mkdir()
                (conflict / "keep").write_text("existing skill")
            with self.assertRaisesRegex(ValueError, "Refusing to replace"):
                installer.install([source], destination)
            self.assertEqual(list(destination.iterdir()), [conflict])


if __name__ == "__main__":
    unittest.main()

"""Host configuration templates render to valid, stable settings."""
import json
from pathlib import Path
import re
import unittest

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
CLONE = "/software/clip-hpc/skills"


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


if __name__ == "__main__":
    unittest.main()

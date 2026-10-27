#!/usr/bin/env python3
"""Link the skills of the catalog's plugins into a chosen local skill directory."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def plugin_skills(root, names=None):
    """Return the skill folders of local catalog plugins, optionally only those named."""
    catalog = json.loads((root / "marketplace.json").read_text())
    folders = {(root / entry["source"]).name: root / entry["source"] / "skills"
               for entry in catalog["plugins"] if isinstance(entry["source"], str)}
    unknown = sorted(set(names or ()) - set(folders))
    if unknown:
        raise ValueError(f"Unknown plugin: {', '.join(unknown)}; choose from {', '.join(folders)}")
    return [folder for name, folder in folders.items() if not names or name in names]


def install(sources, destination):
    skills = sorted((path for source in sources for path in source.iterdir()
                     if (path / "SKILL.md").is_file()), key=lambda path: path.name)
    if not skills:
        raise ValueError(f"No skills found in {', '.join(map(str, sources))}")
    # Preflight the whole bundle so a conflict doesn't leave a partial install.
    pending = []
    for skill in skills:
        target = destination / skill.name
        if target.is_symlink() and target.resolve() == skill.resolve():
            continue
        if target.exists() or target.is_symlink():
            raise ValueError(f"Refusing to replace {target}; choose another destination or resolve the conflict.")
        pending.append((skill, target))
    destination.mkdir(parents=True, exist_ok=True)
    for skill, target in pending:
        target.symlink_to(skill.resolve(), target_is_directory=True)
    return len(pending)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path,
                        help="For example ~/.agents/skills or ./my-project/.agents/skills")
    parser.add_argument("--plugin", action="append", metavar="NAME",
                        help="Link only this plugin's skills; repeat for several (default: all)")
    args = parser.parse_args()
    try:
        count = install(plugin_skills(ROOT, args.plugin), args.destination.expanduser().resolve())
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Linked {count} skills. Keep this checkout at its current path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

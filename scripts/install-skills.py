#!/usr/bin/env python3
"""Link the complete CBE skill bundle into a chosen local skill directory."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def install(source, destination):
    skills = sorted(path for path in source.iterdir() if (path / "SKILL.md").is_file())
    if not skills:
        raise ValueError(f"No skills found in {source}")
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
    args = parser.parse_args()
    try:
        count = install(ROOT / "plugins/cbe/skills", args.destination.expanduser().resolve())
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Linked {count} skills. Keep this checkout at its current path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

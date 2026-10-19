#!/usr/bin/env python3
"""Validate portable manifests, skill discovery metadata, and generated adapters."""
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
import yaml

from bundle import ROOT, SCHEMA, generate, inside, load_json, skill_metadata

NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(root):
    root = root.resolve()
    catalog = load_json(root / "marketplace.json")
    require(set(catalog) == {"name", "display_name", "owner", "description", "plugins"},
            "Unexpected or missing catalog fields")
    require(nonempty(catalog["name"]) and NAME.fullmatch(catalog["name"]), "Invalid marketplace name")
    require(nonempty(catalog["display_name"]) and nonempty(catalog["description"]),
            "Marketplace display name and description are required")
    require(isinstance(catalog["owner"], dict) and nonempty(catalog["owner"].get("name")),
            "Marketplace owner.name is required")
    require(isinstance(catalog["plugins"], list) and catalog["plugins"], "Catalog has no plugins")
    schema = load_json(root / "schemas/plugin-1.0.0.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    plugin_names, paths, skill_names = set(), set(), set()
    for entry in catalog["plugins"]:
        require(isinstance(entry, dict), "Catalog entries must be mappings")
        require(nonempty(entry["category"]), "Missing plugin category")
        source = entry["source"]
        if isinstance(source, dict):
            require(set(entry) == {"name", "source", "description", "category"},
                    "External catalog entries need name, source, description, and category")
            name = entry["name"]
            require(nonempty(name) and NAME.fullmatch(name) and name not in plugin_names,
                    "Invalid or duplicate plugin name")
            plugin_names.add(name)
            require(nonempty(entry["description"]), "External plugin description is required")
            url = urlsplit(source.get("url", ""))
            require(set(source) == {"source", "url"} and source["source"] == "url"
                    and url.scheme == "https" and bool(url.hostname)
                    and not (url.username or url.password or url.query or url.fragment),
                    "External plugins need an HTTPS Git source without credentials")
            continue
        require(set(entry) == {"source", "category"},
                "Local catalog entries need source and category only")
        folder = inside(root, source)
        require(folder not in paths, f"Duplicate plugin path: {folder}")
        paths.add(folder)
        manifest = load_json(folder / "plugin.json")
        errors = sorted(validator.iter_errors(manifest), key=lambda error: str(error.path))
        require(not errors, f"{folder}/plugin.json: " + "; ".join(error.message for error in errors))
        require(manifest["$schema"] == SCHEMA, f"{folder}: wrong schema version")
        name = manifest["name"]
        require(NAME.fullmatch(name) and name == folder.name, f"{folder}: plugin name must match its folder")
        require(name not in plugin_names, f"Duplicate plugin name: {name}")
        plugin_names.add(name)
        require(nonempty(manifest.get("version")) and VERSION.fullmatch(manifest["version"]),
                f"{name}: expected a release version such as 0.2.0")
        require(nonempty(manifest.get("description")) and nonempty(manifest.get("author", {}).get("name")),
                f"{name}: description and author.name are required")
        # This generator currently adapts identity and instruction-only skills.
        require(not manifest.get("extensions"), f"{name}: add explicit adapter support before using extensions")
        skills = sorted((folder / "skills").iterdir())
        require(bool(skills), f"{name}: no skills packaged")
        for skill in skills:
            require(skill.is_dir() and (skill / "SKILL.md").is_file(), f"{skill}: missing SKILL.md")
            data = skill_metadata(skill / "SKILL.md")
            skill_name = data.get("name")
            require(isinstance(skill_name, str) and len(skill_name) <= 64
                    and NAME.fullmatch(skill_name) and skill_name == skill.name,
                    f"{skill}: skill name must match its folder and use kebab-case")
            require(skill_name not in skill_names, f"Duplicate skill name: {skill_name}")
            skill_names.add(skill_name)
            description = data.get("description")
            require(nonempty(description) and len(description) <= 1024,
                    f"{skill}: description must contain 1–1024 characters")
            require(not ({"<", ">"} & set(description)), f"{skill}: description contains angle brackets")
            metadata = data.get("metadata")
            require(isinstance(metadata, dict) and all(isinstance(k, str) and isinstance(v, str)
                                                      for k, v in metadata.items()),
                    f"{skill}: metadata must map strings to strings")
            require(all(nonempty(metadata.get(key)) for key in
                        ("display-name", "short-description", "example-task")),
                    f"{skill}: missing picker metadata")
            require(25 <= len(metadata["short-description"]) <= 64,
                    f"{skill}: short-description must contain 25–64 characters")
            body = (skill / "SKILL.md").read_text().split("\n---\n", 1)[1]
            require(bool(body.strip()), f"{skill}: empty instructions")
            # Check actual relative Markdown links, without fetching remote docs.
            for link in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", body):
                if urlsplit(link).scheme or link.startswith(("#", "/")):
                    continue
                target = (skill / link.split("#", 1)[0]).resolve()
                require(target.is_relative_to(folder) and target.exists(),
                        f"{skill}: broken or nonportable resource link: {link}")
    generate(root, check=True)
    return len(paths), len(skill_names)


def main():
    try:
        plugins, skills = validate(ROOT)
    except (ValueError, KeyError, TypeError, OSError, yaml.YAMLError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Validated {plugins} portable plugin(s), {skills} skills, and all generated adapters.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

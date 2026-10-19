#!/usr/bin/env bash
# Zip each skill for upload as a claude.ai organization or personal skill.
# Usage: scripts/package-skills.sh [skill ...]   (default: the cbe-next plugin's skills)
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dist="$repo_root/dist"
mkdir -p "$dist"

if [ "$#" -eq 0 ]; then
  set -- $(ls "$repo_root/plugins/cbe-next/skills")
fi

for skill in "$@"; do
  skill_dir="$(find "$repo_root/plugins" -type d -path "*/skills/$skill" | head -n 1)"
  if [ -z "$skill_dir" ]; then
    echo "error: skill '$skill' not found under plugins/*/skills/" >&2
    exit 1
  fi
  rm -f "$dist/$skill.zip"
  (cd "$(dirname "$skill_dir")" && zip -qr "$dist/$skill.zip" "$skill")
  echo "Wrote dist/$skill.zip"
done

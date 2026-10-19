#!/bin/sh
# Install or remove the CLIP-HPC host configuration for Claude Code and Codex.
# Run it from the shared clone, as root, on each host:
#   /software/system/agents/skills/deploy/install-host.sh [--dry-run] [--remove]
set -eu
# Configuration must be readable by users even when root has a private umask.
umask 022

usage() {
  echo "usage: $0 [--dry-run] [--remove] [--root DIR]" >&2
  exit 2
}

MARKER="Managed by CLIP-HPC deploy/install-host.sh"
root=/
dry_run=false
remove=false
while [ $# -gt 0 ]; do
  case $1 in
    --dry-run) dry_run=true ;;
    --remove) remove=true ;;
    # Staging root for tests and image builds; written paths still name the real clone.
    --root) [ $# -ge 2 ] || usage; root=$2; shift ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
  shift
done

# The clone is wherever this script lives; keep the logical path, as users see it.
deploy=$(cd "$(dirname "$0")" && pwd)
clone=$(dirname "$deploy")
for required in .git .claude-plugin/marketplace.json .agents/plugins/marketplace.json plugins/cbe; do
  [ -e "$clone/$required" ] || { echo "error: $clone is not a clone of CLIP-HPC/skills (missing $required)" >&2; exit 1; }
done
case $clone in
  *'#'*|*'&'*|*'\'*|*'"'*) echo "error: unsupported characters in clone path: $clone" >&2; exit 1 ;;
esac
if [ "$root" = / ] && ! $dry_run && [ "$(id -u)" -ne 0 ]; then
  echo "error: run as root (or use --dry-run)" >&2
  exit 1
fi

case $(uname -s) in
  Darwin) claude_dir="Library/Application Support/ClaudeCode" ;;
  *) claude_dir=etc/claude-code ;;
esac
prefix=${root%/}

# Our files: the Claude drop-in is ours by name, the Codex files by their marker.
owned() {
  [ ! -e "$1" ] && [ ! -L "$1" ] && return 0
  [ -f "$1" ] && [ ! -L "$1" ] || return 1
  case $1 in *.json) return 0 ;; esac
  head -n 1 "$1" | grep -qF "$MARKER"
}

place() {  # template target
  target=$prefix/$2
  content=$(sed "s#@SKILLS_CLONE@#$clone#g" "$deploy/$1")
  unchanged=false
  if [ -f "$target" ] && [ "$(cat "$target")" = "$content" ]; then
    echo "unchanged: $target"
    unchanged=true
  else
    echo "write: $target"
  fi
  $dry_run && return
  mkdir -p "$(dirname "$target")"
  # Repair directories created by older installs as well as new ones. Only
  # change the client policy directories, not shared system or staging parents.
  chmod 0755 "$(dirname "$target")"
  case $2 in "$claude_dir/"*) chmod 0755 "$prefix/$claude_dir" ;; esac
  if $unchanged; then
    chmod 0644 "$target"
    return
  fi
  tmp=$(mktemp "$target.XXXXXX")
  printf '%s\n' "$content" > "$tmp"
  chmod 0644 "$tmp"
  mv -f "$tmp" "$target"
}

unplace() {  # target
  target=$prefix/$1
  [ -e "$target" ] || { echo "absent: $target"; return; }
  owned "$target" || { echo "skip: $target is not managed by this script"; return; }
  echo "remove: $target"
  $dry_run || rm -f "$target"
}

files="claude/50-clip-hpc.json:$claude_dir/managed-settings.d/50-clip-hpc.json
codex/config.toml:etc/codex/config.toml
codex/requirements.toml:etc/codex/requirements.toml"

# Check every target before changing anything, so a conflict leaves the host untouched.
if ! $remove; then
  echo "$files" | while IFS=: read -r template target; do
    owned "$prefix/$target" || { echo "error: $prefix/$target exists and is not managed by this script; merge deploy/$template by hand" >&2; exit 1; }
  done
fi

echo "$files" | while IFS=: read -r template target; do
  if $remove; then unplace "$target"; else place "$template" "$target"; fi
done

# Git checks the worktree for rev-parse, but local clone/upload-pack checks
# the .git directory. Both are administrator-owned and need explicit trust.
configure_git_trust() {
  for safe_path in "$clone" "$clone/.git"; do
    if $remove; then
      if git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$safe_path"; then
        echo "git: remove safe.directory $safe_path"
        $dry_run || git config --system --fixed-value --unset-all safe.directory "$safe_path"
      fi
    elif ! git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$safe_path"; then
      echo "git: add safe.directory $safe_path"
      $dry_run || git config --system --add safe.directory "$safe_path"
    fi
  done
}

if [ "$root" = / ] && command -v git >/dev/null; then
  configure_git_trust
fi

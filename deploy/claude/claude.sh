#!/bin/sh
# Managed by CLIP-HPC deploy/install.py.
set -eu

# Register each deployed snapshot once per user. Bootstrap costs about a second,
# so later launches skip it; a user who removes the plugin keeps it removed
# until the next deployment.
root=@MARKETPLACE_ROOT@
stamp="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/clip-hpc-snapshot"
if [ "$(cat "$stamp" 2>/dev/null || true)" != "$root" ]; then
  @CLAUDE_BIN@ plugin marketplace add "$root" >/dev/null
  @CLAUDE_BIN@ plugin install cbe@clip-hpc --scope user >/dev/null
  mkdir -p "$(dirname "$stamp")"
  printf '%s\n' "$root" > "$stamp"
fi

exec @CLAUDE_BIN@ "$@"

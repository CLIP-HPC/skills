#!/bin/sh
# Managed by CLIP-HPC deploy/install.py.
set -eu

# Install into the invoking user's CODEX_HOME, never root's shared state.
# Explicit source overrides keep bootstrap local even with an older user config.
@CODEX_BIN@ \
  -c 'marketplaces.clip-hpc.source_type="local"' \
  -c @MARKETPLACE_CONFIG@ \
  -c 'features.plugins=true' \
  plugin add cbe@clip-hpc >/dev/null

exec @CODEX_BIN@ "$@"

# Codex host configuration

`config.toml` makes the `clip-hpc` marketplace known to every Codex user on a
host and installs and enables the `cbe` plugin. Users no longer need to run
`codex plugin marketplace add` or `codex plugin add`.

It needs the Codex catalog `.agents/plugins/marketplace.json` on the
repository's default branch.

## Install

Codex reads one system file, `/etc/codex/config.toml`, and has no drop-in
directory. Merge the two tables into it, or copy the file if the host has none:

```bash
install -d -m 0755 /etc/codex
install -m 0644 deploy/codex/config.toml /etc/codex/config.toml   # only if absent
```

The system file sets defaults. A user can opt out with
`[plugins."cbe@clip-hpc"] enabled = false` in `~/.codex/config.toml`. To make the
settings mandatory, put the same tables in `/etc/codex/managed_config.toml`
instead; it takes precedence over user configuration.

## What happens for users

When a user's Codex session starts, Codex clones the marketplace into
`~/.codex/.tmp/marketplaces/clip-hpc` in the background and installs `cbe` into
`~/.codex/plugins/cache/clip-hpc/`. This happens before login is checked. Later
sessions fetch marketplace updates the same way. Each user needs `git` and
HTTPS access to github.com.

Until a user has started a session once, `codex plugin list` fails with
"marketplace root does not contain a supported manifest". Starting `codex` once
fixes it.

## Verify

As a regular user, start and quit `codex` once, then:

```bash
codex plugin list --marketplace clip-hpc   # cbe@clip-hpc: installed, enabled
```

## Remove

Delete the two tables from `/etc/codex/config.toml`. `codex plugin marketplace
remove` only edits user configuration and cannot remove a system entry.
Installed copies stay in each user's `~/.codex` until they remove them.

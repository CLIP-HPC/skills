# Claude Code host configuration

`50-clip-hpc.json` is a managed-settings drop-in that makes the `clip-hpc`
marketplace known to every Claude Code user on a host and enables the `cbe`
plugin. Users no longer need to run `marketplace add`.

## Install

On each host, for example the CBE.next login nodes:

```bash
install -d -m 0755 /etc/claude-code/managed-settings.d
install -m 0644 deploy/claude/50-clip-hpc.json /etc/claude-code/managed-settings.d/
```

Claude Code reads `/etc/claude-code/managed-settings.json` first, then every
`*.json` in `managed-settings.d/` in alphabetical order. A drop-in is used so
the file does not conflict with other managed settings on the host. Users
cannot override managed settings, but they can still turn the plugin off:
`enabledPlugins` is `true`, not `"force"`.

To make the plugin mandatory, set `"cbe@clip-hpc": "force"` (Claude Code
2.1.273 or later). Users would then be unable to disable it.

## Verify

As a regular user on the host, start `claude`, then run:

```text
/plugin marketplace list     # lists clip-hpc
/plugin                      # cbe@clip-hpc is installed and enabled
```

The marketplace is registered when a session starts. If `cbe` is listed but
not installed, run `/plugin install cbe@clip-hpc` once; it stays enabled
afterwards. Updates follow the marketplace: `/plugin marketplace update clip-hpc`.

## Remove

```bash
rm /etc/claude-code/managed-settings.d/50-clip-hpc.json
```

Plugins users already installed stay in their `~/.claude` until they remove them.

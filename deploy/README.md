# Host configuration

Configuration for shared hosts, such as the CBE.next login nodes, that makes the
`cbe` plugin available to every user without per-user setup:

- [`claude/`](claude/): Claude Code managed-settings drop-in.
- [`codex/`](codex/): Codex system configuration.

Both point at this repository's marketplace on GitHub, so users get plugin
updates when the default branch changes. Neither needs an API key, and neither
lists the internal `ops` plugin.

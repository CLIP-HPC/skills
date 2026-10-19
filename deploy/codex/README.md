# Managed Codex hosts

Deploy from a reviewed checkout on Linux or macOS. Install the approved Codex
binary separately; this setup is tested with Codex CLI **0.163.0** and requires
Python 3.10+ only on the deployment machine. Users need no Python or Git access.

```bash
# Example real binary location; use the path from your software deployment.
sudo python3 deploy/codex/install.py --codex-bin /opt/codex/bin/codex
```

Ensure `/usr/local/bin` precedes the real binary's directory on users' `PATH`.
The real binary must not resolve back to `/usr/local/bin/codex`. The installer
does not download Codex, change shell profiles, or run Codex as root.

For configuration-management packaging, stage the same layout without root:

```bash
python3 deploy/codex/install.py --codex-bin /opt/codex/bin/codex --destdir /tmp/codex-host
```

Deploy that tree at `/` with root ownership, readable files, and executable
directories and launcher. Paths inside the staged files refer to the final
host, not `/tmp/codex-host`.

## Installed layout and behavior

| Host path | Purpose |
|---|---|
| `/etc/codex/config.toml` | Local `clip-hpc` marketplace and enabled `cbe` defaults. |
| `/etc/codex/requirements.toml` | Enforce `check_for_update_on_startup = false` and `features.in_app_updates = false`. |
| `/usr/local/share/clip-hpc/codex/<content hash>/` | Immutable snapshot of the common Codex catalog and public `cbe` package. |
| `/usr/local/bin/codex` | Install `cbe@clip-hpc` into the invoking user's cache, then execute the real Codex binary with the original arguments. |

The launcher uses `codex plugin add` from the deployed local source on each
invocation. This installs all six skills for a fresh user and refreshes existing
copies after an administrator deploys a new snapshot. An enabled config entry
alone does not populate a new user's plugin cache in CLI 0.163.0. Bootstrap uses
explicit local-source overrides, so an older user marketplace setting cannot
redirect that installation to GitHub. A bootstrap failure stops the launcher
and prints Codex's error. User config must be writable, as with a manual plugin
installation. `CODEX_HOME`, authentication, and arguments retain their normal
Codex meanings.

The catalog remains the repository's generated catalog. Only `cbe` is installed
automatically. No credentials or repository maintenance instructions are copied.
The launcher serves CLI users; a desktop app launched directly does not run it.
Desktop users need a separate user plugin-installation step with the same local
catalog. The system update requirements apply to supported desktop clients too.

## Updates and existing configuration

CLI startup update checks are enforced off. The desktop client's built-in
updater is disabled on supported builds after restart. Package managers, MDM,
and manual `codex update` remain separate: deploy approved Codex versions through
your existing software management. See the official
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
[managed configuration](https://learn.chatgpt.com/docs/enterprise/managed-configuration),
and [app update controls](https://learn.chatgpt.com/docs/enterprise/manage-app-updates).

Skill updates require explicitly rerunning the installer from a reviewed
checkout. It creates a new snapshot when content changes; it never polls GitHub.
Keep previous snapshots for rollback, then remove them through your deployment
tool after active sessions finish using them. Roll back by deploying the old
checkout and restarting Codex.

Rerunning this installer replaces its own config files and launcher. It refuses
to overwrite existing files without its ownership comment, including symlinks.
On an already managed host, merge these TOML settings into the existing policy
and deploy the launcher/catalog using your configuration manager instead.
Higher-priority workspace or MDM requirements can affect the effective policy.
The marketplace and plugin entries in system `config.toml` are defaults; users
can override them under normal Codex configuration precedence.

## Verify

As an ordinary user, from outside this checkout:

```bash
command -v codex  # /usr/local/bin/codex
codex plugin marketplace list
codex plugin list --marketplace clip-hpc --json
codex
```

Confirm that `cbe@clip-hpc` is installed and enabled and that `/skills` lists
the six CBE skills. On supported desktop clients, fully restart the app and
verify the managed update indicator in Settings. Validate the effective
requirements on a target host, including any workspace and MDM policy layers.

For an isolated launcher and installation check using the real CLI:

```bash
python3 deploy/codex/smoke-test.py
```

# Managed hosts

Make the `cbe` plugin available to every Claude Code and Codex user on shared
Unix hosts, such as the CBE.next login nodes, and keep client updates under
central control. Deploy from a reviewed checkout on Linux or macOS. Python 3.10+
is needed only on the deployment machine. Users need no Python, Git, or GitHub
access.

Install the approved client binaries separately. This setup is tested with
Claude Code **2.1.292** and Codex CLI **0.163.0**.

```bash
# Example real binary locations; use the paths from your software deployment.
sudo python3 deploy/install.py \
  --claude-bin /opt/claude/bin/claude \
  --codex-bin /opt/codex/bin/codex
```

Pass only one of `--claude-bin` and `--codex-bin` to deploy a single client.
Ensure `/usr/local/bin` comes before the real binaries' directories on users'
`PATH`, and that neither real binary resolves back to a `/usr/local/bin`
launcher. The installer does not download clients, change shell profiles, or
run a client as root.

For configuration-management packaging, stage the same layout without root:

```bash
python3 deploy/install.py --claude-bin /opt/claude/bin/claude \
  --codex-bin /opt/codex/bin/codex --destdir /tmp/clip-hpc-host
```

Deploy that tree at `/` with root ownership, readable files, and executable
directories and launchers. Paths inside the staged files refer to the final
host, not `/tmp/clip-hpc-host`. The Claude Code managed-settings directory
defaults to `/etc/claude-code`, or `/Library/Application Support/ClaudeCode`
when staging on macOS. Use `--claude-managed-dir` when staging for another
platform.

## Installed layout

| Host path | Purpose |
|---|---|
| `/usr/local/share/clip-hpc/<content hash>/` | Immutable snapshot of both generated catalogs and the public `cbe` package, shared by both clients. |
| `/etc/claude-code/managed-settings.d/50-clip-hpc.json` | Declare the local `clip-hpc` marketplace, enable `cbe`, and set `DISABLE_AUTOUPDATER`. |
| `/usr/local/bin/claude` | Register the snapshot and install `cbe@clip-hpc` for the invoking user, then run the real Claude Code binary. |
| `/etc/codex/config.toml` | Local `clip-hpc` marketplace and enabled `cbe` defaults. |
| `/etc/codex/requirements.toml` | Enforce `check_for_update_on_startup = false` and `features.in_app_updates = false`. |
| `/usr/local/bin/codex` | Install `cbe@clip-hpc` for the invoking user, then run the real Codex binary. |

Each launcher keeps the original arguments, and the client's usual
configuration directory (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`) and authentication.
If installation fails, the launcher stops and prints the client's error. User
configuration must be writable, as with a manual plugin installation. Only
`cbe` is installed automatically. No credentials or repository maintenance
instructions are copied.

Neither client installs a plugin from a locally declared marketplace on its
own: Codex CLI 0.163.0 does not populate a new user's plugin cache from an
enabled config entry, and Claude Code 2.1.292 registers settings-declared
marketplaces only when an interactive session starts. The launchers close that
gap for CLI users.

### Claude Code

On the first launch after each deployment, the launcher runs `claude plugin
marketplace add <snapshot>` and `claude plugin install cbe@clip-hpc`, then
records the snapshot in `~/.claude/plugins/clip-hpc-snapshot`. Later launches
skip this step, which takes about a second. Claude Code loads a directory
marketplace in place, so a new snapshot takes effect for every user at their
next launch. A user who uninstalls or disables `cbe` keeps it that way until
the next deployment; `"cbe@clip-hpc": "force"` in the drop-in makes it
mandatory.

`marketplace add` also records the marketplace in the user's
`~/.claude/settings.json`. The managed drop-in declares the same snapshot, so
IDE and desktop sessions, which bypass the launcher, should also register it
when they start. This is not yet verified.

Managed settings cannot be overridden by users. `DISABLE_AUTOUPDATER` stops
background updates. A manual `claude update` stays possible; deploy approved
versions through your software management. See the official
[managed settings](https://code.claude.com/docs/en/managed-settings),
[settings](https://code.claude.com/docs/en/settings), and
[marketplace](https://code.claude.com/docs/en/plugins/marketplace-reference)
documentation.

### Codex

The launcher runs `codex plugin add` from the deployed snapshot on every
invocation, which takes well under a second. This installs all six skills for
a new user and refreshes existing copies after a new deployment. Explicit
local-source overrides make sure an older user marketplace setting cannot
redirect the installation to GitHub.

The desktop app does not run the launcher. Desktop users need a separate
plugin installation from the same local catalog. The system update
requirements also apply to supported desktop clients: their built-in updater
is disabled after a restart. Package managers, MDM, and manual `codex update`
stay separate: deploy approved Codex versions through your software
management. The marketplace and plugin entries in system `config.toml` are
defaults that users can override under normal Codex configuration precedence.
See the official
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
[managed configuration](https://learn.chatgpt.com/docs/enterprise/managed-configuration),
and [app update controls](https://learn.chatgpt.com/docs/enterprise/manage-app-updates).

## Updates and rollback

To update the skills, rerun the installer from a reviewed checkout. It creates
a new snapshot only when content changes, and it never polls GitHub. Keep
previous snapshots for rollback, and remove them through your deployment tool
after active sessions stop using them. To roll back, deploy the old checkout
and restart the clients.

Home directories are usually shared between hosts. Deploy the same checkout to
every host that runs the clients, including compute nodes where users start
them. Otherwise a user switching hosts alternates between snapshots, or ends
up with a plugin path that does not exist.

Rerunning the installer replaces its own launchers and Codex files, which are
recognised by their ownership comment, and its Claude drop-in, recognised by
its file name. It refuses to overwrite any other existing file or a symlink.
On an already managed host, merge these settings into the existing policy and
deploy the snapshot and launchers with your configuration manager instead.
Higher-priority workspace or MDM policy can change the effective settings.

## Verify

As an ordinary user, from outside this checkout:

```bash
command -v claude codex                     # both in /usr/local/bin
claude plugin list                          # cbe@clip-hpc enabled, read from the snapshot
codex plugin list --marketplace clip-hpc --json
```

Start each client and check that the six CBE skills are available: `/skills`
in Codex, and the skill list in Claude Code. On supported Codex desktop
clients, fully restart the app and check the managed update indicator in
Settings. Check the effective policy on a target host, including any workspace
and MDM layers.

To check both launchers with the real CLIs, in isolated temporary state:

```bash
python3 deploy/smoke-test.py
```

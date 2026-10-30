# Managed hosts

Make the `cbe` plugin available to every Claude Code and Codex user on shared
Unix hosts, such as the CBE.next nodes, and keep client updates under central
control. Users need no setup, Python, or GitHub account.

Both clients install `cbe` from this repository on GitHub, at a branch or tag
you choose, and keep it up to date from there. Hosts following `latest` receive
published releases; hosts following `main` receive merged changes. Each host
needs `git` and HTTPS access to `github.com`.

Per-host configuration in `/etc` is written once per host by
`deploy/install-host.sh`. Install the approved client binaries separately.
Tested with Claude Code **2.1.304** and Codex CLI **0.163.0**.

## Host configuration

Run the installer as root on each host, from any checkout of this repository.
Your configuration management can do this, or you can run it by hand on a node:

```bash
deploy/install-host.sh --dry-run          # show what would change
deploy/install-host.sh                    # install or update, following main
deploy/install-host.sh --version latest   # follow published releases
deploy/install-host.sh --version cbe-v0.7.1 # pin a specific release
deploy/install-host.sh --remove           # uninstall
```

`--version` names the Git branch or tag that both clients install from. It
defaults to `main`. It writes:

| Host path | Template |
|---|---|
| `/etc/claude-code/managed-settings.d/50-clip-hpc.json` | `deploy/claude/50-clip-hpc.json` |
| `/etc/codex/config.toml` | `deploy/codex/config.toml` |
| `/etc/codex/requirements.toml` | `deploy/codex/requirements.toml` |

Rerunning it is safe: files with the same content are not rewritten. It repairs
managed file permissions to `0644` and client policy directories to `0755`,
including when root uses a private umask. `--dry-run` does not change permissions.
It replaces only its own files: the Claude drop-in by its name, and the Codex files by
their first-line marker. If another file is already at one of these paths, it
stops before changing anything. Merge the template by hand in that case; Codex
has no drop-in directory. `--remove` deletes only its own files. `--root DIR`
writes below a staging directory instead of `/`, for image builds and tests.
On macOS, the Claude Code managed directory is
`/Library/Application Support/ClaudeCode`.

Earlier versions of the installer served the plugin from a shared clone and
added it to `safe.directory` in the system Git configuration. Running the
installer from that clone removes those two entries.

### Claude Code

`managed-settings.d/50-clip-hpc.json` registers `CLIP-HPC/skills` at the chosen
ref as the `clip-hpc` GitHub marketplace and enables `cbe`. Claude Code installs
managed plugins at the start of each user's next session
([docs](https://code.claude.com/docs/en/plugins/org)) and keeps a copy in each
user's `~/.claude`.

`autoUpdate` refreshes the marketplace in the background during a session.
Claude Code installs a new copy only when the version in
`plugins/cbe/plugin.json` changes, so commits without a version bump don't
reach users. The update loads at the next session or after `/reload-plugins`.

The `env` block sets `DISABLE_UPDATES` and `DISABLE_AUTOUPDATER`, so Claude Code
itself is not updated on the host. Those variables also stop plugin updates, so
`FORCE_AUTOUPDATE_PLUGINS` turns plugin updates back on. It applies to every
marketplace with auto-update on, including Anthropic's official one if a user
adds it. `CLAUDE_CODE_PLUGIN_PREFER_HTTPS` clones over HTTPS, because users have
no GitHub SSH keys; without it, background updates fail. Users cannot override
managed settings, and the managed `enabledPlugins` entry keeps `cbe` loaded
even if a user disables it in their own settings.

See [managed settings](https://code.claude.com/docs/en/managed-settings) and
[plugin loading](https://code.claude.com/docs/en/plugins/loading).

### Codex

`config.toml` declares `https://github.com/CLIP-HPC/skills.git` at the chosen
ref as a `git` marketplace and enables `cbe`. At startup, Codex fetches the ref,
then installs `cbe` into the user's `~/.codex` when it is missing or has
changed (about 1 MB per user). Only `git` sources install automatically; a
`local` marketplace source would require each user to run `codex plugin add`.

These entries are defaults that users can override in `~/.codex/config.toml`.
`requirements.toml` enforces that update checks stay off, including the
desktop app's built-in updater after a restart. Package managers, MDM, and
manual `codex update` are separate: deploy approved versions through your
software management. See
[managed configuration](https://learn.chatgpt.com/docs/enterprise/managed-configuration)
and [app update controls](https://learn.chatgpt.com/docs/enterprise/manage-app-updates).

## Updates and rollback

Use `--version latest` to follow published releases. The release workflow moves
that tag forward after a non-prerelease is published and its manifest version
is checked. It is shared by `cbe` and `grid`, so either plugin's release can
advance it. Never move `latest` by hand.

The installer still defaults to `main`, which includes changes before a release
is published. Hosts following that branch can receive a bumped plugin version
as soon as it is merged. For either moving ref, Claude Code updates during or
after the next session, and Codex at its next start.

To control the rollout manually, install with `--version cbe-v<version>` and
rerun the installer with the next release tag. Roll back the same way with a
known previous tag, then restart both clients and verify the installed version.
Reapply `--version latest` to resume automatic release tracking.

## Migrate an existing Linux host

Use a current checkout for the installer; each user's client fetches the plugin
from GitHub independently. The installer does not require a shared plugin clone
to remain on the host after migration. Keep the approved client binaries and
the current policy disabling client self-updates.

1. Record the old shared-checkout path and back up the three host configuration
   files before replacing or merging them. In a root shell:

   ```sh
   backup=$(mktemp -d /root/clip-hpc-config.XXXXXX)
   for file in /etc/claude-code/managed-settings.d/50-clip-hpc.json \
               /etc/codex/config.toml /etc/codex/requirements.toml; do
     if [ -f "$file" ]; then
       mkdir -p "$backup$(dirname "$file")"
       cp -p "$file" "$backup$file"
     fi
   done
   printf 'Configuration backup: %s\n' "$backup"
   ```

2. From the checkout, preview and apply the release configuration:

   ```sh
   sudo deploy/install-host.sh --version latest --dry-run
   sudo deploy/install-host.sh --version latest
   ```

   The preview reports files to write; inspect the templates as well. If the
   installer reports an unmanaged Codex file, merge the corresponding template
   into it manually, replacing `@SKILLS_REF@` with `latest`. Preserve unrelated
   settings and do not add the ownership marker to a file you manage yourself.
   In that case, merge all three templates manually: the installer checks all
   targets before writing any of them and will continue to refuse unmanaged
   Codex files. To render the templates without touching `/etc`, run
   `deploy/install-host.sh --version latest --root "$(mktemp -d)"` as an ordinary
   user and use the files under the reported staging path.

3. Confirm the Claude marketplace source is `github`, repository
   `CLIP-HPC/skills`, ref `latest`, with `autoUpdate` on. Confirm the Codex
   marketplace source is `git`, URL `https://github.com/CLIP-HPC/skills.git`,
   ref `latest`. Both must enable `cbe@clip-hpc`. These are the values rendered
   from the templates listed above.

4. Check existing users' configuration for old filesystem marketplace entries.
   Codex user configuration, including a custom `CODEX_HOME`, can override the
   system defaults: migrate the `marketplaces.clip-hpc` entry to the Git source
   above, removing obsolete local-source fields, or remove that entry to inherit
   the system default. Check for an explicit user override disabling CBE too.
   For Claude, check the effective marketplace source after the first launch
   under the new managed settings. Preserve unrelated marketplaces, plugins,
   and preferences; do not delete users' entire client directories.

5. Verify with both a fresh ordinary user and an existing user who used the old
   marketplace, as described below. Confirm the source and installed version as
   well as the enabled status. Keep the old checkout until both clients load
   CBE successfully from GitHub.

6. Check `git config --system --get-all safe.directory` for obsolete trust of
   the old checkout and its `.git` directory. Running the installer from that
   same path removes those two entries automatically. If it ran elsewhere,
   remove only those exact old entries with
   `sudo git config --system --fixed-value --unset-all safe.directory PATH`,
   once for each recorded path that is present. Preserve other trust entries.

After the next published CBE release, start both clients again and verify the
new installed version and skills. This checks automatic updates on the actual
host; rendering templates and running installer tests alone cannot establish
that client fetching and cache refresh work there. No cron job is needed for
the plugin checkout.

## Verify

As an ordinary user on a configured host, start each client once, then:

```bash
claude plugin list                          # cbe@clip-hpc enabled
codex plugin list --marketplace clip-hpc    # cbe@clip-hpc installed and enabled
```

Check that the nine CBE skills are available in a session. Check the effective
policy on a target host as well, including any workspace or MDM layers.

The marketplace also lists `grid@clip-hpc`, for the grid experiment groups. The
host configuration doesn't enable it; users who need it install it themselves
with `claude plugin install grid@clip-hpc` or `codex plugin add grid@clip-hpc`.

## Alternative: admin skill directories

Both clients also read skills from an administrator directory, without a
plugin, per-user state, or opt-out:

- Codex: `/etc/codex/skills/<skill>/`
- Claude Code: `.claude/skills/<skill>/` in the managed settings directory,
  that is `/etc/claude-code/.claude/skills/<skill>/` on Linux

Symlink each `plugins/cbe/skills/<skill>` from a checkout there. Skills then
appear without the `cbe:` prefix, and every change to the checkout is live
immediately, but nothing updates the checkout for you. This path doesn't
include the `/groups` hook and hasn't been tested with this repository yet.

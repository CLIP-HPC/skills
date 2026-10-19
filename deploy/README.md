# Managed hosts

Make the `cbe` plugin available to every Claude Code and Codex user on shared
Unix hosts, such as the CBE.next nodes, and keep client updates under central
control. Users need no setup, Python, or GitHub access.

The setup has two parts:

- **A shared clone** of this repository on a filesystem that all hosts mount.
  Check out a reviewed tag or commit; that checkout is what users get.
- **Per-host configuration** in `/etc`, written once by your configuration
  management. It points both clients at the shared clone and contains no
  version, so skill updates never touch `/etc`.

Install the approved client binaries separately. Tested with Claude Code
**2.1.292** and Codex CLI **0.163.0**.

## Shared clone

```bash
git clone https://github.com/CLIP-HPC/skills.git "$CLONE"   # e.g. under /software
git -C "$CLONE" checkout <reviewed tag or commit>
```

Keep it readable by all users and writable only by administrators.

## Host configuration

Replace `@SKILLS_CLONE@` in the templates with the clone's absolute path:

```bash
CLONE=/path/to/shared/skills
sed "s#@SKILLS_CLONE@#$CLONE#" deploy/claude/50-clip-hpc.json \
  > /etc/claude-code/managed-settings.d/50-clip-hpc.json
sed "s#@SKILLS_CLONE@#$CLONE#" deploy/codex/config.toml > /etc/codex/config.toml
cp deploy/codex/requirements.toml /etc/codex/requirements.toml
```

If the host already has `/etc/codex/config.toml` or `requirements.toml`,
merge the tables instead of copying. Codex has no drop-in directory. On macOS,
the Claude Code managed directory is `/Library/Application Support/ClaudeCode`.

### Claude Code

`managed-settings.d/50-clip-hpc.json` registers the shared clone as the
`clip-hpc` directory marketplace and enables `cbe`. Claude Code installs managed
plugins at the start of each user's next session
([docs](https://code.claude.com/docs/en/plugins/org)), and loads plugins from
a directory marketplace in place, so it reads the skills from the shared clone.
Each user's `~/.claude` gets the registration and a small cached copy.

The `env` block sets `DISABLE_UPDATES` and `DISABLE_AUTOUPDATER`, so no session
on the host tries to update the shared installation. Users cannot override
managed settings. They can still disable `cbe`; set
`"cbe@clip-hpc": "force"` to prevent that.

See [managed settings](https://code.claude.com/docs/en/managed-settings) and
[plugin loading](https://code.claude.com/docs/en/plugins/loading).

### Codex

`config.toml` declares the shared clone as a `git` marketplace and enables
`cbe`. At startup, Codex compares the clone's revision with its own copy, then
clones it and installs `cbe` into the user's `~/.codex` when it is missing or
has changed (about 1 MB per user). This needs `git` on the host, but no network
access. Only `git` sources install automatically; a `local` marketplace source
would require each user to run `codex plugin add`.

These entries are defaults that users can override in `~/.codex/config.toml`.
`requirements.toml` enforces that update checks stay off, including the
desktop app's built-in updater after a restart. Package managers, MDM, and
manual `codex update` are separate: deploy approved versions through your
software management. See
[managed configuration](https://learn.chatgpt.com/docs/enterprise/managed-configuration)
and [app update controls](https://learn.chatgpt.com/docs/enterprise/manage-app-updates).

Users clone from a repository owned by another account. If Git refuses with
"detected dubious ownership", trust the clone system-wide:

```bash
git config --system --add safe.directory "$CLONE"
```

## Updates and rollback

Update the shared clone, for example `git -C "$CLONE" checkout <next tag>`.
Claude Code picks up the change at each user's next session. Codex picks it up
at the next start, when it sees the new revision. Roll back the same way, by
checking out the previous tag. Changes reach running Claude sessions as files
are read, so prefer switching tags over editing files in the clone.

## Verify

As an ordinary user on a configured host, start each client once, then:

```bash
claude plugin list                          # cbe@clip-hpc enabled, read from $CLONE
codex plugin list --marketplace clip-hpc    # cbe@clip-hpc installed and enabled
```

Check that the six CBE skills are available in a session. Check the effective
policy on a target host as well, including any workspace or MDM layers.

## Alternative: admin skill directories

Both clients also read skills from an administrator directory, without a
plugin, per-user state, or opt-out:

- Codex: `/etc/codex/skills/<skill>/`
- Claude Code: `.claude/skills/<skill>/` in the managed settings directory,
  that is `/etc/claude-code/.claude/skills/<skill>/` on Linux

Symlink each `"$CLONE"/plugins/cbe/skills/<skill>` there. Skills then appear
without the `cbe:` prefix, and every change to the clone is live immediately.
Neither path has been tested with this repository yet.

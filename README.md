# CLIP-HPC agent skills

Shared Agent Skills for CBE.next, the Vienna BioCenter HPC cluster, distributed
as the `cbe` plugin in the `clip-hpc` marketplace. The same nine skill folders
work in Codex and Claude Code.

The canonical manifest is [`plugins/cbe/plugin.json`](plugins/cbe/plugin.json),
using the [Agent Plugins 1.0.0 format](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json).
Host discovery files are generated and committed, so users can install directly
from Git without Python, uv, or a build step.

[`AGENTS.md`](AGENTS.md) contains instructions for agents maintaining this repo.
It is outside the `plugins/cbe` package and the individual skill directories,
so plugin and standalone-skill installation do not distribute it.

## Skills

Install the complete plugin: these skills refer to each other by name.

| Skill | Use it to |
|---|---|
| `cbe-next` | Connect, follow cluster rules, pick partitions and GPUs, and write batch scripts. Start here. |
| `cbe-software` | Find, load, or install software: modules, containers, `uv`, conda, licensed software. |
| `cbe-python` | Set up and maintain reproducible uv and conda environments tracked in git. |
| `cbe-data` | Choose filesystems, restore files, and move data on and off the cluster. |
| `cbe-tuning` | Make jobs faster or request resources that match what they use. |
| `cbe-queue` | Understand why a job waits: priority, fair share, backfill, and start order. |
| `cbe-triage` | Find out why a job failed. |
| `cbe-ticket` | Write and open a complete support ticket for CBE.next or OpenOnDemand. |
| `cbe-migrate` | Port job scripts, data, and environments from legacy CBE before its 2026-12-18 shutdown. |

The instructions follow the [CBE.next documentation](https://docs.vbc.ac.at/research-computing/cbe/).
Executing cluster commands requires the user's existing SSH access and a valid
certificate. The plugin itself needs no API key or MCP server. Ticket creation
can use an available Atlassian integration; without one, the skills provide
text for the support portal.

## Install in Codex

Using Codex CLI 0.163.0, the version checked by CI:

```bash
codex plugin marketplace add CLIP-HPC/skills
codex plugin add cbe@clip-hpc
```

For an unpublished checkout, run `codex plugin marketplace add .` from its root
instead of adding the GitHub repository, then install `cbe@clip-hpc`.
The repo marketplace is also available as a local source in supported desktop
clients; restart the app if the source has not appeared.

In Codex, select the skill using `$` or `/skills`, or ask naturally:

```text
Use the cbe-next skill to adapt this sbatch script for CBE.next.
```

Refresh the marketplace after a release:

```bash
codex plugin marketplace upgrade clip-hpc
codex plugin add cbe@clip-hpc
```

See [OpenAI's plugin packaging and marketplace documentation](https://developers.openai.com/plugins/build/plugins).


## Install in Claude Code

```bash
claude plugin marketplace add CLIP-HPC/skills
claude plugin install cbe@clip-hpc
```

Inside a Claude Code session, use `/plugin marketplace add CLIP-HPC/skills`
and `/plugin install cbe@clip-hpc` instead. Invoke a skill with
`/cbe:cbe-next`, or ask naturally for help with a CBE.next task.

For local development, use `claude --plugin-dir ./plugins/cbe` from this checkout.

```bash
claude plugin marketplace update clip-hpc
claude plugin update cbe@clip-hpc
```

In Claude Code, the plugin also adds a hook that asks before Bash commands that
delete, move, or overwrite files under `/groups`. It runs only where `/groups`
exists and uses `python3` from `PATH`. Set `CBE_GROUPS_GUARD=off` to disable it,
or `CBE_PROTECTED_PATHS` to a colon-separated list of other roots to protect.
Codex and the skill-only installation don't include the hook.

## Managed hosts

To enable `cbe` for every Claude Code and Codex user on shared Unix hosts, such
as the CBE.next nodes, installed from this repository on GitHub with client
updates under central control, see [`deploy/`](deploy/README.md).

## Why generated compatibility files?

The schema URL identifies a file format; it is not a plugin discovery directory.
Codex supports the portable root `plugin.json`. Claude Code's documented manifest
location is still `.claude-plugin/plugin.json`, and its marketplace location is
`.claude-plugin/marketplace.json`. It can load standard components without a
manifest, but that does not make it read the portable manifest's identity and
version metadata.

We therefore maintain one portable plugin manifest, one small source catalog,
and one copy of each skill. Both host catalogs expose the same plugins and
sources. `scripts/bundle.py` generates the host adapters:

| Edit this source | Generated output |
|---|---|
| `plugins/cbe/plugin.json` | `plugins/cbe/.claude-plugin/plugin.json` |
| `marketplace.json` plus portable plugin metadata | `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json` |
| Each skill's frontmatter `metadata` | Its `agents/openai.yaml` picker labels and example prompt |

Root `marketplace.json` is this repository's authoring catalog, not a claim of
a portable marketplace standard. Only the generated catalogs are read by hosts.
There is no separate `.codex-plugin/plugin.json`, duplicated skill content,
or per-user configuration checked into this repository. Automatic skill
selection retains each host's default behavior.

For direct Git deployment, commit generated adapters with their source changes.
Consumers do not regenerate them. CI fails when any adapter is missing or stale;
it does not push regenerated commits. Require the validation checks on the branch
or commit used for deployment. Repository agents follow `AGENTS.md` to regenerate
the adapters as part of each source change.

References: [OpenAI plugin structure](https://developers.openai.com/plugins/build/plugins#plugin-structure),
[Claude manifest reference](https://code.claude.com/docs/en/plugins-reference),
and [Claude marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference).

## Use standalone skills

When a plugin install is unsuitable, link all nine folders into a host's skill
directory. The helper needs only Python 3.10+ and never replaces existing files.

```bash
# Codex: personal skills, available across projects.
python3 scripts/install-skills.py --destination ~/.agents/skills

# Codex: skills for a consuming project.
python3 scripts/install-skills.py --destination /path/to/project/.agents/skills

# Claude Code: personal skills using the same shared source folders.
python3 scripts/install-skills.py --destination ~/.claude/skills
```

Choose either plugin installation or standalone links in a given host to avoid
duplicate skills. Keep this checkout at its current path while links point to
it. To remove a standalone installation, remove only the nine links the helper
created. No other files need changing.

For a host that accepts uploaded Agent Skills, the existing helper builds one
archive per skill:

```bash
scripts/package-skills.sh                 # all nine into dist/
scripts/package-skills.sh cbe-triage      # one skill
```

## Develop and validate

Maintainers need [uv](https://docs.astral.sh/uv/) and Python 3.10+. Dependencies
are locked in `uv.lock`; they are not runtime requirements for the skills.

1. Edit `plugins/cbe/skills/<skill>/SKILL.md`. Discovery descriptions decide when
   a client loads a skill: keep the identifiers users paste or type (host and node
   names, partitions, QOS names, paths, tool names) and say which sibling skill
   handles adjacent requests. Place picker labels, the short description, and a
   neutral example task in its frontmatter `metadata`.
2. For a release, bump `version` in `plugins/cbe/plugin.json`. Change catalog
   membership in root `marketplace.json`.
3. Generate and validate:

   ```bash
   uv run --locked python scripts/bundle.py
   uv run --locked python scripts/validate.py
   uv run --locked python -m unittest discover -s tests -v
   ```

4. With Codex CLI 0.163.0 and Claude Code 2.1.292 installed, run:

   ```bash
   uv run --locked python scripts/smoke-test.py
   ```

   This validates the Claude marketplace and plugin manifests, then installs the
   plugin in both clients using isolated temporary state. The Codex package omits
   the Claude manifest. It verifies all nine installed skills and their picker metadata.
   It does not call a model, submit cluster jobs, or change your installed plugins.
5. When changing descriptions or workflow instructions, run the Claude Code eval
   suite in `plugins/cbe/evals/`. It calls a model on your own Claude account, so
   it costs money and is not part of CI:

   ```bash
   claude plugin eval plugins/cbe --judge-model sonnet --no-publish
   ```

   Each case checks that the expected skill loads (reported, not scored) and that
   the answer has the expected substance, with and without the plugin; the
   headline number is the difference. The `neg` cases check that no CBE skill loads
   for unrelated prompts. Run the [manual behavior scenarios](tests/scenarios.md)
   in Codex, which has no equivalent runner. Commit generated outputs with their sources.

CI checks schemas, names, relative resource links, metadata, generated-file drift,
archive contents, and regression tests on Linux and macOS. A separate job runs
the CLI compatibility smoke test without credentials, against the pinned versions
above and, without blocking merges, the latest releases; it also runs weekly.
Claude's `plugin validate` does not check `SKILL.md` frontmatter, so
`scripts/validate.py` is the check for skill names and descriptions in both clients. The published
Agent Plugins schema is vendored under `schemas/` so schema validation is offline.
No workflow publishes releases or changes your client configuration. When a
release is published, the release workflow checks its tag against the manifest
version and moves the tag `latest` to the newest release.

This public bundle supports regular use of CBE / CLIP. Internal staff tooling
is separate and is not required to install or use these skills. Keep facts to
what the public documentation states.

The skills state facts from the CBE.next pages on docs.vbc.ac.at (source: the
`newdocs` repository). Until the CBE.next release, the authoritative source is
the `main` branch of `newdocs`, which has changes not yet on the live site. When
those pages change, update the skills and bump the version.

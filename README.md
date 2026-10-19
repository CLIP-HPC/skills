# CLIP-HPC agent skills

Agent skills for CBE.next, the Vienna BioCenter HPC cluster, packaged as a Claude Code plugin marketplace (`clip-hpc`).

The skills teach an agent how to connect to CBE.next, submit and tune Slurm jobs, find software, handle data, triage failed jobs, and port workloads from legacy CBE. They follow the [CBE.next documentation](https://docs.vbc.ac.at/research-computing/cbe/).

## Skills

The `cbe` plugin contains six skills that refer to each other by name:

| Skill | Use it to |
|---|---|
| `cbe-next` | Connect, follow the cluster rules, pick partitions and GPUs, and write batch scripts. Start here. |
| `cbe-software` | Find, load, or install software: modules, containers, `uv`, conda, licensed software. |
| `cbe-data` | Choose filesystems, restore files, and move data on and off the cluster. |
| `cbe-tuning` | Make jobs faster or request resources that match what they use. |
| `cbe-triage` | Find out why a job failed and draft a support ticket. |
| `cbe-migrate` | Port job scripts, data, and environments from legacy CBE before it shuts down on 2026-12-18. |

## Install in Claude Code

```bash
claude plugin marketplace add CLIP-HPC/skills
claude plugin install cbe@clip-hpc
```

Inside a Claude Code session, use `/plugin marketplace add CLIP-HPC/skills` and `/plugin install cbe@clip-hpc` instead.

HPC support and operations staff also install the `ops` plugin. It is listed in this marketplace but installs from the internal `CLIP-HPC/operator-skills` repository, so it only works with GitHub access to that repository:

```bash
claude plugin install ops@clip-hpc
```

Update later with:

```bash
claude plugin marketplace update clip-hpc
```

## Use on claude.ai

Organization and personal skills on claude.ai are uploaded as one `.zip` per skill:

```bash
scripts/package-skills.sh                 # all six skills into dist/
scripts/package-skills.sh cbe-triage      # a single skill
```

## Layout

```text
.claude-plugin/marketplace.json           # marketplace catalogue
plugins/cbe/.claude-plugin/plugin.json
plugins/cbe/skills/<skill>/SKILL.md
scripts/package-skills.sh                 # zip skills for claude.ai upload
```

## Change a skill

1. Edit `plugins/cbe/skills/<skill>/SKILL.md`.
2. Bump `version` in `plugins/cbe/.claude-plugin/plugin.json`. Installed copies only update when the version changes.
3. Validate:

   ```bash
   claude plugin validate .
   claude plugin validate plugins/cbe
   ```

4. Commit with a COPS or RFC prefix where one applies, for example `COPS-239: agent: ...`.

This repository is public. Keep facts to what the public documentation states. Support and operations material belongs in the internal `CLIP-HPC/operator-skills` repository, which the `ops` entry in this marketplace points to.

The skills state facts from the CBE.next pages on docs.vbc.ac.at (source: the `newdocs` repository). Until the CBE.next release, the authoritative source is the `review/final-state` branch of `newdocs`, not `main` or the live site. When those pages change, update the skills and bump the version.

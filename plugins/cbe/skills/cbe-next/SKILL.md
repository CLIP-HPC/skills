---
name: cbe-next
description: How to work on CBE.next, the Vienna BioCenter HPC cluster (SSH alias cbe.next, login atlas.cbenext.vbc.ac.at, nodes cbe-c3-*/cbe-g5-*/cbe-m3-*). Covers Slurm sbatch/salloc/srun and job arrays, partitions c, g, and m, Slurm accounts, NVIDIA B200 GPUs and MIG slices, modules (EESSI and CBE stacks), Apptainer containers, uv Python environments, storage ($HOME, /scratch, $SCRATCHDIR, /groups, /resources, /clustertmp), data transfer, and OpenOnDemand. Use whenever connecting to, submitting jobs on, installing software on, or moving data to or from CBE.next.
---

# CBE.next

Facts below reflect the CBE.next docs as of 2026-10-19. Values marked *not configured yet* may have changed; prefer what the cluster reports (`sinfo`, `showuserlimits`, `module spider`).

Legacy CBE is a different system that shuts down on 2026-12-18. You can recognise it by the hostnames `cbe.vbc.ac.at`, `clip-login-0/1.cbe.vbc.ac.at`, and `clip-*` compute nodes, and by the `/scratch-cbe` path. Don't apply its instructions here. Watch out for `/scratch`: on legacy CBE it was the 30-day exchange area that is now `/clustertmp`, while on CBE.next `/scratch` is the job scratch (`$SCRATCHDIR`).

## Access

- SSH alias `cbe.next` points to `atlas.cbenext.vbc.ac.at`. From outside the campus, go through the jump host `sshjump.vbc.ac.at` (`ssh -J sshjump.vbc.ac.at atlas.cbenext.vbc.ac.at`).
- Authentication uses a 16-hour SSH certificate held in the user's `ssh-agent`. If SSH fails with an auth error, ask the user to run `step ssh login vbc-cbe` (unmanaged devices: `step ssh login --provisioner=VBC_user vbc-cbe`). You can't renew it yourself.
- If SSH asks to accept a host key, stop and don't accept it. Tell the user to report it in the CBE.next MS Teams channel.
- Browser access: OpenOnDemand at https://ood.atlas.cbenext.vbc.ac.at/ offers Jupyter, RStudio Server, code-server, and a Remote Desktop (the replacement for XPRA). Use it for GUI and notebook work, not X11 in batch jobs.

## Rules

- No computation on login nodes. Use them to edit, inspect, submit, and review. Run CPU-, memory-, or time-heavy work, containers, and large transfers through Slurm.
- Always set `--time`. No partition time limits exist yet, and the backfill scheduler starts jobs with short, accurate limits sooner.
- Don't pass `--qos`; only `normal` exists. Don't use `--reservation=interactive` or `gpu_interactive`; they don't exist yet and Slurm rejects them.
- Test with a small input, then size the real request with `jobeff <job-id>` or `sacct ... MaxRSS`.
- Don't cancel and resubmit an unchanged pending job. Read the reason first (see Diagnose).
- Load modules inside job scripts, never in `.bashrc`.
- Each array task writes to its own output path. Never delete a shared directory from inside an array task.
- Never put passwords, tokens, or private keys in job scripts or support requests.
- Don't override `UCX_NET_DEVICES` or `NCCL_IB_HCA`; Slurm sets them for the RoCE network.
- Mail notifications don't work (`--mail-type` has no effect). Chain follow-up work with `--dependency=afterok:<job-id>`.
- Query Slurm sparingly. Every `squeue`, `sacct`, `sinfo`, `scontrol`, or site-tool call loads the shared scheduler, and Slurm rate-limits users who send too many. Never use `watch squeue` or tight polling loops: check every few minutes at most, query all jobs at once (`squeue --me`), and use `--dependency` instead of waiting scripts.
- Accounts: jobs run under the user's default Slurm account. Users in several labs or groups can choose one with `-A <account>`. Check memberships with `sacctmgr show user $USER withassoc format=DefaultAccount%30,Account%30`.

## Partitions and nodes

| Partition | Nodes | Cores per node | Memory per node | Default memory per CPU | GPUs |
|---|---|---|---|---|---|
| `c` (default) | `cbe-c3-[1-18]` | 192 (AMD Zen 5, no SMT) | about 754 GB | 3,800 MB | none |
| `g` | `cbe-g5-[1-8]` | 192 | about 1.5 TB | 7,600 MB | 8× B200 (4 full + 28 MIG slices per node) |
| `m` | `cbe-m3-[1-4]` | 160 (4× Intel Xeon Platinum 8460H) | about 7.9 TB | 3,800 MB | none |

- Use partition `m` only for jobs that need more memory than a `c` node has (about 754 GB). Always request the memory explicitly, for example `--mem=2T`; the default per CPU is the same as on `c`.
- No node uses SMT, so one Slurm CPU is one physical core.
- Array indices: 0–3000.
- Per-job temporary storage, both deleted when the job ends:
  - `/tmp` (`$TMPDIR`) and `/var/tmp`: private, on the fast BeeGFS filesystem behind `/scratch`. The best place for a job's temporary files.
  - `/dev/shm`: private, in the job's memory. Very fast, but everything written there counts against `--mem`. Use it for many small temporary files or small caches.
- Maintenance: one day per month, always announced. Jobs whose `--time` would run into it stay pending with `ReqNodeNotAvail`.

## Batch template

```bash
#!/usr/bin/env bash
#SBATCH --job-name=example
#SBATCH --time=00:10:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=2G
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err
set -euo pipefail
module load <software-name>/<version>
srun <application> <input-file>
```

Create `logs/` before submitting. For arrays, use `--array=0-N%K` and `--output=logs/%x-%A_%a.out`.

Interactive: `salloc --time=00:30:00 --cpus-per-task=1 --mem=2G`. On CBE.next, `salloc` without a command opens a shell directly on the compute node; `exit` ends the allocation.

## GPUs (partition `g`)

- Always request a typed GPU. An untyped `--gres=gpu:1` gets whatever type is free.
  - `--gres=gpu:nvidia_b200:N`: full B200 (about 180 GB). Use it for multi-GPU/NCCL/NVLink work or large training runs.
  - `--gres=gpu:nvidia_b200_1g.23gb:1`: MIG slice (23 GB), for single-GPU inference, small models, or development. Never use several MIG slices for multi-GPU communication.
- Set `--cpus-per-task` and `--mem` explicitly; a GPU request doesn't reserve them.
- Check the current layout with `sinfo -p g -o "%N %G"`. Inside the job, verify with `nvidia-smi -L` and `echo $CUDA_VISIBLE_DEVICES`.
- Containers: use `apptainer exec --nv`. Never use `--cleanenv` on GPU nodes; it drops `CUDA_VISIBLE_DEVICES`. If a clean environment is needed, pass `--env CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES}"`.

## Software

- Two sticky module stacks load at sign-in: `EESSI/2025.06` and `CBE/2025.06`. They survive `module purge`. Find software with `module spider <name>` and load it with an explicit `module load <name>/<version>`.
- Python: `uv` for Python-only projects; conda from the global Miniforge (conda-forge only) for other dependencies. Never Anaconda, Miniconda, or the `defaults` channel (license terms). Use `conda`, not `mamba -n`, which fails on CBE.next.
- Containers: Apptainer only (`singularity` is an alias). Images are built outside CBE.next, or by IT from a Git repository, and pulled from a registry.
- Before pulling or downloading anything, check the read-only collections in `/cvmfs`, `/programs`, and `/resources`.
- For finding, choosing, and using software, use the `cbe-software` skill.

## Storage

| Path | Use for | Lifetime and backup | Check usage |
|---|---|---|---|
| `$HOME` (`/users/$USER`) | scripts, config, environments, small files | persistent; snapshots in `/users/.snapshot`; backup 180 days | `quota -s` |
| `$SCRATCHDIR` (`/scratch/users/$USER`) | large active data and job I/O | files deleted after 28 days; no backup | `du -sh $SCRATCHDIR` |
| `/groups/<group>` | shared input and retained results; not temporary job output | persistent; hourly snapshots in `/groups/.snapshot` | `quota -s` |
| `/resources` | curated reference data, read-only | — | — |
| `/clustertmp` | exchanging data with workstations or other groups; not job output | unmodified data is deleted automatically | — |

- Staging pattern: authoritative copy in `/groups`, then stage into `$SCRATCHDIR`, compute, copy results back to `/groups`, and clean up.
- Never leave the only copy of results on `/scratch`.
- Never delete or overwrite anything in `/groups` without the user's explicit confirmation of the exact paths.
- Run large transfers as batch jobs, never on the login node.
- For filesystem performance, policies, restores, and transfers to or from external endpoints, use the `cbe-data` skill.

## Diagnose

- Pending: run `squeue --me --start` and `scontrol show job <id> | grep -E "JobState|Reason"`. Common reasons: `Priority`/`Resources` mean wait or shrink the request; `ReqNodeNotAvail` usually means maintenance; `DependencyNeverSatisfied` means cancel and fix; `JobHeldAdmin` means contact support.
- Priority: fair share with a 7-day half-life plus age. Inspect with `sprio -l -j <id>` and `sshare -l`. There's no preemption.
- Site tools (on `PATH`): `jobinfo <id>`, `jobeff --me`, `showuserlimits`, `showpartitions -g`, `pestat -p c`, `showjobreasons`, `showuserjobs`.
- Failed job: use the `cbe-triage` skill.
- Slow job, or sizing and optimising resource requests: use the `cbe-tuning` skill.

## When to stop and hand back to the user

Stop for:

- quota, permission, or I/O errors you can't explain;
- software still missing after `module spider`;
- memory needs beyond a single `m` node (about 7.9 TB);
- multi-terabyte transfers;
- SSH certificate or host key problems;
- `JobHeldAdmin`.

Support: the CBE.next MS Teams channel for operational questions, or the HPC Servicedesk (https://vbc.atlassian.net/servicedesk/customer/portal/5/group/6). ÖAW users can also write to contact@clip.science. Include the job ID, commands, exact error, `module list` output, and affected paths. Never include secrets or sensitive data.

## Details (fetch as Markdown)

https://docs.vbc.ac.at/research-computing/cbe/<page>/index.md, where `<page>` is one of: `cluster-resources`, `slurm-jobs`, `gpu-jobs`, `software-environment-eessi`, `containers`, `python-and-conda`, `storage-and-data`, `transfer-data`, `openondemand-web-applications`, `bring-your-own-license`, `troubleshooting-and-support`, `change-notes`.

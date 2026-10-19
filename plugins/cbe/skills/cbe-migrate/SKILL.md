---
name: cbe-migrate
description: "Port job scripts, sbatch files, modules, conda environments, containers, data, and interactive JupyterHub, RStudio, or XPRA workflows from legacy CBE to CBE.next. Use for legacy cbe.vbc.ac.at, clip-login-* or clip-* hosts, /scratch-cbe, old QOS settings such as c_short, m_long, or g_rapid, and preparation for the legacy shutdown on 2026-12-18."
metadata:
  display-name: "CBE migration"
  short-description: "Migrate legacy CBE workflows to CBE.next"
  example-task: "port this legacy CBE workflow to CBE.next."
---

# Port workloads from legacy CBE to CBE.next

Legacy CBE shuts down on 2026-12-18. After that, data that exists only on legacy CBE is gone, including legacy home directories and `/scratch-cbe`. This skill covers translating and validating workloads. For general CBE.next usage, use the `cbe-next` skill; for software replacements, `cbe-software`; for filesystems and transfers, `cbe-data`.

Facts below reflect the docs as of 2026-10-19. Items marked *not final* may have changed. Prefer what CBE.next reports (`sinfo`, `module spider`, `showuserlimits`).

## How to work

1. **Inventory first.** For each workflow, collect:
   - the job script or start command;
   - CPU, memory, runtime, GPU, and temporary-storage needs;
   - modules, conda environments, containers, and custom binaries;
   - input, output, scratch, and archive paths;
   - notification, transfer, and cleanup steps before or after the job.

   Include arrays, interactive sessions, notebooks, and transfer jobs, not just the obvious batch scripts.
2. **Translate a copy.** Write the CBE.next version next to the original, for example `job.cbenext.sbatch`. Keep the legacy script unchanged until the user confirms the new one works.
3. **Report every change.** Give the user a short per-script list: what you changed, why, and anything you couldn't translate.
4. **Validate small.** Run a representative small job on CBE.next before any production run. Compare with a known-good legacy result where one exists.
5. **Ask before moving data.** Confirm what to copy, where, and roughly how much before starting any transfer. Never delete legacy data; the user decides when legacy copies can go.

Don't assume you can reach both clusters from one session. Check which host you're on (`hostname`): legacy login nodes are `clip-login-0/1`. If a step has to run on the other cluster, give the user the exact commands.

## Hostnames and access

| Legacy CBE | CBE.next |
|---|---|
| `ssh cbe.vbc.ac.at` | `ssh cbe.next` |
| `clip-login-0/1.cbe.vbc.ac.at` | the `cbe.next` alias; don't hardcode login node names |
| VPN from outside campus | jump host: `ssh -P vbc-jump-ext cbe.next` on managed devices |
| password or key login | 16-hour SSH certificate: the user runs `step ssh login vbc-cbe` |

Update hostnames in local SSH configs, scripts, and group documentation too.

## Storage paths

| Legacy path | CBE.next path | Action |
|---|---|---|
| `/groups/<group>` | `/groups/<group>` | Same storage. Don't copy. |
| `/resources` | `/resources` | Same storage. Don't copy. |
| `/programs` | `/programs` | SBGrid software, same path. |
| `/scratch` (the clustertmp share) | `/clustertmp` | Same data, new path. Rewrite `/scratch/...` to `/clustertmp/...`. |
| `/users/$USER` (`$HOME`) | `/users/$USER` (`$HOME`) | Separate home directories. Copy what's still needed. |
| `/scratch-cbe` (`$SCRATCHDIR`) | `/scratch` (`$SCRATCHDIR`) | Different filesystem. Copy only active data. Files on the new `/scratch` are deleted after 28 days. |

**The `/scratch` trap:** a legacy script that writes to `/scratch/...` meant the shared exchange area. On CBE.next, that same path is the fast job scratch, where files are deleted after 28 days. Rewrite these paths explicitly. Don't leave a bare `/scratch` path, and prefer `$SCRATCHDIR` for job I/O.

**Per-job temporary space:** on CBE.next, each job gets a private `/tmp` (`$TMPDIR`, also `/var/tmp`) on the fast BeeGFS filesystem, and a private `/dev/shm` in its memory that counts against `--mem`. Both are deleted when the job ends. Legacy scripts that wrote large temporary files to `/dev/shm` need more `--mem`, or should switch to `$TMPDIR`.

### Copying data

Copy through storage that both clusters mount. Run large copies as batch jobs, never on a login node.

On legacy CBE, stage into the clustertmp share (legacy path `/scratch`):

```bash
mkdir -p /scratch/<user>/migration
rsync --archive --partial --info=progress2 $HOME/my-project/ /scratch/<user>/migration/my-project/
```

On CBE.next, copy from the same share (new path `/clustertmp`) to the final location:

```bash
rsync --archive --partial --info=progress2 /clustertmp/<user>/migration/my-project/ $HOME/my-project/
```

- For group data, stage in `/groups/<group>`.
- Before removing any copy, verify the new one is complete: `rsync --archive --checksum --dry-run --itemize-changes <staged>/ <final>/` copies nothing and lists every missing or different file. Repeat the copy until the list is empty. Do the same check on legacy CBE, between the original and the staged copy.
- Remove the staged copy from `/clustertmp` afterwards, because it's a shared area. Ask the user first.
- Clean up before copying: keep code, scripts, configuration, and needed inputs. Don't copy old logs, intermediates, failed runs, or whole scratch trees.
- For multi-terabyte data, stop and ask the user to check with the CBE.next MS Teams channel first.

## Slurm directives

Review the whole `#SBATCH` block. Don't assume it runs unchanged.

| Legacy CBE | CBE.next |
|---|---|
| `--partition=c` | `c`, the default; the line can stay or go |
| `--partition=m` | `m`: four nodes with about 7.9 TB each. Always set `--mem` explicitly (for example `--mem=2T`); the default per CPU is only 3,800 MB. Don't move high-memory jobs to `g`. |
| `--partition=g` | `g` |
| `--gres=gpu:<p100\|v100\|rtx\|a100>:N`, or untyped | `--gres=gpu:nvidia_b200:N` for a full B200 (about 180 GB), or `--gres=gpu:nvidia_b200_1g.23gb:1` for a MIG slice (23 GB, single GPU only) |
| `--qos=c_short`, `m_long`, `g_rapid`, and similar | Remove. Only `normal` exists; the new QOS scheme is *not final*. |
| `--qos=grid_generic` | Not possible yet. The grid partition is *not final*; flag it to the user. |
| implicit time limit from QOS (`rapid` 1 h, `short` 8 h, `medium` 2 days, `long` 14 days) | Always set an explicit `--time`. Carry over the old effective limit, or better, measured runtime plus a margin. |
| `--nodelist`, `--exclude`, `--constraint` with `clip-c*`, `clip-g*`, `clip-m*` | Remove. Request generic resources. |
| `--reservation=...` (interactive) | Remove. The interactive reservations don't exist yet. |
| `srun --pty bash` for interactive work | `salloc --time=<t> --cpus-per-task=<n> --mem=<m>`, which opens a shell on the compute node |
| implicit default account | Jobs use the user's default Slurm account. Users in several labs or groups add `-A <account>`. |
| `--mail-type`, `--mail-user` | No effect; there's no mail. Use `--dependency=afterok:<id>` for follow-up work, or tell the user to check `squeue --me` or `jobinfo`. |

**Resource sizing:**

- Node sizes changed a lot. Legacy regular nodes had 22 or 38 virtual cores and 85 or 170 GB. CBE.next `c` nodes have 192 cores and about 754 GB, with a default of 3,800 MB per CPU.
- Re-check `--nodes`, `--ntasks-per-node`, and `--mem`. Make memory explicit if the job relied on a legacy default.
- For GPU jobs, set `--cpus-per-task` and `--mem` explicitly; a GPU request doesn't reserve them.
- MIG slices can't talk to each other. Multi-GPU jobs need full `nvidia_b200` GPUs.
- Don't set `UCX_NET_DEVICES` or `NCCL_IB_HCA` in ported MPI or NCCL scripts; Slurm sets them.

## Software

| Legacy CBE | CBE.next |
|---|---|
| `/software/...` paths, `/software/2020` tree, `foss-2018b` and `foss-2019b` toolchains | Gone. Find replacements with `module spider <name>` in the default stacks `EESSI/2025.06` and `CBE/2025.06`, which are always loaded. |
| `ml load <name>/<version>` | Same Lmod syntax, but module names and versions differ. Check each one. |
| saved module collections (`module restore`) | Not portable. Rebuild them with `module save`. |
| conda, mamba, micromamba environments | Use the global Miniforge on CBE.next (conda-forge only). Re-create environments from an export (below). For Bioconda tools, the prebuilt images in `/cvmfs/singularity.galaxyproject.org/all/` are an alternative. Python-only projects can move to `uv`. |
| Singularity containers | `singularity` is an alias for Apptainer 1.5.3. Rebuild images that depend on legacy paths, drivers, MPI, or module trees. Use `--nv` for GPUs, never `--cleanenv` on GPU nodes. |
| MATLAB module | No module. Bring your own license: the user installs MATLAB or uses a container, and `MLM_LICENSE_FILE` goes in the job script. |
| private copies of reference genomes or indexes | Check `/resources` and `/cvmfs/data.galaxyproject.org` first. |

**Conda environments:** don't copy environment directories or a personal Anaconda or Miniconda installation. On legacy CBE, export each environment with `conda env export -n <name> --from-history > environment.yml`. Replace a `defaults` channel with `conda-forge` (Anaconda license terms), copy the file, and on CBE.next run `conda env create -n <name> -f environment.yml`. Use `conda`, not `mamba -n`. Create environments in `$HOME` or `/groups`, never on `/scratch`. For pip-only environments, `pip freeze` and `uv` work too.

Record the old and new module names and versions for each workflow, so the user can compare results.

## Interactive services

| Legacy CBE | CBE.next |
|---|---|
| JupyterHub | OpenOnDemand Jupyter (https://ood.atlas.cbenext.vbc.ac.at/). Register custom environments as kernels. |
| RStudio | OpenOnDemand RStudio Server |
| XPRA or remote desktop | OpenOnDemand Remote Desktop: a Linux desktop in the browser, running as a Slurm job. |
| X11 in batch or interactive jobs | Don't port. Use OpenOnDemand. |

## Validate

On CBE.next, submit a small job with the same software, input type, output location, and resource pattern. Then check:

- exit code `COMPLETED 0:0` in `sacct`;
- logs in the expected place;
- the expected software versions;
- plausible runtime, CPU, and memory (`jobeff <id>`);
- temporary data cleaned up or staged out;
- output matching a legacy result for the same input, where one exists.

Scale up only after this passes.

## Finish

For each migrated workflow, give the user a record of:

- the CBE.next script location;
- the modules, environments, or containers used;
- the input, output, scratch, and archive paths;
- the validation result and date;
- differences from the legacy workflow.

Suggest labelling or removing the legacy script once the group confirms the new one, so nobody submits new work to legacy CBE.

## Stop and hand back to the user

Stop for:

- grid jobs (`grid_generic`), which have no CBE.next target yet;
- multi-terabyte transfers;
- software with no equivalent after `module spider`;
- license server access;
- anything that would delete legacy data;
- SSH certificate or host key problems.

Support: the CBE.next MS Teams channel, or the HPC Servicedesk (https://vbc.atlassian.net/servicedesk/customer/portal/5/group/6). ÖAW users can also write to contact@clip.science.

## Details (fetch as Markdown)

- Migration guide: https://docs.vbc.ac.at/research-computing/cbe/migrate-from-cbe/index.md
- Legacy reference: https://docs.vbc.ac.at/research-computing/legacy-cbe/cbe-slurm-user-s-advanced-guide/index.md and https://docs.vbc.ac.at/research-computing/legacy-cbe/cbe-storage-user-s-guide/index.md
- CBE.next: https://docs.vbc.ac.at/research-computing/cbe/<page>/index.md, where `<page>` is one of `cluster-resources`, `slurm-jobs`, `gpu-jobs`, `software-environment-eessi`, `containers`, `python-and-conda`, `storage-and-data`, `transfer-data`, `openondemand-web-applications`, `bring-your-own-license`.

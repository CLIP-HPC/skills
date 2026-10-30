---
name: cbe-nextflow
description: "Set up, run, resume, and debug Nextflow and nf-core pipelines on CBE.next: the Nextflow modules, a CBE.next config for the Slurm executor (partitions c, g, m, QOS from the task time, typed B200 or MIG GPUs), Apptainer/Singularity image caches, the head job as an sbatch job instead of on the login node, work directories on $SCRATCHDIR, publishDir to /groups, -resume, and nf-core tools. Use for nextflow run, nf-core pipelines such as rnaseq, sarek, or atacseq, -profile cbe or other legacy CBE profiles, nextflow.config, .nextflow.log, failed processes and exit status 137 or 140, work/.command.err, cached tasks that rerun, container pull failures, and pipelines that stop when the session ends. Use cbe-triage for failed Slurm jobs outside Nextflow, cbe-software for single tools, and cbe-python for conda environments."
metadata:
  display-name: "CBE Nextflow"
  short-description: "Run and debug Nextflow and nf-core pipelines"
  example-task: "run nf-core/rnaseq on my samples on CBE.next."
---

# Nextflow on CBE.next

Facts below reflect CBE.next as of 2026-10-30 (Nextflow modules 22.10.7, 24.04.4, 25.04.6, and 26.04.0 in `EESSI/2025.06`, Apptainer 1.5). Prefer what the cluster reports (`module spider Nextflow`).

A Nextflow run has three parts in three places. Keep them apart:

| Part | What it is | Where on CBE.next |
|---|---|---|
| Head job | The `nextflow run` process: plans the run and submits each task as a Slurm job | An `sbatch` job on partition `c`; never the login node |
| Work directory | One directory per task with inputs, outputs, logs; needed for `-resume` | `$SCRATCHDIR` (files deleted after 28 days) |
| Results | What `publishDir` or `--outdir` copies out | `/groups/<group>/...` |

Launch from a project directory in `/groups/<group>/<user>/<project>` or `$HOME`. Nextflow writes `.nextflow/` (the resume cache) and `.nextflow.log` there, so always launch the same pipeline from the same directory.

## Don't use the legacy `cbe` profile

nf-core's institutional profile `-profile cbe` was written for legacy CBE. On CBE.next it loads modules that don't exist (`build-env/f2021`, `anaconda3`), caps tasks at 36 CPUs, and uses the legacy image cache in `/resources/containers`. Remove `cbe` from `-profile`, and from `custom_config_base` or `-c` files copied from legacy CBE, and use the config below instead. Use `-profile singularity` (not `apptainer`): nf-core modules then download prebuilt Singularity images instead of converting Docker images on the cluster.

## Set up

1. Load a module explicitly. Use the newest one unless the pipeline asks for an older version (`manifest.nextflowVersion` in its `nextflow.config`):

    ```bash
    module spider Nextflow
    module load Nextflow/26.04.0      # also loads the Java it needs
    ```

    Don't install Nextflow with `curl | bash`, conda, or into `~/bin`: a second Nextflow on `PATH` causes version confusion in jobs.
2. nf-core tools (`nf-core pipelines list`, `download`, `create`) are not a module. Run them with `uvx nf-core ...`, or add `nf-core` to a uv project (see `cbe-python`).
3. Put the cluster settings in `cbe-next.config` in the project and commit it with the pipeline parameters. Pass it with `-c cbe-next.config`:

    ```groovy
    // CBE.next: Slurm, Apptainer, and the site's partitions and QOS levels
    params {
        config_profile_description = 'CBE.next, Vienna BioCenter'
        igenomes_base              = '/resources/references/igenomes'
    }

    executor {
        name              = 'slurm'
        queueSize         = 200
        submitRateLimit   = '5 sec'
        queueStatInterval = '2 min'
        exitReadTimeout   = '5 min'
    }

    process {
        executor       = 'slurm'
        cache          = 'lenient'
        resourceLimits = [cpus: 192, memory: 7.5.TB, time: 14.d]
        // m only for tasks that need more than a c node has; Slurm rejects m jobs under 700,000 MB
        queue          = { task.memory > 740.GB ? 'm' : 'c' }
        // QOS level from the time limit; the submit hook adds the partition prefix
        clusterOptions = {
            def t = task.time ?: 8.h
            "--qos=${t <= 1.h ? 'rapid' : t <= 8.h ? 'short' : t <= 48.h ? 'medium' : 'long'}"
        }

        withLabel: 'process_gpu' {
            queue            = 'g'
            clusterOptions   = {
                def t = task.time ?: 8.h
                "--gres=gpu:nvidia_b200_1g.23gb:1 --qos=${t <= 1.h ? 'rapid' : t <= 8.h ? 'short' : t <= 48.h ? 'medium' : 'long'}"
            }
            containerOptions = '--nv'
        }
    }

    singularity {
        enabled      = true
        autoMounts   = true
        pullTimeout  = '1 h'
        envWhitelist = 'CUDA_VISIBLE_DEVICES'
    }
    ```

    Why each part:
    - `submitRateLimit` and `queueStatInterval`: Slurm on CBE.next rate-limits users who send many requests. Nextflow's defaults (no submit limit, a status query every minute) can hit it on large runs.
    - `cache = 'lenient'`: `/groups` and `/scratch` are network filesystems whose inode numbers and timestamps can change, which makes the default cache rerun tasks after `-resume`.
    - `queue`, `clusterOptions`: CBE.next partitions have no time limit; the QOS sets it. Write only the level (`--qos=short`); a submit hook adds the partition prefix. A task without `time` gets `short` (8 hours).
    - `resourceLimits` caps pipeline defaults at the largest node. `m` nodes have 160 cores, so a task asking for more than 740 GB *and* more than 160 CPUs fails; lower its CPUs.
    - GPUs: the Slurm executor ignores the `accelerator` directive, so GPUs are requested in `clusterOptions`. Always a typed GPU: a 23 GB MIG slice as above, or `--gres=gpu:nvidia_b200:1` for a full B200 when the model needs more memory. Nextflow starts containers with a cleared environment, so `envWhitelist` passes `CUDA_VISIBLE_DEVICES` through. nf-core pipelines label GPU processes `process_gpu`; check the pipeline's `conf/base.config` and adapt the selector if it uses another label.
4. Set the image cache to group storage, so every run and every group member reuses the images, and they don't fill `$HOME` (file-count limit) or vanish from `/scratch`:

    ```bash
    export NXF_SINGULARITY_CACHEDIR=/groups/<group>/nextflow/singularity
    export APPTAINER_CACHEDIR=$SCRATCHDIR/apptainer-cache
    mkdir -p "$NXF_SINGULARITY_CACHEDIR" "$APPTAINER_CACHEDIR"
    ```

    Put these lines in the head job script, not in `~/.bashrc`. Don't point the cache at `/resources/containers`. Compute nodes can reach container registries and GitHub, so the head job pulls pipelines and images itself; `nf-core pipelines download` is only needed for offline copies.
5. Reference genomes: before downloading, check `/resources/references` (an AWS iGenomes copy for `--genome`, last updated in 2020), `/cvmfs/data.galaxyproject.org`, and `/cvmfs/refgenomes-databio.galaxyproject.org`. For current assemblies, pass `--fasta` and `--gtf` explicitly instead of `--genome`.

## Run

Run the head job as a batch job. It needs little CPU and memory, but must run as long as the whole pipeline:

```bash
#!/usr/bin/env bash
#SBATCH --job-name=nf-rnaseq
#SBATCH --partition=c
#SBATCH --qos=medium
#SBATCH --time=2-00:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=logs/%x-%j.out
set -euo pipefail
module load Nextflow/26.04.0
export NXF_OPTS='-Xms1g -Xmx6g'
export NXF_SINGULARITY_CACHEDIR=/groups/<group>/nextflow/singularity
export APPTAINER_CACHEDIR=$SCRATCHDIR/apptainer-cache
mkdir -p "$NXF_SINGULARITY_CACHEDIR" "$APPTAINER_CACHEDIR"

nextflow run nf-core/rnaseq -r 3.27.0 \
    -profile singularity -c cbe-next.config \
    -params-file params.yaml \
    -work-dir "$SCRATCHDIR/nextflow/<project>/work" \
    --outdir /groups/<group>/<user>/<project>/results \
    -resume -ansi-log false \
    -with-report logs/report-$SLURM_JOB_ID.html -with-trace logs/trace-$SLURM_JOB_ID.txt
```

- Size the head job's time to the whole run: `medium` (2 days) for most runs, `long` (14 days) only for runs that need it. When the head job hits its limit, Nextflow stops submitting; resubmit the same script and `-resume` continues.
- Don't run `nextflow run` on the login node, in `tmux` or `screen` there, or with `nohup`. That breaks the login-node rule, and the run dies with the session or the node.
- Pin the pipeline release with `-r` and keep inputs in `params.yaml`, so the run can be repeated. Record `nextflow -version` and the commit of the project with the results.
- Test first: `-profile test,singularity -c cbe-next.config` runs the pipeline's small test data set in a few minutes and pulls the images into the cache.
- Many short tasks load the scheduler. In your own pipelines, group them with the `array` directive (Nextflow 24.04 or newer; each array job may have at most 3,001 tasks) instead of thousands of separate jobs.
- Follow progress in the head job's output file or `.nextflow.log`, and with `squeue --me` every few minutes at most. Task jobs are named `nf-<PROCESS>_(<tag>)`.
- To stop a run, cancel only the head job (`scancel <head-job-id>`). Nextflow then cancels its task jobs; check with `squeue --me` after a minute and cancel leftovers by name.

## Debug

Start from the head job's output and `.nextflow.log` in the launch directory. The error message names the failed process, its exit status, and its work directory. Then look in that directory:

| File | Contains |
|---|---|
| `.command.sh` | the task's script with all variables filled in |
| `.command.run` | the Slurm wrapper with the `#SBATCH` lines Nextflow generated |
| `.command.out`, `.command.err`, `.command.log` | the task's output, errors, and Slurm output |
| `.exitcode` | the exit status; missing when the job was killed |
| `.command.trace` | measured CPU, memory, and time |

Get the Slurm job ID from `.command.log` or the trace file, then use `jobinfo <id>` or `sacct -j <id>`. Reproduce one task by hand in an interactive allocation: `salloc` with the same resources, `cd` into the work directory, `bash .command.run`.

| Symptom | Likely cause and fix |
|---|---|
| Exit status 137, or Slurm state `OUT_OF_MEMORY` | Memory too small. nf-core pipelines retry with more memory; otherwise raise it for that process with `withName: 'NAME' { memory = 32.GB }` in `cbe-next.config`. |
| Exit status 140, or state `TIMEOUT` | Time limit too short: raise `time` for that process. The QOS follows automatically. |
| `Process terminated for an unknown reason`, no `.exitcode` | The job was killed or the node failed: check `sacct -j <id>` and continue with `-resume`. If the job ended normally, the filesystem was slow to show the file: raise `exitReadTimeout`. |
| `sbatch: error: ... QOS` or `Invalid qos specification` | A `--qos` with a partition prefix or a time limit above its QOS. Use the closure above. |
| `Batch job submission failed: ... Requested node configuration is not available` | More CPUs or memory than any node in the partition, or `m` with too little memory. Check `resourceLimits` and the `queue` closure. |
| Tasks stay pending for hours | Read the reason with `squeue --me` (see `cbe-queue`); many `long` tasks wait for QOS caps. |
| `Failed to pull singularity image` or a timeout | Unset or unwritable `NXF_SINGULARITY_CACHEDIR`, `Disk quota exceeded` (`myquota`), or a slow registry: rerun with `-resume`; `pullTimeout` is set to 1 hour above. |
| `GLIBC_*`, `command not found` in a task | The task runs without its container: check that `-profile singularity` is set and that no `module` or `conda` directive overrides it. |
| `Unable to acquire lock on session` | Another Nextflow runs in the same launch directory. Wait for it, or cancel it; never delete `.nextflow/` to get around the lock. |
| All tasks rerun after `-resume` | Different launch directory, changed inputs or parameters, work directory deleted after 28 days on `/scratch`, or `cache = 'lenient'` missing. `nextflow log` lists earlier runs; `-dump-hashes` shows what changed. |
| `OutOfMemoryError` in the head job | Raise `NXF_OPTS='-Xmx...'` and the head job's `--mem` together. |
| No GPU in a task (`nvidia-smi` fails, `torch.cuda.is_available()` is `False`) | The process doesn't match the GPU selector (check its label), or `--nv` or `envWhitelist` is missing. |

For a failure in the task's own tool, debug it like any job with `cbe-triage`. A problem on the cluster side goes to `cbe-ticket`; attach `.nextflow.log`, the failed task's work directory path, and the job ID.

## Clean up

- When the results are checked, delete the run's work directory on `/scratch`; it is the bulk of the data. After that, `-resume` starts from scratch.
- `nextflow log` lists the runs from this launch directory; `nextflow clean -n -before <run name>` shows which work directories of older runs would go, and `-f` instead of `-n` deletes them. Run it in the launch directory, and only after the results are in `/groups`.
- Don't delete anything under `/groups` without the user's explicit confirmation of the exact paths (see `cbe-data`).
- Remove unused images from the group cache now and then; they are rebuilt on the next run.

## Details

- https://docs.vbc.ac.at/research-computing/cbe/<page>/index.md for `slurm-jobs`, `gpu-jobs`, `containers`, and `storage-and-data`
- Upstream: https://www.nextflow.io/docs/latest/executor.html#slurm, https://www.nextflow.io/docs/latest/cache-and-resume.html, https://nf-co.re/docs/usage/getting_started/configuration

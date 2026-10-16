---
name: cbe-tuning
description: Improve the performance and resource efficiency of Slurm jobs on CBE.next, the Vienna BioCenter HPC cluster. Analyses the tools a job runs, past runtime and resource usage (sacct, jobeff, jobinfo), thread and process settings, job structure (job arrays for trivially parallel work), storage I/O (/scratch, per-job /tmp, /groups hot spots), and GPU choice (full B200 vs MIG). Proposes an optimisation plan and, if the user agrees, runs small parameter sweeps. Use when a job is slow, waits long in the queue, over- or under-requests CPU, memory, GPU, or time, or the user asks to optimise, speed up, scale, or parallelise a workload.
---

# Tune jobs on CBE.next

The goal is a plan the user agrees to, backed by measurements. Don't rewrite production jobs blindly.

## Principles

- **Measure before changing.** Base every proposal on accounting data or a measured test, not on guesses.
- **Propose, then act.** Present the plan and wait for the user's go-ahead before changing scripts or submitting test jobs.
- **Keep experiments small.** Every test job uses a small but representative input: same tool, same parameters, same file types, a fraction of the data. Never benchmark with the full production dataset.
- **Keep the cluster usable.** Throttle test arrays (`--array=...%4`), set tight `--time` values, and cancel experiments that clearly won't answer the question.
- **Query Slurm sparingly.** Every `squeue`, `sacct`, `sinfo`, `scontrol`, or site-tool call loads the shared scheduler, and Slurm rate-limits heavy users. No `watch squeue` or tight polling loops: check every few minutes at most, query all jobs at once (`squeue --me`), and keep `sacct` time windows narrow.
- **One change at a time.** Change one variable per comparison, so the effect can be attributed.
- **Simple first.** Prefer job arrays and right-sizing over MPI or code changes.

## 1. Understand the job

- Read the job script, and identify each tool and its version (see the `cbe-software` skill).
- For each tool, find the options that control parallelism and memory, such as `--threads`, `-t`, `-p`, `-@`, `--cores`, `-Xmx`, and buffer or chunk sizes. Check them in the tool's own help or docs, not from memory.
- Check that the tool's threads match the allocation. Pass `$SLURM_CPUS_PER_TASK` to the tool, for example `-t "${SLURM_CPUS_PER_TASK}"`, and set `OMP_NUM_THREADS` where relevant.
  - More threads than allocated CPUs means oversubscription.
  - Fewer means idle CPUs that still block other users.
- Note where the job reads and writes: `/groups`, `$SCRATCHDIR`, per-job `/tmp`, or `/clustertmp`.

## 2. Analyse past runs

```bash
sacct -u $USER -S <start-date> --name=<job-name> \
  --format=JobID,JobName%30,State,Elapsed,Timelimit,AllocCPUS,TotalCPU,ReqMem,MaxRSS,AllocTRES%40
jobeff --me            # CPU and memory efficiency of recent jobs
jobeff <job-id>
jobinfo <job-id>       # combined sacct, sstat, and squeue view, including running jobs
```

Look for:

- **CPU efficiency** (`TotalCPU` against `Elapsed × AllocCPUS`). Low means over-requested CPUs, a tool not using its threads, or an I/O-bound job.
- **Memory** (`MaxRSS` against the request). Size the next request to the peak of comparable runs plus a margin, not to a single run.
- **Runtime** against `--time`. Accurate time limits start sooner through backfill; the scheduler plans up to 30 days ahead in 5-minute steps.
- **Queue wait** (`sacct ... --format=Submit,Start`). Long waits often mean oversized requests, not a busy cluster; check `sprio -l -j <id>` and `sshare -l`.
- **Variation** across inputs of different sizes. That suggests sizing per input class.

Node sizes: `c` nodes have 192 cores and about 754 GB (3,800 MB per CPU by default). `g` nodes have 192 cores, about 1.5 TB, and 8 B200 GPUs. `m` nodes have 160 cores and about 7.9 TB; use them only when a job needs more memory than a `c` node, and set `--mem` explicitly. A request should fit comfortably in one node unless the job is genuinely multi-node.

For a job that is running now, observe it on its compute node: threads actually busy, memory against the limit, processes waiting on I/O, and GPU utilisation. Follow `cbe-triage` step 4a. Identify the job's processes with `scontrol listpids <job-id>`, not by name, because other jobs share the node. The job's cgroup (`job_<job-id>`) gives the memory and CPU figures. Observe read-only, with a few samples.

## 3. Choose optimisation levers

| Lever | When | How |
|---|---|---|
| Right-size CPU and memory | Low efficiency, or OOM | Set `--cpus-per-task` to what the tool uses; set `--mem` from the peak `MaxRSS` plus a margin |
| Accurate `--time` | Limits far above actual runtime | Use the measured runtime plus a margin |
| Thread count | Tool's threads don't match the allocation | Wire the tool's thread option to `$SLURM_CPUS_PER_TASK` |
| Job array | The same tool runs over many independent inputs (samples, chromosomes, chunks) | One task per input or per batch of inputs, `--array=0-N%K`, output subfolder per task; arrays go up to index 3000 |
| Split or merge steps | One script mixes steps with very different needs | Separate jobs chained with `--dependency=afterok:<id>`, each sized for its own step |
| Batch tiny tasks | Thousands of seconds-long tasks | Process several inputs per array task, to cut scheduling overhead |
| Stage to `/scratch` | Heavy I/O directly on `/groups` | Stage input into `$SCRATCHDIR`, write intermediates to `$SCRATCHDIR` or per-job `/tmp`, copy results back |
| Avoid `/groups` hot spots | Many tasks writing into one folder | One output subfolder per task |
| File layout | Huge numbers of small files, or files over 1 TB | Pack small files (`tar`, HDF5, Zarr); split large outputs |
| Wider striping | Very large files read or written by many nodes at once | Ask the user to request it from support |
| GPU choice | GPU memory need is small, or the GPU is idle much of the time | Use a MIG slice (`gpu:nvidia_b200_1g.23gb`, 23 GB) instead of a full B200; set CPUs and memory explicitly |
| Container overhead | Image pulled per job | Pull once to a `.sif` in `$HOME` or `/groups`, or use an image from `/cvmfs` |

Per-job `/tmp` (`$TMPDIR`) and `$SCRATCHDIR` are on the same fast BeeGFS filesystem. Use `/tmp` for files that should disappear with the job, and `$SCRATCHDIR` for data shared between jobs or steps. `/dev/shm` is faster still, but it's part of the job's memory. Use it for many small files created and deleted in a tight loop, or small caches, and add its size to `--mem`.

## 4. Parameter sweeps (only with user consent)

Ask the user before running a sweep. Explain:

- the parameters you want to vary;
- the values you'll test;
- the size of the test input;
- the number of jobs and the expected total core-hours and GPU-hours.

```bash
#SBATCH --array=0-5%3
#SBATCH --time=00:20:00
threads=(4 8 16 32 48 96)
t=${threads[$SLURM_ARRAY_TASK_ID]}
# match the allocation to the value under test, or submit one array per --cpus-per-task value
```

- Keep sweeps small: a handful of values and a small representative input. Repeat a point only if results are noisy.
- When the request itself varies (CPUs, memory, GPU type), submit separate small jobs or arrays per request size. Don't over-allocate one job and use part of it.
- Collect `Elapsed`, `TotalCPU`, and `MaxRSS` from `sacct` for each task. Report runtime, speedup, and efficiency per value.
- Recommend the point where extra resources stop paying off (for example, under 70% parallel efficiency), not the absolute fastest.

## 5. MPI and multi-node: advanced, ask first

Only suggest MPI when the application supports it and a single 192-core node isn't enough. Before setting it up:

- Ask the user whether they want it, and say clearly that it makes the job considerably more complex to set up, debug, and maintain.
- Prefer a job array if the work is actually independent pieces.

If the user agrees:

- Use the MPI build of the application from the module stacks (`module spider`), and launch it with `srun`.
- Request `--nodes`, `--ntasks-per-node`, and `--cpus-per-task` deliberately.
- Don't set `UCX_NET_DEVICES` or `NCCL_IB_HCA`. Slurm sets them for the 400 Gbit/s RoCE network, and overriding them falls back to slower paths.
- For multi-GPU NCCL, use full `gpu:nvidia_b200` GPUs. MIG slices can't communicate with each other.
- Validate on 2 nodes with a small case before scaling. Measure scaling efficiency the same way as a sweep.

## 6. Present the plan

For each proposed change, give:

- the evidence (numbers from `sacct`, `jobeff`, or the sweep);
- the change itself, as a diff of the script;
- the expected effect;
- any risk.

Apply changes to a copy of the script, validate with one small run, and only then suggest updating the production script.

## Details (fetch as Markdown)

https://docs.vbc.ac.at/research-computing/cbe/<page>/index.md, where `<page>` is one of `cluster-resources`, `slurm-jobs`, `gpu-jobs`, `storage-and-data`, `software-environment-eessi`; and https://docs.vbc.ac.at/data-services/storage-parallelization/index.md and https://docs.vbc.ac.at/data-services/storage-best-practices/index.md.

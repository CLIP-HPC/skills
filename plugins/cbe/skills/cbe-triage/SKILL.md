---
name: cbe-triage
description: "Diagnose failed, crashed, killed, cancelled, timed-out, out-of-memory, hanging, or incorrect Slurm jobs on CBE.next using job logs and accounting data. Check system-side causes such as exceeded quota, scratch deletion, node failure, network or storage errors, and maintenance; compare with successful runs, reproduce minimally, and hand over to cbe-ticket when it needs support. Use cbe-tuning for otherwise working jobs that need better performance."
metadata:
  display-name: "CBE job triage"
  short-description: "Diagnose failed jobs and find their cause"
  example-task: "diagnose this failed job from its script and logs."
---

# Triage failed jobs on CBE.next

This skill is for diagnosing your own jobs.

## Principles

- **Evidence before conclusions.** Keep a list of hypotheses, and attach the evidence for and against each one. Don't declare a cause until the evidence supports it. Say "unclear" when it is.
- **Compare with what worked.** A previous successful run of the same or a similar job is the best reference.
- **Reproduce minimally.** Reproduce with the smallest input and the smallest resources that still show the problem. Never resubmit the full production job to "see if it happens again".
- **Read-only first.** Diagnose without changing data. Don't delete or overwrite outputs, inputs, or anything in `/groups` (see the `cbe-data` skill).
- **Query Slurm sparingly.** Every `squeue`, `sacct`, `sinfo`, `scontrol`, or site-tool call loads the shared scheduler, and Slurm rate-limits heavy users. No `watch squeue` or tight polling loops: check every few minutes at most, query all jobs at once (`squeue --me`), and keep `sacct` time windows narrow.
- **Escalate when needed.** If the cause stays unclear, or fixing it needs action on the cluster, propose a ticket with the `cbe-ticket` skill.

## 1. Collect the facts

Ask for, or find, the job ID, the script, the working directory, and when the job ran.

```bash
sacct -j <job-id> --format=JobID,JobName%30,State,ExitCode,DerivedExitCode,Start,End,Elapsed,Timelimit,NodeList%30,AllocCPUS,ReqMem,MaxRSS,AllocTRES%40
jobinfo <job-id>
scontrol show job <job-id>     # only while Slurm still knows the job
```

- Read the job's stdout and stderr files completely, especially the first error and the last lines. The first error is usually the cause; later ones are often consequences.
- Record the modules loaded, the container image, and the input and output paths.

## 2. Read the state

| `State` / signal | Usual meaning | Check |
|---|---|---|
| `OUT_OF_MEMORY`, or `oom-kill` in the log | Memory exceeded the request | `MaxRSS` against `ReqMem`; growth with input size |
| `TIMEOUT` | Hit `--time` | Did it make progress? Compare `Elapsed` with earlier runs |
| `FAILED` with an exit code | The application exited non-zero | The log's first error; the exit code's meaning for this tool |
| `CANCELLED` | Cancelled by the user, a dependency, or an admin | `sacct` and the log; whether the user cancelled it |
| `NODE_FAIL`, or `BOOT_FAIL` | Node problem | `NodeList`; whether other jobs on that node failed at the same time |
| `PENDING` for a long time | Not a failure | Reason codes (see the `cbe-next` skill) |
| `COMPLETED`, but output is wrong or missing | Logic, path, or data problem | Paths, inputs, versions, and empty or partial files |

Exit codes above 128 mean the process was killed by signal (code − 128): 137 is SIGKILL, often out of memory; 139 is SIGSEGV; 143 is SIGTERM.

## 3. Compare with previous runs

```bash
sacct -u $USER -S <date> --name=<job-name> --format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,NodeList%20,Start
jobeff <job-id>
```

Look for what changed between the last good run and the failure:

- input size or content;
- script or parameters;
- module versions (the sticky stacks may have been updated);
- container image tag;
- requested resources;
- the node it ran on;
- the date (maintenance, a 28-day deletion on `/scratch`).

Check whether similar jobs from the same user or group failed at the same time and on the same nodes. That points to the system rather than the job.

## 4. Check system-side causes

| Suspect | Evidence to look for |
|---|---|
| Quota exceeded | `Disk quota exceeded` or `No space left on device` in logs; `myquota` (all filesystems at once) |
| `/dev/shm` use | Out-of-memory although the program's own memory looks fine: files in `/dev/shm` count against `--mem` |
| Scratch deletion | Missing inputs on `/scratch` older than 28 days, or missing staged data in `/clustertmp` |
| Permissions | `Permission denied` on `/groups`. Remember that `chmod` is ignored; access comes from ACLs, so it isn't fixable by the agent |
| Node failure | `NODE_FAIL`; the same node in several failing jobs; `sinfo -R` lists down or drained nodes with reasons; `pestat -p <partition>`; `showevents -w <node> -t 3days` for the node's state changes around the failure |
| Network or storage I/O | Stale file handle, I/O errors, timeouts, MPI/UCX/NCCL connection errors; whether several jobs failed together |
| Maintenance | Job ended or stayed pending around an announced maintenance; CBE.next change notes |
| GPU not visible | `CUDA_VISIBLE_DEVICES` empty inside a container (`--cleanenv` on GPU nodes), or an untyped `--gres` gave the wrong GPU type |
| Environment drift | Modules loaded in `.bashrc`, legacy CBE paths (`/scratch-cbe`, `/software`), legacy `/scratch` meaning `/clustertmp` |
| Licence | License-server connection errors (bring your own license) |

A single symptom is not proof. For example, `Killed` can be out of memory or an admin action; check `sacct` and the memory figures before concluding.

## 4a. Watch a running job on its node

For a job that is still running (hanging, slow, or using unexpected resources), observe it on the compute node. You can only SSH to nodes where you have a running job.

**First look, from the login node:** `psjob <job-id>` lists the job's processes on its nodes, which is often enough to see a stuck or idle job without connecting.

**Find the node:** `squeue -j <job-id> -o "%N"`. For a multi-node job, `scontrol show hostnames <nodelist>` lists each node.

**Connect:**

- `ssh <node>` from the login node.
- Or join the job's allocation: `srun --jobid=<job-id> --overlap --pty bash`.

Either way, your session may count against the job's resources. Keep it light and short.

**Identify the job's processes exactly.** Several jobs from the same and other users share a node, so never pick processes by name, user, or `top` ranking alone.

Primary method: ask Slurm on the node. The node's host name differs from its Slurm node name, so set `SLURMD_NODENAME`; without it, `scontrol listpids` fails with `does not exist on node (null)`.

```bash
SLURMD_NODENAME=$(hostname -s) scontrol listpids <job-id>          # PIDs of the job on this node, with their step (batch, 0, extern, ...)
SLURMD_NODENAME=$(hostname -s) scontrol listpids <job-id>.<step>   # one step only
```

Use these PIDs for all further checks.

Monitoring source: the job's cgroup. Each job has its own cgroup for resource isolation; it's where the memory, CPU, and OOM figures below come from. Its directory has an internal name, not the job ID, so don't search for it by name. Take it from a PID that `listpids` reported:

```bash
cat /proc/<pid>/cgroup                                                  # e.g. 0::/system.slice/slurmstepd.scope/<internal-id>/step_0/user/task_0
jobdir=/sys/fs/cgroup$(cut -d: -f3 /proc/<pid>/cgroup | sed 's#/step_.*##')   # the job's cgroup directory
```

Two processes belong to the same job only if their cgroup paths match up to `/step_`. Step directories inside the job cgroup (`step_batch`, `step_0`, `step_extern`, and so on) separate the batch script from `srun` steps; an SSH session on the node joins the job in `step_extern`.

**Observe.** Use read-only, sampled commands, never continuous loops left running:

```bash
ps -o pid,ppid,stat,pcpu,pmem,rss,nlwp,etime,args -p <pid,pid,...>
top -b -n 3 -d 5 -H -p <pid>                             # threads of one process, 3 samples
cat "$jobdir"/memory.current "$jobdir"/memory.max        # memory used vs limit (cgroup v2)
cat "$jobdir"/memory.events                              # oom and oom_kill counts
cat "$jobdir"/cpu.stat                                   # CPU usage and throttling
cat "$jobdir"/cpuset.cpus.effective                      # CPUs the job may use
nvidia-smi --query-compute-apps=pid,used_memory --format=csv   # match GPU PIDs to the job's PIDs
```

What to look for:

| Observation | Likely meaning |
|---|---|
| Fewer busy threads than allocated CPUs | Thread setting too low, or a serial bottleneck |
| More runnable threads than CPUs in `cpuset.cpus.effective` | Oversubscription |
| `memory.current` close to `memory.max`, or rising `oom` counts | Memory pressure, about to be OOM-killed |
| Processes in state `D` for long periods | Waiting on I/O (storage or network) |
| Low CPU and no I/O | Waiting on a lock, network, licence server, or deadlocked |
| GPU memory used but low utilisation | CPU or I/O bound feeding the GPU |

**Don't change anything.** Never `kill`, signal (`kill -STOP`/`-CONT`), `renice`, or attach debuggers or tracers (`gdb`, `strace`, `perf`, `py-spy`) without the user's explicit approval. They can slow, stop, or crash the job. Never touch processes outside the job's cgroup. Log out when done.

## 5. Reproduce with a minimal example

Only reproduce after reading the evidence. Then build the smallest case that still fails:

- the same tool, version, and parameters as the failing run;
- a reduced input (a few records, one sample, one chunk);
- small resources and a short `--time`;
- a separate test directory under `$SCRATCHDIR`, never writing into the production output directory.

If a small case doesn't reproduce the problem, scale the input up in a few steps, which tells you something about the cause (size-dependent memory, for example). Keep the final reproducer as a self-contained script plus a description of its input, so someone else can run it.

## 6. Conclude or escalate

If you found the cause:

- explain it with the evidence;
- propose the fix as a diff to the script;
- validate the fix with the minimal example before the user reruns production.

Propose a support ticket when:

- the cause is still unclear after the steps above;
- it is on the system side (node, network, or storage faults; quota changes; permissions; striping);
- it needs an admin (`JobHeldAdmin`, a restore from backup).

Write and open it with the `cbe-ticket` skill, which lists the facts to include. Missing software is a request through the `cbe-software` skill.

## Details (fetch as Markdown)

All research-computing pages are relevant. Start with:

- https://docs.vbc.ac.at/research-computing/cbe/troubleshooting-and-support/index.md
- https://docs.vbc.ac.at/research-computing/ssh-troubleshooting/index.md (SSH and certificate problems)
- https://docs.vbc.ac.at/research-computing/cbe/slurm-jobs/index.md (pending reasons, site tools)
- https://docs.vbc.ac.at/research-computing/cbe/cluster-resources/index.md
- https://docs.vbc.ac.at/research-computing/cbe/gpu-jobs/index.md
- https://docs.vbc.ac.at/research-computing/cbe/storage-and-data/index.md
- https://docs.vbc.ac.at/research-computing/cbe/software-environment-eessi/index.md
- https://docs.vbc.ac.at/research-computing/cbe/python-and-conda/index.md
- https://docs.vbc.ac.at/research-computing/cbe/containers/index.md
- https://docs.vbc.ac.at/research-computing/cbe/change-notes/index.md (maintenance and configuration changes)

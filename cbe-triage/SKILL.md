---
name: cbe-triage
description: Triage failed, crashed, killed, hanging, or misbehaving Slurm jobs on CBE.next, the Vienna BioCenter HPC cluster. Checks job logs and accounting data, compares them with previous successful runs, checks system-side causes (quota exceeded, scratch deletion, node failure, network or storage errors, maintenance), reproduces the problem with a minimal example, and, when the cause is unclear or needs cluster-side action, drafts an HPC Servicedesk ticket with the diagnosis, the steps taken, and the minimal reproducer. Use when a job failed, timed out, ran out of memory, was cancelled, produced wrong or missing output, or behaves differently than before.
---

# Triage failed jobs on CBE.next

## Principles

- **Evidence before conclusions.** Keep a list of hypotheses, and attach the evidence for and against each one. Don't declare a cause until the evidence supports it. Say "unclear" when it is.
- **Compare with what worked.** A previous successful run of the same or a similar job is the best reference.
- **Reproduce minimally.** Reproduce with the smallest input and the smallest resources that still show the problem. Never resubmit the full production job to "see if it happens again".
- **Read-only first.** Diagnose without changing data. Don't delete or overwrite outputs, inputs, or anything in `/groups` (see the `cbe-data` skill).
- **Escalate when needed.** If the cause stays unclear, or fixing it needs action on the cluster, prepare an HPC Servicedesk ticket.

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
| Quota exceeded | `Disk quota exceeded` or `No space left on device` in logs; `quota -s`; group usage at https://apps.vbc.ac.at/quotas/ |
| Scratch deletion | Missing inputs on `/scratch` older than 28 days, or missing staged data in `/clustertmp` |
| Permissions | `Permission denied` on `/groups`. Remember that `chmod` is ignored; access comes from ACLs, so it isn't fixable by the agent |
| Node failure | `NODE_FAIL`; the same node in several failing jobs; `sinfo -R` lists down or drained nodes with reasons; `pestat -p <partition>` |
| Network or storage I/O | Stale file handle, I/O errors, timeouts, MPI/UCX/NCCL connection errors; whether several jobs failed together |
| Maintenance | Job ended or stayed pending around an announced maintenance; CBE.next change notes |
| GPU not visible | `CUDA_VISIBLE_DEVICES` empty inside a container (`--cleanenv` on GPU nodes), or an untyped `--gres` gave the wrong GPU type |
| Environment drift | Modules loaded in `.bashrc`, legacy CBE paths (`/scratch-cbe`, `/software`), legacy `/scratch` meaning `/clustertmp` |
| Licence | License-server connection errors (bring your own license) |

A single symptom is not proof. For example, `Killed` can be out of memory or an admin action; check `sacct` and the memory figures before concluding.

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

Escalate to the HPC Servicedesk when:

- the cause is still unclear after the steps above;
- it is on the system side (node, network, or storage faults; quota changes; permissions; striping);
- it needs an admin (`JobHeldAdmin`, a restore from backup, missing software).

### Ticket

Draft the ticket and show it to the user. Create it only after the user approves the text.

```text
Summary: <one line: what fails, where, since when>

Job IDs: <ids>        Time: <date and time range>        Nodes: <NodeList>
Partition/resources: <partition, CPUs, memory, GPUs, time>

What happened:
<expected vs. actual; exact error lines from the logs; sacct State and ExitCode>

Initial diagnosis:
<hypotheses with the evidence for and against each; what has been ruled out>

Steps taken:
<numbered list of checks and their results, including comparisons with previous good runs>

Minimal reproducer:
<script, input description, the command to run, and the observed result>

Environment:
<module list, container image and digest, relevant paths, no file contents>
```

- Never include passwords, keys, certificates, tokens, or confidential file contents. Point to paths instead.
- Create the ticket with the Atlassian connector (`createJiraIssue` on `vbc.atlassian.net`) in the HPC Servicedesk project. Use the issue type that `getJiraProjectIssueTypesMetadata` reports. TODO(confirm): the project key and request type.
- If the connector isn't available, or the user has no permission to create issues through the API, give the user the finished text to paste into the HPC Servicedesk portal: https://vbc.atlassian.net/servicedesk/customer/portal/5/group/6.
- ÖAW users can also write to contact@clip.science. For quick operational questions, there's the CBE.next MS Teams channel.

## Details (fetch as Markdown)

All research-computing pages are relevant. Start with:

- https://docs.vbc.ac.at/research-computing/cbe/troubleshooting-and-support/index.md
- https://docs.vbc.ac.at/research-computing/cbe/slurm-jobs/index.md (pending reasons, site tools)
- https://docs.vbc.ac.at/research-computing/cbe/cluster-resources/index.md
- https://docs.vbc.ac.at/research-computing/cbe/gpu-jobs/index.md
- https://docs.vbc.ac.at/research-computing/cbe/storage-and-data/index.md
- https://docs.vbc.ac.at/research-computing/cbe/software-environment-eessi/index.md
- https://docs.vbc.ac.at/research-computing/cbe/change-notes/index.md (maintenance and configuration changes)

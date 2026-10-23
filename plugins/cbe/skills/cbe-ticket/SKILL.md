---
name: cbe-ticket
description: "Write and open an HPC Servicedesk ticket (Jira project ISD, request type CLIP Support) for a CBE.next or OpenOnDemand problem: failed or hanging jobs, broken nodes, storage, mount, or permission errors, login and SSH problems, OpenOnDemand sessions (Jupyter, RStudio, VS Code, Remote Desktop) that do not start, and suspected Slurm scheduler faults. Use when the user asks to open, file, write, or draft a ticket or support request, or when a problem needs admin action the user cannot take. Collects the job IDs, logs, script, input and output paths, environment, and a minimal reproducer that support needs. A long queue wait alone is not a ticket: use cbe-queue. Diagnose with cbe-triage first."
metadata:
  display-name: "CBE support ticket"
  short-description: "Draft and open a complete HPC Servicedesk ticket"
  example-task: "write a support ticket for this OpenOnDemand session that does not start."
---

# Open a support ticket for CBE.next

The goal is a ticket that support can act on without asking back. Many tickets lack a job ID, the script location, input and output paths, or a reproducer. Support then has to search for them, and a question left unanswered closes the ticket without a fix. Collect these facts before writing, and say which are unavailable.

## When to open a ticket

- **The user asks for one**, for any CBE.next or OpenOnDemand problem. Collect the facts first (step 1). If they show a cause the user can fix, such as out of memory, a wrong partition or path, a full quota of their own, or environment setup, say so and offer to fix it together now: that is usually faster than a ticket. Draft the ticket when the user still wants one, when the fix needs support, or when the cause stays unclear.
- **Propose one yourself** only when the problem can't be fixed with the user's own privileges, and say why. For example:
  - node faults: `NODE_FAIL`, the same node in several failures, a GPU missing on one node, a drained node that isn't in maintenance;
  - storage and mounts: I/O errors, stale file handles, missing CVMFS or `/groups` mounts, quota changes the user didn't make;
  - access: `Permission denied` on `/groups` (ACLs; `chmod` doesn't help), account or default-account errors;
  - admin actions: `JobHeldAdmin`, restore from backup older than the snapshots, enabling OpenOnDemand app development;
  - a cause that stays unclear after `cbe-triage`.
- Proposing is not creating. Show the draft and create the ticket only after the user approves the text.

### Not a ticket

- **A long queue wait alone.** Explain it with the `cbe-queue` skill. The exception is a suspected scheduler fault, for example:
  - jobs held in `ReqNodeNotAvail` although no reservation covers their time window;
  - `Resources` while the requested nodes are idle and not reserved, for hours;
  - `sbatch` or `squeue` failing with `Socket timed out`, `Unable to contact slurm controller`, or similar errors, repeatedly;
  - jobs stuck in `COMPLETING` for a long time;
  - submissions refused for a queue limit the user didn't reach.
  If the user insists on a ticket about a normal wait, draft it with the evidence from `cbe-queue`, and say the likely answer.
- Problems the user can fix: out of memory, wrong partition or QOS, a wrong path, a full quota of their own, environment setup. Fix them in the session with `cbe-triage` or `cbe-tuning`, and validate the fix with a small test job.
- A missing software installation: request type **CLIP Software** (see the `cbe-software` skill). Account and access requests: **CLIP Account** (below).

## 1. Collect the facts

Gather what you can yourself with read-only commands, in as few SSH calls as possible, and ask the user only for the rest. Don't poll Slurm. Never resubmit a production job to collect evidence.

**For every ticket:**

- what the user expected and what happened, in one or two sentences;
- when it happened: date and time range, and whether it still happens;
- whether it worked before, and what changed since (inputs, script, modules, container, node, maintenance);
- whether it happens every time, sometimes, or once;
- what was tried, with the results.

**Jobs** (failed, killed, hanging, wrong output, or not starting):

| Fact | How to get it |
|---|---|
| Job IDs of the failing jobs, and of a comparable successful job | `sacct -u $USER -S <date> --name=<job-name> -X -o JobID,State,ExitCode,Start,End,NodeList` |
| State, exit code, node, partition, QOS, resources | `sacct -j <id> -o JobID,JobName%30,State,ExitCode,Partition,QOS,NodeList%30,AllocTRES%50,ReqMem,MaxRSS,Elapsed,Timelimit`; `jobinfo <id>` |
| Job script path and submit command | `sacct -j <id> -o WorkDir%80,SubmitLine%120` |
| stdout and stderr paths, and the first error | `scontrol show job <id>` while Slurm still knows the job, else the `#SBATCH --output`/`--error` lines; quote the first error and the last lines |
| Input data location | from the script and its arguments |
| Output and working directory | from the script; whether partial output exists |
| Environment | `module list`, conda environment name and path, container image and tag or digest |
| Minimal reproducer | a script path, its small input, the command to run, and the observed result (see `cbe-triage`, step 5) |

**OpenOnDemand sessions:**

- application (Jupyter, RStudio Server, VS Code, Remote Desktop, shell, files) and the form values: cores, memory, runtime, partition, working directory;
- the session ID and its Slurm job ID from **My Interactive Sessions**;
- the session log shown by OpenOnDemand, especially its last lines;
- what the browser shows (exact message), the browser and operating system, and whether another browser or a private window behaves the same;
- whether a smaller session, or a fresh session after ending the failed one, starts.

**Login and SSH:**

- client operating system, and native terminal or WSL;
- network location: on campus, VPN, or elsewhere;
- `step ssh login vbc-cbe` and `ssh-add -l` results;
- the last relevant lines of `ssh -v <host>`, without keys or certificates.

**Storage and transfers:**

- the path and the operation, and the exact error;
- the job ID, if a job hit it;
- the approximate data size and file count;
- whether a small test file works, and `quota -s` output.

**Suspected scheduler fault:** the pending job IDs with `squeue -j <ids> -o "%.14i %.9P %.10q %.11l %.20V %R"`, the time the state began, the exact error messages from Slurm commands, and whether other users report the same.

Leave a field out when it doesn't apply. When it applies but is unavailable, write "not available" and why. Never guess a job ID, path, or time.

## 2. Write the ticket

Write in English unless the user prefers German. Keep log excerpts short: the first error and the lines around it, not whole files. Point to files by path; support can read them on the cluster.

```text
Summary: <what fails, where, since when; for example "RStudio sessions on OpenOnDemand time out at start since 2026-10-21">

What happened:
<expected vs. actual, in plain words>

When: <date and time range>; still happening: <yes/no>; frequency: <every time / sometimes / once>
Worked before: <yes, until <date>; changed since: ... / no / unknown>

Job IDs: <failing ids>; comparable successful job: <id or "none">
Partition / QOS / resources: <partition, QOS, CPUs, memory, GPUs, time>
Nodes: <NodeList>
Job script: <path>; submitted with: <command>
Logs: <stdout and stderr paths>
Input: <path>
Output / working directory: <path>
Environment: <module list; conda environment; container image and digest>

OpenOnDemand: <application, session ID, form values, browser and OS>   (only for OpenOnDemand)

Error (excerpt):
<the first error and a few lines of context>

Steps taken and findings:
<numbered checks with their results, including what was ruled out>

Minimal reproducer:
<script path, small input, command, observed result; or "not reproducible with a small case" and why>

Why this needs support:
<what the user cannot do themselves: node, storage, permission, admin action, unclear cause>
```

- Never include passwords, keys, certificates, tokens, or the contents of confidential files. Point to paths instead.
- Name only the user's own jobs and files. Don't name other users; describe their effect instead ("another user's jobs filled the queue").
- Show the complete draft to the user, and change it until they approve it.

## 3. Create the ticket

Create it only after the user approves the text.

- With the Atlassian connector (`createJiraIssue`) on `vbc.atlassian.net`:
  - project `ISD` (IT Service Desk);
  - issue type `Support`;
  - request type **CLIP Support** (ID `30`) in the field `customfield_10010`.

  Use **CLIP Account** (ID `29`) for account or access problems, and **CLIP Software** (ID `31`) for software installation requests.
- If the connector isn't available, or the user can't create issues through the API, give the user the final text to paste into the portal form: https://vbc.atlassian.net/servicedesk/customer/portal/5/group/6/create/30 (CLIP Support), `/create/29` (CLIP Account), or `/create/31` (CLIP Software).
- If the user already has a ticket open for the same problem, add the new facts to it as a comment instead of opening another one.
- ÖAW users can also write to contact@clip.science. For quick operational questions, there's the CBE.next MS Teams channel.

After creating it, give the user the ticket key and link. Remind them to keep the logs, scripts, and inputs in place until the ticket is closed, and to answer support's questions on the ticket: unanswered questions close tickets without a fix.

## Details (fetch as Markdown)

- https://docs.vbc.ac.at/research-computing/cbe/troubleshooting-and-support/index.md (what to include)
- https://docs.vbc.ac.at/research-computing/cbe/openondemand-web-applications/index.md (sessions that don't start)
- https://docs.vbc.ac.at/research-computing/ssh-troubleshooting/index.md (SSH and certificate problems)
- https://docs.vbc.ac.at/research-computing/cbe/slurm-jobs/index.md (pending reasons)
- https://docs.vbc.ac.at/research-computing/cbe/change-notes/index.md (maintenance and configuration changes)

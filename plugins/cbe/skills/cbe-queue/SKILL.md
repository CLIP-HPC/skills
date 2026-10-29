---
name: cbe-queue
description: "Explain why a CBE.next Slurm job is pending or waits long to start, and why jobs start in the order they do: job priority, Fair Tree fair-share across holding, institute, lab, and user accounts, usage decay, job age, QOS, backfill, and limits. Use for questions such as why is my job still pending, why is the queue so long, do I get low priority because I submit many jobs, or why did someone else's job start before mine; for pending reasons Priority or Resources, sprio, sshare, and squeue --start estimates. Analyses the user's own pending and recent jobs, including which ones were backfilled. Use cbe-tuning to change resource requests and cbe-triage for failed jobs."
metadata:
  display-name: "CBE queue and priority"
  short-description: "Explain job priority, fair share, and waiting times"
  example-task: "explain why my pending jobs have not started yet."
---

# Explain waiting times on CBE.next

The goal is an explanation of the user's own situation that someone without Slurm background can follow, backed by numbers from their jobs. Not a lecture on scheduling theory, and not a promise of a start time.

The most common misunderstanding: "I submitted many jobs, so I now have low priority." Correct it with the user's own numbers. Priority is a number per job, not a class attached to a person. Pending jobs cost nothing. What lowers fair-share is resources actually used by running jobs in the last few weeks, by the user *and* by their lab, institute, and holding.

## Rules

- **Query sparingly.** Slurm rate-limits users. Run the inspection commands below once, combined into as few SSH calls as possible. No polling, no `watch`. Keep `sacct` windows to 14 days or less (the server refuses more than 60).
- **Read live values.** Weights, QOS, and limits can change. Take them from `sprio -w`, the job's own `QOS`, and `sacctmgr show qos`, not from memory. The values below are a guide to reading them.
- **Never cancel and resubmit** a pending job to "reset" it: it loses the age it has accumulated and starts again at the back. Don't change `--nice` or holds without asking.
- **Other users' jobs:** compare priority components and requests, report counts, and don't name other users or speculate about their work. If the user names a specific job that started earlier, inspecting it is fine.
- Explain, then hand over. Changing requests is the `cbe-tuning` skill. A failed job is `cbe-triage`.
- **A long wait is not a support ticket.** Propose one with the `cbe-ticket` skill only when the evidence points to a scheduler fault: `ReqNodeNotAvail` without a reservation in the job's time window, `Resources` for hours while the needed nodes are idle and unreserved, repeated Slurm controller timeouts, or jobs stuck in `COMPLETING`.

## How CBE.next orders jobs

### 1. Priority: one number per job

Slurm recomputes the priority of every pending job every 5 minutes. It's a weighted sum; `sprio -w` shows the weights. As of 2026-10-22:

| Factor | Weight | What it measures | Practical effect |
|---|---|---|---|
| Fair-share | 100,000 | Recent usage of the user's whole account branch compared to its share | Dominant |
| Age | 20,000 | Time since the job became eligible; grows linearly, full after 7 days | Old jobs catch up |
| QOS | 10,000 | The job's QOS (see below) | `interactive` first, then `rapid`/`short`, `medium`, `long` |
| Job size | 1,000 | Size of the request | Negligible |
| Partition | 500 | Same for `c`, `g`, `m` | No effect |

Each partition is its own queue: a `g` job doesn't compete with a `c` job. Preemption is off: a running job is never stopped for a higher-priority one.

### 2. Fair-share: Fair Tree over the account hierarchy

Accounts form a tree: holding (`vbc`, `oeaw`, ...) → institute (`vbc_imba`, `vbc_gmi`, ...) → lab or group (`vbc_imba_<lab>`, or `vbc_shared_is` under `vbc_gmi`) → users. Names don't always show the parent. Slurm compares each branch only with its siblings:

- Shares at each level: the holdings `vbc` and `oeaw` have fixed shares; VBC institutes have different shares, ÖAW institutes equal ones; all accounts in an institute have equal shares; all users of an account have equal shares. `sshare -l` shows the user's own branch.
- **LevelFS** = share relative to siblings ÷ usage relative to siblings. Above 1 means the branch used less than its share recently (under-served), below 1 means more. `inf` means no recent usage.
- Slurm walks the tree from the top, sorting siblings by LevelFS, and ranks all users. The **FairShare factor** (0–1) is that rank position, so it's relative: 1.0 is the front of the cluster-wide order, near 0 the back. A value of 0.15 does not mean "15% priority"; it means many other users currently rank ahead.
- Consequence: a user who hasn't run anything ranks behind every user of a less busy institute, if their own institute has been busy. Within one lab, the user with less recent usage ranks first. Heavy use by one lab lowers that lab first, and other labs only when the whole institute is over-served.
- **Usage** is what jobs held while running: allocated resources × elapsed time, converted to billing units per partition. It counts the allocation, not what the program used, and actual run time, not the requested `--time`. With `PriorityFlags=MAX_TRES`, a job is billed by its largest weighted resource per node. Read the weights with `scontrol show partition <p> | grep TRESBillingWeights`. On 2026-10-22: on `c`, 1 CPU or about 3.7 GB memory is one unit; on `g`, a full B200 counts like 24 CPUs and a MIG slice like about 3.4; on `m`, about 48 GB of memory is one unit. Over-requested memory or GPUs therefore cost fair-share even when idle. A job's rate is the `billing=` value in `ReqTRES` (`scontrol show job <id>`) or `AllocTRES` (`sacct`); for example, 2 CPUs with 200 GB on `c` bill 53 units per hour, not 2.
- Usage decays with a half-life of 7 days and is never reset: heavy use a week ago counts half, two weeks ago a quarter.

### 3. QOS tiers

Each partition has its own QOS levels. Jobs without `--qos` get `<p>_short`; users choose `--qos=rapid`, `medium`, `long`, or `interactive` themselves, and a submit hook adds the partition prefix. Read the tiers with:

```bash
sacctmgr -P show qos format=Name,Priority,MaxWall,MaxTRESPerUser%60,GrpTRES%60
```

On 2026-10-22: `interactive` (up to 12 h, small per-user caps) has QOS priority 1500, `<p>_rapid` (up to 1 h) and `<p>_short` (up to 8 h) 1000, `<p>_medium` (up to 2 days) 500, and `<p>_long` (up to 14 days) 100. Longer tiers also cap how much one user, and the whole tier, may run at once. A job pending with a `QOSMax*PerUser` reason is waiting for the user's *own* jobs to finish, not for priority. A `QOSGrp*` reason means the tier is full for everyone.

### 4. Scheduling: priority order, then backfill

- The main scheduler tries pending jobs in priority order. If the top job doesn't fit yet, it gets reason `Resources` and Slurm reserves the nodes it will need. Jobs behind it get reason `Priority`.
- The backfill scheduler runs about every 2 minutes. It plans up to 30 days ahead in 5-minute steps from the **time limits** of running jobs, and starts a lower-priority job early if it fits in a gap without delaying the planned start of any higher-priority job. It tests up to 200 pending jobs per user per cycle.
- So a small job with a short, accurate `--time` often starts before larger or longer jobs with higher priority, and that's intended: it uses cores that would otherwise sit idle while a big job waits for a whole node to drain.
- Batch jobs never start at the instant of submission (`defer_batch`); a few seconds of wait on an idle cluster is normal.
- `squeue --start` estimates assume every running job uses its full time limit. Estimates usually move earlier as jobs finish early, and can move later when higher-priority jobs arrive. The estimate isn't a commitment.
- `ReqNodeNotAvail` usually means a maintenance or other reservation: the job's time limit would run into it. It starts after the reservation, or earlier with a shorter `--time` that ends before it.

## Workflow

### 1. Collect, in one SSH call

```bash
squeue --me -t PD -o "%.14i %.9P %.10q %.11l %.5C %.8m %.16b %.8Q %.20V %.20S %R"
sprio -w
sprio -l -u $USER
sacctmgr -nP show user $USER withassoc format=DefaultAccount,Account
```

For the account used by the pending jobs (`squeue -o %a`, or the default account), show the chain from the root down to the user, and the lab's users. The filter follows the tree indentation, because account names don't always contain their parent's name (`vbc_shared_is` sits under `vbc_gmi`). Report every level of the chain:

```bash
lab=<account>
sshare -l -a -P -o Account,User,RawShares,NormShares,EffectvUsage,LevelFS,FairShare \
  | awk -F'|' -v lab="$lab" -v me="$USER" 'NR==1 {print; next}
      {a=$1; d=match(a, /[^ ]/); gsub(/^ +/, "", a)}
      $2 == "" {up[d]=$0; if (a == lab) for (i=1; i<=d; i++) if (i in up) print up[i]}
      a == lab && $2 == me'
sshare -l -a -A "$lab" -o User%25,RawUsage,EffectvUsage,LevelFS,FairShare
```

Queue context for the partition of the job in question (the answer reports counts, not names):

```bash
squeue -h -t PD -p <partition> --sort=-p -o "%.14i %.8Q %.10q %.11l %.5C %.8m %.16b %R"
showpartitions
```

And the user's recent history, with waits and how each job was started:

```bash
sacct -X -u $USER -S now-14days -E now -P -n \
  -o JobID,Partition,QOS,Eligible,Start,Timelimit,Elapsed,AllocTRES%60,Priority,Flags \
  | awk -F'|' 'function t(s){gsub(/[-T:]/, " ", s); return mktime(s)}
      $5 ~ /^[0-9]/ {w = t($5) - t($4); print $0 "|wait_s=" w}'
```

`Flags` shows `SchedMain` (started by the main scheduler in priority order), `SchedBackfill` (started by backfill), or `SchedSubmit` (started at submission). Wait is measured from `Eligible`, so time spent waiting on a dependency or `--begin` isn't counted.

### 2. Find backfill examples that benefited the user

Pick up to three of the user's `SchedBackfill` jobs with a non-trivial wait or a busy period, preferably recent. For each, count older jobs with a higher priority that were still pending in the same partition when it started:

```bash
t=$(date -d "<Start> - 1 second" +%FT%T)
sacct -a -X -r <partition> -s PD -S "$t" -E "$t" -n -P -o Submit,Priority \
  | awk -F'|' -v s="<Eligible>" -v p="<Priority>" '$1 < s && $2 > p' | wc -l
```

A count above zero means the job started ahead of that many older, higher-priority jobs: concrete evidence that backfill helped this user. Zero means the cluster simply had room; say so rather than overstating it. Stop after three checks; each is a query on the shared scheduler.

### 3. Diagnose

Go through these in order and stop at the first that explains most of the wait:

1. **Not waiting for priority at all:** reasons such as `ReqNodeNotAvail`, `Dependency`, `JobHeld*`, `BeginTime`, `QOSMax*`, `QOSGrp*`, `Assoc*`. Explain the reason and what ends it.
2. **Fair-share:** in the chain, find the highest level with LevelFS below 1. That level explains the factor: the institute, the lab, or the user. Say which, and that it decays by half every 7 days.
3. **Request shape:** whole-node CPU requests, large memory, full B200 GPUs, or the `m` partition need a node to drain. Compare with what is pending ahead and what `showpartitions` reports free.
4. **Time limit and QOS:** long limits miss backfill gaps, and the `medium` and `long` QOS rank lower and have tighter caps. Compare the limit with `Elapsed` of similar finished jobs.
5. **Just a busy partition:** many higher-priority pending jobs ahead and few free cores. Age will lift the job over the following days.

For "someone else's job started before mine", compare the two jobs on each point above: partition and request size, time limit and QOS, `Flags` (backfill?), eligible time (age), and the FairShare component from `sprio -l -j <id>` while pending, or `Priority` from `sacct` after the start.

### 4. Explain

Use this structure, in plain language, with the user's numbers:

1. **Short answer**, two or three sentences: why this job is waiting and the single biggest factor.
2. **What "priority" means here:** one sentence that it's a per-job number recalculated every 5 minutes, and that the number of submitted jobs doesn't lower it.
3. **The job's priority, broken down** from `sprio`, each part as a share of its maximum, for example "fair-share 42,489 of 100,000: your institute used more than its share in the last two weeks".
4. **Where the user stands in the tree:** holding, institute, lab, user, each with "used more / less than its share recently". If the user personally used little but their lab or institute used a lot, say so explicitly: this is the usual surprise.
5. **The queue around the job:** number of higher-priority jobs pending in the same partition, and whether the request needs a fully free node.
6. **What already worked in their favour:** how many of their recent jobs started through backfill, with one to three concrete job IDs, their wait, and how many older higher-priority jobs they overtook. Also mention age: their pending job gains priority every hour it waits, up to 7 days.
7. **What they can do**, only where it applies: a time limit close to the real runtime (measured with `sacct`), smaller requests that match measured use (hand off to `cbe-tuning`), the right `-A` account for the work when they belong to several, job arrays instead of thousands of single jobs, and waiting rather than resubmitting.

Avoid unexplained jargon. When a Slurm term is needed (backfill, fair-share, QOS), define it in a short clause the first time.

## Details (fetch as Markdown)

https://docs.vbc.ac.at/research-computing/cbe/cluster-resources/index.md (priority, Fair Tree example, backfill, maintenance) and https://docs.vbc.ac.at/research-computing/cbe/slurm-jobs/index.md (pending reasons, site tools). Upstream: https://slurm.schedmd.com/fair_tree.html, https://slurm.schedmd.com/priority_multifactor.html, and https://slurm.schedmd.com/sched_config.html.

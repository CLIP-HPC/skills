---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

My job on CBE.next got killed overnight. Can you tell me what happened and what to change?

slurm-48211.out ends with:
```
slurmstepd: error: Detected 1 oom_kill event in StepId=48211.batch. Some of the step tasks have been OOM Killed.
```
sacct -j 48211 --format=JobID,State,ReqMem,MaxRSS,Elapsed:
```
48211        OUT_OF_MEMORY   16G            02:41:07
48211.batch  OUT_OF_MEMORY   16G  16.2G     02:41:07
```

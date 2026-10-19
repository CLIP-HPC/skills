---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

This CBE.next job works but it takes forever and I think I'm wasting resources. Can we make it faster?

Script requests: --cpus-per-task=32 --mem=256G --time=2-00:00:00
jobeff output from the last run:
```
CPU Efficiency: 9.4% of 3-02:13:20 core-walltime
Memory Efficiency: 11.2% of 256.00 GB
Elapsed: 05:49:10
```

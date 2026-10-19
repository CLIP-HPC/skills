---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

Adapt this sbatch script so it runs on CBE.next. Don't submit anything, just give me the revised script.

```bash
#!/bin/bash
#SBATCH --job-name=align
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
module load bwa/0.7.17
bwa mem -t 8 ref.fa reads_1.fq reads_2.fq > out.sam
```

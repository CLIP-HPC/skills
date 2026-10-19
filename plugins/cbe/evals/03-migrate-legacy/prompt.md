---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

We still run this on the old CBE cluster (clip-login-1). Please port it to CBE.next.

```bash
#!/bin/bash
#SBATCH --qos=c_short
#SBATCH --mem=8G
cd /scratch-cbe/users/jdoe/project
ml load samtools/1.9-foss-2018b
samtools sort in.bam -o sorted.bam
```

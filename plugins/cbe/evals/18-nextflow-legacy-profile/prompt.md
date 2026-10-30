---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

On the old CBE cluster I ran `nohup nextflow run nf-core/rnaseq -profile cbe --input samples.csv --outdir results &` on the login node. How do I run the same pipeline on CBE.next?

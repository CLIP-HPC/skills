---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

My ROOT ntuples (about 2 TB, files of 3-5 GB each) are on EOS under /eos/vbc/group/mygroup/ntuples. I want to process them in Slurm array jobs on CBE.next. Should I read them through /eos directly or copy them, and how?

---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

I want to fine-tune a small PyTorch model on CBE.next. It needs one whole GPU with at least 40 GB; an A100 or a B200 is fine, whichever starts first. Write me the sbatch script for `python train.py`, but don't submit it.

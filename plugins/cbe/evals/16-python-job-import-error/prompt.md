---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

My script runs fine on the CBE.next login node after `source ~/myenv/bin/activate` (made with python -m venv, then pip install scipy numpy). But in my sbatch job it fails with `ModuleNotFoundError: No module named 'scipy'`. The job script just has `#SBATCH` lines and `python run.py`. How do I make this work reliably?

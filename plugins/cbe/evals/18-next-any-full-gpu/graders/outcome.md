---
type: llm
weight: 1
---

The response gives an sbatch script for partition `g` that requests one GPU and limits it to whole A100 or B200 GPUs with a feature constraint, such as `--gres=gpu:1 --constraint="fullgpu&(a100|b200)"` or an equivalent `--constraint` using `fullgpu`, `a100`, and `b200`. It does not use `--nodelist` or `--exclude` to pick nodes, does not leave an untyped `--gres=gpu:1` without a constraint, and does not request a MIG slice or an RTX 6000. It sets `--time`, `--cpus-per-task`, and `--mem` explicitly and does not claim to have submitted the job.

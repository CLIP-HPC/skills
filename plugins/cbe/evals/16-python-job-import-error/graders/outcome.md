---
type: llm
weight: 1
---

The response explains that the job does not use the virtual environment and fixes the job script to use it explicitly (activating it by path inside the script, calling the environment's Python by path, or `uv run` in a uv project). It recommends tracking the dependencies in a file in the project (such as `pyproject.toml` with `uv.lock`, or a pinned requirements file) so the environment can be rebuilt, and does not recommend `pip install --user` or putting activation into `~/.bashrc`.

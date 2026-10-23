---
type: llm
weight: 1
---

The response proposes a hand-written `environment.yml` with explicit versions and the conda-forge and bioconda channels (no `defaults`), committed to the git repository, plus a lock file such as `conda-lock.yml` produced by `conda export` (or an explicit file) that is also committed. It creates the environment with `conda` (or `mamba` with `-p`), not `mamba -n`, outside `/scratch`, and changes packages by editing the file rather than by ad-hoc `conda install` or `pip install`. It does not tell the user to run `conda init`.

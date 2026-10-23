---
name: cbe-env
description: "Set up, repair, and maintain reproducible Python and conda environments on CBE.next with uv, conda, or mamba (global Miniforge): a project in a git repository whose dependencies are tracked in pyproject.toml and uv.lock, or environment.yml and conda-lock.yml, then built, used in Slurm jobs and Jupyter kernels, updated, and rebuilt from those files. Use for creating a venv or conda environment, environment.yml, requirements.txt, pip installs, conda init, ~/.conda filling the $HOME quota, broken, unsolvable, or drifting environments, ModuleNotFoundError only in jobs, ~/.local site-packages leaking in, and turning an existing environment into tracked files. Use cbe-software to find whether a tool already exists as a module or container, and cbe-migrate for moving environments from legacy CBE."
metadata:
  display-name: "CBE environments"
  short-description: "Reproducible uv and conda environments in git"
  example-task: "set up a tracked conda environment for this analysis project."
---

# Reproducible environments on CBE.next

Environments that grow by ad-hoc `pip install` and `conda install` end up unsolvable, fill the `$HOME` quota, and can't be rebuilt, because nobody knows what they contain. The fix is to treat the environment as a disposable build product of files in git:

- **The spec file is the source of truth.** You edit `pyproject.toml` or `environment.yml`, never the environment. Every change goes through the file.
- **A lock file records the exact result**, so the same environment can be rebuilt on any day: `uv.lock` or `conda-lock.yml`.
- **The environment directory is never committed, copied, or patched.** When it breaks or drifts, delete it and rebuild from the lock. That takes about a minute.

Facts below reflect CBE.next as of 2026-10-23 (uv 0.11, conda 26.7 with mamba 2.9 in a read-only Miniforge, no pixi or micromamba). Prefer what the cluster reports.

## Choose the tool

| The project needs | Use | Tracked files |
|---|---|---|
| Only Python packages from PyPI | `uv` project | `pyproject.toml`, `uv.lock`, `.python-version` |
| R, bioinformatics tools, compilers, or C libraries, possibly with Python | conda from conda-forge and Bioconda | `environment.yml`, `conda-lock.yml` |
| One existing command-line tool | No environment: a module or a Galaxy BioContainer (see `cbe-software`) | the module name or image path |

- Check `cbe-software` first when the user needs a single tool such as `samtools` or `STAR`. A module or container needs no maintenance at all.
- Don't use mamba or micromamba as separate tools. `conda` on CBE.next already uses the libmamba solver.
- Never Anaconda, Miniconda, or the `defaults`, `main`, `r`, `msys2`, or `anaconda` channels (license terms; see `cbe-software`). Don't install your own conda.

## Ground rules that prevent most support tickets

These come from recurring HPC Servicedesk tickets. Follow them in every setup and point them out when the user's current setup breaks one.

1. **Don't run `conda init`, and don't put `conda activate`, `module load`, or `PATH` exports in `~/.bashrc`.** Init blocks break OpenOnDemand Jupyter and RStudio sessions ("Spawn failed", blank RStudio) and hide modules. Activate explicitly in each shell or job.
2. **Watch the `$HOME` file-count limit, not just its size.** Conda environments and `~/.conda/pkgs` hold tens of thousands of files each. Run `myquota` before creating an environment, run `conda clean --all -y` after each build, and put large or shared environments in `/groups/<group>`. Never put environments on `/scratch` (files deleted after 28 days).
3. **No `pip install --user`, ever.** Packages in `~/.local/lib/python3.*` load into every environment and kernel and break them. Use the environment's own `python -m pip`, or better, the spec file.
4. **One project, one environment.** Don't reuse a big "everything" environment across projects; it becomes unsolvable.
5. **Rebuild instead of repairing.** If a solve fails or imports break after an install, fix the spec file and rebuild from scratch.
6. **Build on CBE.next.** Environments from legacy CBE, a laptop, or another cluster aren't portable: rebuild them from their spec files here.
7. **Don't load modules that provide Python, R, GCC, or CUDA into a process that uses an environment.** Their libraries shadow the environment's (`GLIBC_...` or `CXXABI_...` not found).

## Before you start: check the user's setup

Collect everything in one SSH call and read it before proposing changes:

```bash
myquota
grep -n -E 'conda|mamba|>>> conda initialize|PYTHONPATH|LD_LIBRARY_PATH' ~/.bashrc ~/.bash_profile ~/.profile 2>/dev/null
cat ~/.condarc 2>/dev/null
ls ~/.local/lib/ 2>/dev/null
du -sh --inodes ~/.conda/pkgs ~/.conda/envs ~/.cache/uv ~/.cache/pip 2>/dev/null
conda env list
```

Report what breaks the ground rules and propose the fix, but edit the user's dotfiles only after they agree:

- a `conda initialize` block in `~/.bashrc`: run `conda init --reverse`, or delete the block;
- `defaults` or `anaconda` channels in `~/.condarc`: remove them;
- `~/.local/lib/python3.*`: rename it (`mv ~/.local/lib/python3.12 ~/.local/lib/python3.12.disabled`) rather than deleting it, and set `export PYTHONNOUSERSITE=1` in job scripts;
- large caches: `conda clean --all -y`, `uv cache prune`.

## Set up a project

Work in a git repository: the user's existing project, or a new one created with `git init`. Location:

- Code and small projects: `$HOME` or `/groups/<group>/<user>/<project>`.
- Environments larger than a few GB, or used by the whole group: `/groups/<group>`.
- Never `/scratch`.

Commit the spec and lock files after every successful change, with the change in the message ("add scanpy 1.11"). The git history then answers what changed when an analysis result changes.

### uv (Python only)

```bash
cd <project>
uv init --bare --python 3.12     # writes pyproject.toml; use plain `uv init` for a new app with main.py
```

Add to `pyproject.toml`, so every rebuild uses a uv-managed Python:

```toml
[tool.uv]
python-preference = "only-managed"
```

Without it, uv picks the first Python on `PATH`, which on CBE.next is the OS or the EESSI compatibility layer's interpreter. The environment then breaks when that interpreter changes in an OS or EESSI stack update. Managed interpreters go to `~/.local/share/uv/python`.

```bash
uv python pin 3.12               # writes .python-version
uv add numpy pandas              # adds to pyproject.toml, updates uv.lock and .venv
uv add --dev ipykernel pytest    # tools that the analysis doesn't import
uv run python analysis.py        # runs in .venv after checking it matches uv.lock
```

- Add and remove packages only with `uv add` and `uv remove`. Never `uv pip install` or `pip install` into a project environment: the lock file doesn't record them.
- Rebuild exactly from the lock: `uv sync --locked` (fails if `pyproject.toml` and `uv.lock` disagree).
- Upgrade on purpose: `uv lock --upgrade-package <name>` or `uv lock --upgrade`, then `uv sync`, test, and commit.
- If uv warns that it can't hardlink files (the cache in `$HOME` and the project in `/groups` are separate filesystems), `export UV_LINK_MODE=copy` silences it.
- Single scripts don't need a project. Use `uv add --script script.py <pkg>` to write inline metadata, and `uv run script.py`.

`.gitignore`:

```gitignore
.venv/
__pycache__/
```

### conda (Python, R, and non-Python tools)

Write `environment.yml` by hand. List only what the project imports or calls directly, with a version for each:

```yaml
name: my-analysis
channels:
  - conda-forge
  - bioconda
dependencies:
  - python=3.12
  - samtools=1.21
  - r-base=4.4
  - pandas=2.2
```

Keep `conda-forge` before `bioconda`, and add `bioconda` only when the project uses it. Don't write a `prefix:` line.

Create the environment inside the project directory, with strict channel priority, which Bioconda requires:

```bash
CONDA_CHANNEL_PRIORITY=strict conda env create -p ./.conda -f environment.yml
conda export -p ./.conda --file conda-lock.yml
conda clean --all -y
```

For a large environment, use `-p /groups/<group>/envs/<project>` instead of `./.conda`, and write that path in the project's README.

- `conda-lock.yml` records every package with its exact build. Rebuild with `conda env create -p ./.conda -f conda-lock.yml`.
- Change packages by editing `environment.yml`, then apply the change and re-lock:

    ```bash
    CONDA_CHANNEL_PRIORITY=strict conda env update -p ./.conda -f environment.yml --prune
    conda export -p ./.conda --file conda-lock.yml
    ```

    If the update fails or takes very long, delete `./.conda` and create it again from `environment.yml`.
- Never `conda install` or `pip install` into the environment directly. The change is gone after the next rebuild.
- Don't use `conda export --from-history` to write `environment.yml`. It drops the `bioconda` channel and all pip packages, and it writes a `prefix:` line. It only helps to rescue an untracked environment (below).
- Use `mamba` only with a path: `mamba env create -p ./.conda -f environment.yml`. `mamba -n <name>` fails on CBE.next (read-only shared installation).

**pip packages in a conda environment.** Prefer the conda-forge build of a package. For a package only on PyPI, add a `pip:` section with an exact version (`- pip` and `- pip: [some-tool==1.4.2]`). `conda-lock.yml` doesn't record pip packages: after rebuilding from the lock, install them with `conda run -p ./.conda python -m pip install --no-deps <pkg>==<version>`. If most packages come from PyPI, the project is better off with uv.

`.gitignore`:

```gitignore
.conda/
```

## Use the environment

Activate by path in every job and session. Name-based activation and `source ~/.bashrc` in job scripts are the usual cause of "ModuleNotFoundError only in sbatch".

uv:

```bash
#!/usr/bin/env bash
#SBATCH --job-name=analysis
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
export PYTHONNOUSERSITE=1
cd /groups/<group>/<user>/<project>
uv run --locked python analysis.py
```

conda:

```bash
#!/usr/bin/env bash
#SBATCH --job-name=analysis
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
export PYTHONNOUSERSITE=1
eval "$(conda shell.bash hook)"
conda activate /groups/<group>/<user>/<project>/.conda
which python
python analysis.py
```

Before the first real job, run one short test job that imports the main packages. For GPU packages, test on the GPU partition: `python -c "import torch; print(torch.cuda.is_available())"`.

### Jupyter kernels in OpenOnDemand

Add `ipykernel` to the spec (`uv add --dev ipykernel`, or `- ipykernel` in `environment.yml`; for R, `- r-irkernel`), rebuild, then register it once under a short name without slashes:

```bash
uv run python -m ipykernel install --user --name <project> --display-name "Python (<project>)"
conda run -p ./.conda python -m ipykernel install --user --name <project> --display-name "Python (<project>)"
```

The kernel spec in `~/.local/share/jupyter/kernels/<project>/` points to the environment's Python by path, so it keeps working after a rebuild in the same place. Don't install packages from a notebook cell (`!pip install`): add them to the spec file.

## Turn an existing, untracked environment into tracked files

Don't copy or repair the old environment. Recover its spec, rebuild, and compare:

1. Find what the user actually asked for:

    ```bash
    conda export -n <old> --from-history        # conda packages requested by name
    conda list -n <old> | grep pypi             # packages installed with pip
    conda list -n <old> --show-channel-urls | awk '{print $4}' | sort | uniq -c   # channels in use
    ```

    For a plain venv: `<venv>/bin/python -m pip list --not-required` lists the top-level packages.
2. Check the project's code for its imports (`rg -n '^\s*(import|from) ' --type py`, `library(` for R), and keep only packages the project uses. Ask the user about unclear ones.
3. Write `pyproject.toml` or `environment.yml` with versions close to the old environment (`conda list -n <old> <pkg>`). Replace `defaults` with `conda-forge`.
4. Build the new environment, run the project's tests or a known analysis, and compare the results.
5. Commit the files. Remove the old environment only after the user confirms (`conda env remove -n <old>`), then run `conda clean --all -y`.

## Maintenance

- Rebuild any time: delete `.venv` or `.conda` and rebuild from the lock. Do this when an import breaks, after a CBE.next software stack change, or when the project moves to another directory.
- Upgrade deliberately, for example once per project phase: update versions in the spec, rebuild, test, commit spec and lock together.
- Clean caches: `conda clean --all -y`, `uv cache prune`. Remove environments you no longer use; `conda env list` shows them.
- Record the environment in the results: the git commit of the project, or at least `uv.lock` or `conda-lock.yml`, next to the outputs.

## When it still fails

- `CondaError: Unable to create prefix directory`, `No space left on device`, or `Disk quota exceeded`: `myquota` (files and size), then clean caches or move the environment to `/groups`.
- Solver runs very long: remove unused packages and loose pins from the spec, check that `defaults` isn't listed anywhere, and create it again from scratch. A large solve needs memory; don't run it in a small OpenOnDemand session.
- `GLIBC_*` or `CXXABI_*` not found: a module or a build from another system is mixed in. Run `module purge` and rebuild on CBE.next.
- Other failures: diagnose with `cbe-triage`. A problem the user can't fix with their own privileges goes to `cbe-ticket`.

## Details (fetch as Markdown)

- https://docs.vbc.ac.at/research-computing/cbe/python-and-conda/index.md
- https://docs.vbc.ac.at/research-computing/cbe/openondemand-web-applications/index.md (custom Jupyter kernels)
- https://docs.vbc.ac.at/research-computing/cbe/storage-and-data/index.md (quotas)
- Upstream: https://docs.astral.sh/uv/concepts/projects/, https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html, https://bioconda.github.io/

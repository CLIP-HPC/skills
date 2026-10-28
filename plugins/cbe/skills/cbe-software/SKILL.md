---
name: cbe-software
description: "Find, load, install, or run software on CBE.next using Lmod modules (EESSI/2025.06 and CBE/2025.06 stacks, module spider, collections), CVMFS repositories (Galaxy BioContainers, Refgenie reference data, CERN unpacked images), SBGrid in /programs, Apptainer, uv Python environments, or conda from the global Miniforge (conda-forge only, never Anaconda or Miniconda). Use when asking whether a tool is available, choosing a software source, resolving an environment, building a container outside the cluster, running bring-your-own-license software such as MATLAB, or requesting missing software."
metadata:
  display-name: "CBE software"
  short-description: "Find and configure software on CBE.next"
  example-task: "find a suitable software environment for this workflow."
---

# Software on CBE.next

Facts below reflect the docs as of 2026-10-19 and the tools in `/software/system/utils/bin` as of 2026-10-23. Prefer what the cluster reports (`module spider`, directory listings) over this file.

## Where software comes from

| Source | Location | What it provides |
|---|---|---|
| EESSI stack | `module avail` (`EESSI/2025.06`) | Community-built scientific software |
| CBE site stack | `module avail` (`CBE/2025.06`) | Site builds with EasyBuild, optimised for the AMD Zen 5 nodes |
| Galaxy BioContainers | `/cvmfs/singularity.galaxyproject.org/all/` | Ready-to-run Apptainer images for over 100,000 Bioconda tool versions |
| Galaxy reference data | `/cvmfs/data.galaxyproject.org` | Reference genomes and prebuilt aligner indexes |
| Refgenie genomes | `/cvmfs/refgenomes-databio.galaxyproject.org` | Refgenie-managed genome assets |
| CERN unpacked images | `/cvmfs/unpacked.cern.ch` | Selected images mirrored from Docker Hub, GitHub, Quay, NVIDIA, and others |
| Grid experiment software | `/cvmfs/<repo>`, for example `alice.cern.ch`, `atlas.cern.ch`, `cms.cern.ch` | HEP experiment stacks and conditions data; for setup, use the `grid-software` skill from the `grid` plugin, if installed |
| SBGrid | `/programs` | Structural biology collection |
| Curated reference data | `/resources` | Genomes and indexes |
| Your own | containers you pull or build; `uv` or conda environments; binaries in `$HOME` or `/groups` | Anything not provided above |

## Command-line tools on `PATH`

`/software/system/utils/bin` is on every user's `PATH`, with no module needed. Run `ls /software/system/utils/bin` for the current set and `<tool> --version` for versions.

| Purpose | Tools |
|---|---|
| Search files and code | `rg` (ripgrep), `fd` |
| Git and GitHub | `gh`, `lazygit` |
| Coding agents | `claude` (Claude Code), `codex` (Codex CLI), `herdr` (terminal workspace for agent sessions) |
| Data transfer | `rclone`, `azcopy` (see the `cbe-data` skill) |
| Environments | `uv`, `conda` and `mamba` (Miniforge), `apptainer` |
| Interactive, for the user's terminal | `btop` and `btm` (process monitors), `fzf`, `zoxide`, `yazi` (file manager) |
| Cluster and storage helpers | `jobinfo`, `jobeff`, `myquota`, `stage`, and others (see the `cbe-next` skill) |

- Use these instead of installing your own copy into `$HOME` or a conda environment.
- Prefer `rg` and `fd` over `grep -r` and `find`, but give them a narrow starting directory. Never sweep all of `/groups`, `/scratch`, or `/cvmfs`: that loads shared storage for everyone.
- `btop`, `btm`, `lazygit`, `yazi`, and `fzf` need an interactive terminal. Suggest them to the user; don't run them from a non-interactive agent shell.

Not provided: Anaconda, Miniconda, and micromamba; Podman; a MATLAB module; building Apptainer images from a definition file on CBE.next (*not available yet*); `xrdcp`/`xrdfs` and the VOMS tools may not be installed yet (COPS-232; see the `grid` plugin).

## Search in this order

Stop at the first source that has a suitable version. For a general command-line tool, first check whether it's already on `PATH`: `command -v <name>`.

1. **Modules.**
   - `module spider <name>` searches the whole hierarchy, case-insensitively, and finds partial names.
   - `module spider <name>/<version>` shows which prerequisite (compiler or toolchain) modules to load first.
   - `module avail` only lists what's loadable right now.
2. **Galaxy BioContainers**, for bioinformatics tools from Bioconda:

   ```bash
   ls /cvmfs/singularity.galaxyproject.org/all/ | grep '^<tool>:'
   ```

   Image names follow `<tool>:<version>--<build>`.
3. **SBGrid**, for structural biology: `source /programs/sbgrid.shrc` (`.cshrc` for csh/tcsh), then call the program.
4. **CERN unpacked images**, for images from public registries: `ls /cvmfs/unpacked.cern.ch/<registry>/<namespace>/`. Only images on CERN's mirror list are there.
5. **Pull a container yourself**, for example `apptainer pull docker://...`.
6. **Python packages:** `uv`. **Packages with non-Python dependencies** (R, bioinformatics tools): a conda environment from conda-forge and Bioconda.
7. **Still missing:** ask the user whether to request an installation. That's an IT Service Desk request of type **CLIP Software**: project `ISD`, request type ID `31`, portal form https://vbc.atlassian.net/servicedesk/customer/portal/5/group/6/create/31. Draft the request with the application, version, workflow, resource needs, and any license restrictions, show it to the user, and create it only after they approve.

**CVMFS gotcha:** repositories mount on first access, so `ls /cvmfs` can look nearly empty. List the full repository path directly.

**Reference data:** before downloading a genome or index, check `/resources`, `/cvmfs/data.galaxyproject.org`, and `/cvmfs/refgenomes-databio.galaxyproject.org`.

## Use modules

```bash
module load <name>/<version>
module list
which <executable>
<executable> --version
```

- Always give an explicit version.
- `EESSI/2025.06` and `CBE/2025.06` are sticky: `module purge` keeps them. To unload one deliberately, use `module --force unload EESSI`.
- In job scripts, run `module purge` and then the `module load` lines, so the job doesn't depend on the interactive shell. Never load application modules in `.bashrc`.
- Don't mix compiler or MPI toolchains unless the application documents that it's supported.
- Collections replace `.bashrc` loading:
  - `module save <name>` and `module restore <name>`;
  - `module savelist` lists them and `module describe <name>` shows one;
  - they're stored in `~/.lmod.d`;
  - re-check them after a stack update.
- Opting out of EESSI and the site stack (`touch ~/.noeessi`, then a new login) removes all of these modules. Only suggest it if the user explicitly wants a bare environment.

## Use containers

- CBE.next runs containers with Apptainer 1.5.3 only (`singularity` is the same binary). There's no Podman.
- Run containers inside Slurm jobs, not on the login node.

```bash
export APPTAINER_CACHEDIR="${SCRATCHDIR}/apptainer-cache"
export APPTAINER_TMPDIR="${SCRATCHDIR}/apptainer-tmp"
mkdir -p "${APPTAINER_CACHEDIR}" "${APPTAINER_TMPDIR}"
apptainer pull docker://docker.io/library/python:3.13-slim
apptainer exec python_3.13-slim.sif python --version
```

- Put the cache and build temp on `$SCRATCHDIR`, so they don't fill the `$HOME` quota. Keep long-lived `.sif` files in `$HOME` or `/groups`, because `/scratch` deletes files after 28 days.
- Home and the working directory are bind-mounted automatically. Bind other paths explicitly: `--bind /scratch/users/${USER}` or `--bind /groups/<group>`.
- Images under `/cvmfs` run directly. Don't copy them.
- GPUs: use `--nv`. Never use `--cleanenv` on GPU nodes; it drops `CUDA_VISIBLE_DEVICES`. If a clean environment is needed, use `--env CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES}"`.

### Use your own image

Apptainer runs images from any OCI registry, such as Docker Hub, GitHub, or Quay. You can't build images from a definition file on CBE.next yet. Instead:

- build the image outside CBE.next, push it to a registry, and pull it: `apptainer pull my-tool_1.0.sif docker://<registry>/<namespace>/my-tool:1.0`;
- or let IT build it from a Git repository: see the "Singularity image builds" and "Docker image builds" pages under `hosting-publishing/build-automation/` in the docs.

## Python and conda

For a project environment that should stay reproducible (tracked in git with `pyproject.toml` and `uv.lock`, or `environment.yml` and `conda-lock.yml`), and for repairing a grown or broken environment, use the `cbe-python` skill. The commands below are the quick, untracked form from the docs.

### uv

- `uv` 0.11 is the tool for Python-only projects. Use `uv venv ~/venvs/<name>`, then `source ~/venvs/<name>/bin/activate`, then `uv pip install <pkgs>`. For one-off scripts, use `uv run --with <pkg> python script.py`.
- Create environments in `$HOME` or `/groups`, never on `/scratch`.
- Record them with `uv pip freeze > requirements.txt`.
- For software with complex native dependencies, use conda, a container, or a BioContainer image instead.
- Jupyter kernels for OpenOnDemand: run `uv pip install ipykernel`, then `python -m ipykernel install --user --name <name> --display-name "Python (<name>)"`.

### conda

A global Miniforge (conda 26.7, mamba 2.9) is on the `PATH` through the `CBE` module. Only the conda-forge channel is configured.

- **Never use Anaconda, Miniconda, or the `defaults`, `main`, `r`, `msys2`, or `anaconda` channels.** The Anaconda Repository needs a paid license for organizations with more than 200 employees or contractors, unless an academic or non-profit and research policy applies. Don't install them, don't add those channels, and replace `defaults` with `conda-forge` in exported files. conda-forge and Bioconda are fine.
- **Use `conda`, not `mamba -n`.** `mamba create -n <name>` and `mamba install -n <name>` look only in the read-only shared installation and fail (`Permission denied` or `No prefix found`). `conda` uses the same libmamba solver. If the user prefers mamba, pass the full environment path with `-p ~/.conda/envs/<name>` to `mamba create` and `mamba install`; `conda activate <name>` still finds it by name.
- Create and activate:

    ```bash
    conda create -n <name> python=3.12 <packages>
    conda create -n <name> -c conda-forge -c bioconda <tools>
    eval "$(conda shell.bash hook)"
    conda activate <name>
    ```

- Don't run `conda init`: it edits `~/.bashrc` and activates `base` at every sign-in, which can hide modules. Use `eval "$(conda shell.bash hook)"` where activation is needed.
- Environments go to `~/.conda/envs`, packages to `~/.conda/pkgs` (`conda clean --all` frees space). Shared group environments: `conda create -p /groups/<group>/envs/<name> ...`. Never on `/scratch`.
- In jobs: `eval "$(conda shell.bash hook)"` and `conda activate <name>`, or `conda run -n <name> <command>`.
- Don't load modules for tools the active environment also provides (Python, R): the first one on `PATH` wins.
- Jupyter kernel: `conda install -n <name> ipykernel`, then `conda run -n <name> python -m ipykernel install --user --name <name> --display-name "Python (<name>)"`.

Export and re-create (never copy an environment directory; conda writes its path into the files):

| Goal | Export | Re-create |
|---|---|---|
| Portable, only requested packages | `conda export -n <name> --from-history --file environment.yml` | `conda env create -n <name> -f environment.yml` |
| Same versions, any build | `conda export -n <name> --no-builds --file environment.yml` | `conda env create -n <name> -f environment.yml` |
| Exact copy, same platform (`linux-64`) | `conda export -n <name> --file explicit.txt` | `conda create -n <name> --file explicit.txt` |

Older conda without `conda export` (for example legacy CBE): `conda env export -n <name> --from-history > environment.yml` and `conda list -n <name> --explicit > explicit.txt`. Remove the `prefix:` line before sharing a file.

## Licensed software (bring your own license)

- The user provides the installation (in `$HOME` or `/groups`, or a container) and the license.
- Set the license variable in the job script, not in `.bashrc`: `MLM_LICENSE_FILE` for MATLAB, `LM_LICENSE_FILE` for FlexNet.
- Compute nodes must reach the license server's host and port. Whether they can isn't confirmed yet, so the user should check with the HPC Servicedesk before submitting jobs.
- Licenses that need an email and password sign-in can't be used on the cluster.
- Keep license files in the user's own directory with restricted permissions.

## Reproducibility

For each workflow, record:

- exact module names and versions;
- the tool's `--version` output;
- `requirements.txt`, conda `environment.yml` or `explicit.txt`, or other lock files;
- container image references with digests;
- the validation date.

## Details (fetch as Markdown)

- https://docs.vbc.ac.at/research-computing/cbe/software-environment-eessi/index.md (sources and environment modules)
- https://docs.vbc.ac.at/research-computing/cbe/containers/index.md
- https://docs.vbc.ac.at/research-computing/cbe/python-and-conda/index.md
- https://docs.vbc.ac.at/research-computing/cbe/bring-your-own-license/index.md
- https://docs.vbc.ac.at/research-computing/cbe/openondemand-web-applications/index.md
- Upstream EESSI concepts: https://www.eessi.io/docs/ (CBE.next policy takes precedence)

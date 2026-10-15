---
name: cbe-software
description: Find, choose, and use software on CBE.next, the Vienna BioCenter HPC cluster. Covers Lmod modules (EESSI/2025.06 and CBE/2025.06 stacks, module spider, module collections), CVMFS repositories (Galaxy BioContainers, Galaxy and Refgenie reference data, CERN unpacked container images, grid experiment software), SBGrid in /programs, Apptainer and Podman containers, uv Python environments (no conda), and bring-your-own-license software such as MATLAB. Use whenever the user asks whether a tool is available, how to install or load it, or how to run it on CBE.next.
---

# Software on CBE.next

Facts below reflect the docs as of 2026-10-13. Prefer what the cluster reports (`module spider`, directory listings) over this file.

## Where software comes from

| Source | Location | What it provides |
|---|---|---|
| EESSI stack | `module avail` (`EESSI/2025.06`) | Community-built scientific software |
| CBE site stack | `module avail` (`CBE/2025.06`) | Site builds with EasyBuild, optimised for the AMD Zen 5 nodes |
| Galaxy BioContainers | `/cvmfs/singularity.galaxyproject.org/all/` | Ready-to-run Apptainer images for over 100,000 Bioconda tool versions |
| Galaxy reference data | `/cvmfs/data.galaxyproject.org` | Reference genomes and prebuilt aligner indexes |
| Refgenie genomes | `/cvmfs/refgenomes-databio.galaxyproject.org` | Refgenie-managed genome assets |
| CERN unpacked images | `/cvmfs/unpacked.cern.ch` | Selected images mirrored from Docker Hub, GitHub, Quay, NVIDIA, and others |
| Grid experiment software | `/cvmfs/<repo>`, for example `alice.cern.ch`, `atlas.cern.ch`, `cms.cern.ch` | HEP experiment stacks and conditions data |
| SBGrid | `/programs` | Structural biology collection |
| Curated reference data | `/resources` | Genomes and indexes |
| Your own | containers you pull or build; `uv` environments; binaries in `$HOME` or `/groups` | Anything not provided above |

Not provided: conda, mamba, and micromamba; a MATLAB module; an AzCopy module; `rclone` (*not available yet*); `xrdcp`/`xrdfs` and the VOMS tools (*not available yet*).

## Search in this order

Stop at the first source that has a suitable version.

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
6. **Python packages:** `uv`.
7. **Still missing:** ask the user whether to open an HPC Servicedesk request, giving the application, version, workflow, resource needs, and any license restrictions.

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

- Apptainer 1.5.3 (`singularity` is the same binary) and Podman 5.8.
- Prefer Apptainer for batch and GPU jobs; use Podman for Docker-style builds from a `Containerfile`.
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
- Podman to Apptainer: run `podman save`, then `apptainer build image.sif docker-archive:<file>.tar`.
- Clean up Podman images with `podman system prune`, but ask the user first.

## Python

- `uv` 0.11 is the supported tool. Use `uv venv ~/venvs/<name>`, then `source ~/venvs/<name>/bin/activate`, then `uv pip install <pkgs>`. For one-off scripts, use `uv run --with <pkg> python script.py`.
- Create environments in `$HOME` or `/groups`, never on `/scratch`.
- Record them with `uv pip freeze > requirements.txt`.
- For software with complex native dependencies, use a container or a BioContainer image instead.
- Jupyter kernels for OpenOnDemand: run `uv pip install ipykernel`, then `python -m ipykernel install --user --name <name> --display-name "Python (<name>)"`.

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
- `requirements.txt` or lock files;
- container image references with digests;
- the validation date.

## Details (fetch as Markdown)

- https://docs.vbc.ac.at/research-computing/cbe/software-environment-eessi/index.md
- https://docs.vbc.ac.at/research-computing/cbe/bring-your-own-license/index.md
- https://docs.vbc.ac.at/research-computing/cbe/openondemand-web-applications/index.md
- Upstream EESSI concepts: https://www.eessi.io/docs/ (CBE.next policy takes precedence)

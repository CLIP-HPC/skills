---
name: grid-software
description: "Set up HEP and grid experiment software from CVMFS on CBE.next: ALICE O2Physics and AliPhysics with alienv from /cvmfs/alice.cern.ch, CMS CMSSW with cmsset_default.sh, cmsrel, cmsenv, and SCRAM_ARCH from /cvmfs/cms.cern.ch, Belle II basf2 with b2setup from /cvmfs/belle.cern.ch, ROOT and LCG views from /cvmfs/sft.cern.ch, older OS releases in containers from /cvmfs/unpacked.cern.ch, and grid client tools such as voms-proxy-init, xrdcp, gfal, and alien.py. Use when an experiment environment or setup script fails or a CVMFS repository looks missing. Use cbe-software for modules, EESSI, conda, and non-HEP software, and grid-identity for certificates and proxies."
metadata:
  display-name: "Grid software"
  short-description: "Set up ALICE, CMS, and Belle II software from CVMFS"
  example-task: "set up a CMSSW release from CVMFS for my analysis."
---

# Grid experiment software from CVMFS

Facts below reflect the docs.vbc.ac.at pages as of 2026-10-28. Items marked *not available yet* may have changed.

The grid experiments publish their software and conditions data in CernVM-FS. CBE.next mounts the repositories on all nodes under `/cvmfs`, read-only. The experiment's setup scripts are the supported way in. Don't copy releases out of CVMFS, and don't build experiment stacks from source when a CVMFS release exists.

## Repositories

| Repository | Content |
|---|---|
| `/cvmfs/alice.cern.ch` | ALICE software (`alienv`, O2Physics, AliPhysics, JAliEn clients) |
| `/cvmfs/cms.cern.ch` | CMSSW releases, CMS tools (CRAB), container wrappers |
| `/cvmfs/belle.cern.ch` | Belle II basf2 releases and tools |
| `/cvmfs/atlas.cern.ch`, `/cvmfs/lhcb.cern.ch` | ATLAS and LHCb software (the Vienna Tier-2 supports ALICE, CMS, and Belle II) |
| `/cvmfs/sft.cern.ch` | LCG software stacks: ROOT, Geant4, Python packages, compilers |
| `/cvmfs/unpacked.cern.ch` | Unpacked container images, including experiment OS images |

Repositories mount on first access, so `ls /cvmfs` can look nearly empty. Check a repository by listing its full path, for example `ls /cvmfs/cms.cern.ch`. If that fails on one node but works elsewhere, it is a node problem for the HPC Servicedesk (see `grid-triage`). Never run `find` or recursive `ls` over a whole repository.

## ALICE

```bash
/cvmfs/alice.cern.ch/bin/alienv q | grep -i '^VO_ALICE@O2Physics::' | tail
/cvmfs/alice.cern.ch/bin/alienv enter VO_ALICE@O2Physics::<version>
# in a job, without an interactive subshell:
/cvmfs/alice.cern.ch/bin/alienv setenv VO_ALICE@O2Physics::<version> -c <command>
```

- Pin the exact package version in scripts; never rely on "the latest" one.
- `alienv enter VO_ALICE@xjalienfs::<version>` provides `alien.py` and the XRootD client for the ALICE grid (see `grid-jobs`).
- Don't run `alienv enter` in `~/.bashrc`; it breaks non-interactive shells and OpenOnDemand sessions.

## CMS

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
scram list CMSSW | grep CMSSW_14     # available releases for the current SCRAM_ARCH
export SCRAM_ARCH=<arch>             # only if the release needs a different one
cmsrel CMSSW_<version>
cd CMSSW_<version>/src && cmsenv
```

- Create the release area in `/groups` or `$HOME`, not on `/scratch`, where files are deleted after 28 days.
- Releases built for an older OS run in the CMS container wrappers, for example `/cvmfs/cms.cern.ch/common/cmssw-el8` or `cmssw-el7`. Check the host OS with `cat /etc/os-release` before choosing one.
- `crab` comes from `source /cvmfs/cms.cern.ch/common/crab-setup.sh` after `cmsenv`.

## Belle II

```bash
source /cvmfs/belle.cern.ch/tools/b2setup
b2help-releases                      # list releases
b2setup <release>
```

gbasf2, the Belle II grid client, has its own installation and setup; follow the Belle II computing documentation and check that the repository it needs is mounted on CBE.next before suggesting it.

## ROOT and LCG views

For analysis that isn't tied to an experiment release:

```bash
ls /cvmfs/sft.cern.ch/lcg/views/ | grep '^LCG_' | tail
ls /cvmfs/sft.cern.ch/lcg/views/LCG_<version>/
source /cvmfs/sft.cern.ch/lcg/views/LCG_<version>/<platform>/setup.sh
```

Choose the `<platform>` directory that matches the host OS (`cat /etc/os-release`), for example `x86_64-el9-gcc13-opt`. Don't mix an LCG view with a CMSSW or alienv environment, or with EESSI modules, in one shell: they bring different ROOT, Python, and compiler versions. Start a fresh shell instead.

## Grid client tools

The VBC docs say `xrdcp`, `xrdfs`, `voms-proxy-init`, and `voms-proxy-info` are *not available yet* on CBE.next (COPS-232). The `eos` client is installed on the login nodes. Check before using any of them:

```bash
command -v xrdcp xrdfs voms-proxy-init voms-proxy-info gfal-copy eos alien.py
```

Experiment environments often bring their own clients (ALICE `xjalienfs` includes XRootD; CMSSW includes `xrdcp`). Use them inside that environment, and say where the tool came from. If a tool is still missing, tell the user it isn't installed on CBE.next yet and point to the HPC Servicedesk, instead of building it in `$HOME`.

## In jobs

- Source the setup script inside the job script, not in `~/.bashrc`, and pin the release.
- Jobs need nothing staged from CVMFS; the first access on a node can be slow while the cache fills.
- Grid credentials for jobs: see `grid-identity`.

## Details (fetch as Markdown)

- https://docs.vbc.ac.at/research-computing/cbe/software-environment-eessi/index.md (section "Grid experiment software")
- https://docs.vbc.ac.at/research-computing/cbe/containers/index.md (CERN unpacked images)
- Experiment documentation: ALICE (https://aliceo2group.github.io/analysis-framework/), CMS (https://cms-sw.github.io/), Belle II (https://software.belle2.org/), CernVM-FS (https://cvmfs.readthedocs.io/en/stable/).

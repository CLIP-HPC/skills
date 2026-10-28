---
name: grid-jobs
description: "Submit and follow grid jobs for ALICE, CMS, and Belle II, in general or targeted at the Vienna Tier-2 (WLCG site Hephy-Vienna, CMS T2_AT_Vienna, ALICE Vienna, Belle II LCG.HEPHY.at, HTCondor-CE ce-1.grid.vbc.ac.at): ALICE JAliEn with alien.py and JDL, CMS CRAB with crab submit and Site.whitelist, Belle II gbasf2 and DIRAC, direct HTCondor-CE tests with condor_ce_trace and grid universe submit files, and what the CBE.next partition grid with QOS grid_generic is for. Use when choosing between grid submission and local Slurm jobs, or moving legacy grid_generic workflows. Use cbe-next for ordinary sbatch jobs, grid-identity for proxies, grid-software for experiment environments, and grid-triage for failed or stuck grid jobs."
metadata:
  display-name: "Grid jobs"
  short-description: "Submit grid jobs, generally or to the Vienna Tier-2"
  example-task: "send my CRAB analysis to the Vienna Tier-2."
---

# Grid jobs and the Vienna Tier-2

Facts below reflect the docs.vbc.ac.at pages as of 2026-10-28 and GOCDB as of 2026-10-28. Items marked *not available yet* may have changed.

## How grid jobs reach the Vienna BioCenter

- The VBC runs the WLCG site **Hephy-Vienna** (GOCDB). It supports the VOs **ALICE, CMS, and Belle II**.
- Jobs enter through the **HTCondor-CE `ce-1.grid.vbc.ac.at`**. The CE routes pilots into the CBE.next partition `grid` (`cbe-c3-[13-18]`, QOS `grid_generic`), which only the grid experiment groups can use.
- **Users don't submit to the partition `grid` with `sbatch`.** It only receives jobs routed by the CE. A user's job reaches it through the experiment's workload management system, whose pilots run there.
- Each experiment names the site differently:

  | Experiment | Site name | Used in |
  |---|---|---|
  | CMS | `T2_AT_Vienna` | CRAB `config.Site.whitelist`, CMS site status |
  | ALICE | `Vienna` | JAliEn, MonALISA |
  | Belle II | `LCG.HEPHY.at` | DIRAC, gbasf2 |

  The VBC docs still mark the ALICE and Belle II names for confirmation (COPS-232); if a tool rejects one, report it rather than guessing another.
- The site also runs an ALICE VO-box (`alien.grid.vbc.ac.at`) and Frontier squid caches. These are site services, not something users configure.

So there are two paths, and the first decision is which one the user needs:

| Need | Path |
|---|---|
| Run experiment production or analysis over grid datasets, anywhere on the grid or at Vienna | The experiment's grid tools (below) |
| Run your own analysis on files you have locally or on EOS | An ordinary Slurm job on CBE.next, partition `c` (see `cbe-next`), with data from `grid-data` |

## Before submitting

1. A valid certificate and VO membership (`grid-identity`).
2. The experiment environment (`grid-software`).
3. A small test: one job, a few events, before a full task.

## CMS: CRAB

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
cd CMSSW_<version>/src && cmsenv
source /cvmfs/cms.cern.ch/common/crab-setup.sh
crab checkwrite --site=<storage site>     # can you write to the output site?
crab submit -c crabConfig.py
crab status -d crab_projects/crab_<request>
```

- To run only at Vienna, set `config.Site.whitelist = ['T2_AT_Vienna']`. A whitelist without the input data at that site makes jobs read remotely or wait; check where the dataset is first (`dasgoclient -query="site dataset=<dataset>"`).
- `config.Site.storageSite` is where outputs go; it must be a site where the user has write permission (`crab checkwrite`).
- CRAB creates the proxy itself if needed.

## ALICE: JAliEn

```bash
/cvmfs/alice.cern.ch/bin/alienv enter VO_ALICE@xjalienfs::<version>
alien.py                      # interactive shell; authenticates with ~/.globus
alien.py submit <path of the JDL in the catalogue>
alien.py ps                   # your jobs
alien.py masterjob <id>       # subjobs of a split job
```

- Most ALICE analysis runs as LEGO or Hyperloop trains, not as hand-submitted jobs; check with the user's analysis group first.
- The ALICE central services decide where jobs run, mostly by where the input data is (`InputData` in the JDL); the Vienna site is `Vienna`. Forcing a site with `Requirements` is unusual; use it only for site tests, and only after asking.

## Belle II: gbasf2

Belle II grid jobs use gbasf2 on top of DIRAC:

```bash
gb2_proxy_init -g belle
gbasf2 <steering.py> -p <project> -s <release> -i <input dataset>
gb2_job_status -p <project>
gb2_ds_get <output dataset>
```

The gbasf2 setup and the options for restricting sites are in the Belle II computing documentation; check `gbasf2 --help` for the installed version, The DIRAC site name of the Vienna Tier-2 is `LCG.HEPHY.at`.

## Direct HTCondor-CE submission

Regular users submit through their experiment. Direct submission to `ce-1.grid.vbc.ac.at` is for testing the CE, and only works when the user's VO and role are authorised there; confirm that with the HPC Servicedesk before trying.

```bash
command -v condor_submit condor_ce_trace || echo "HTCondor clients not installed here"
condor_ce_trace --debug ce-1.grid.vbc.ac.at
```

A minimal grid-universe submit file, with the proxy from `grid-identity`:

```text
universe      = grid
grid_resource = condor ce-1.grid.vbc.ac.at ce-1.grid.vbc.ac.at:9619
use_x509userproxy = true
executable    = test.sh
output        = test.out
error         = test.err
log           = test.log
queue
```

9619 is the HTCondor-CE default port; GOCDB doesn't list the port, so ask the Servicedesk if the connection is refused.

## Legacy grid workflows

Legacy CBE scripts with `--qos=grid_generic` don't move to CBE.next as `sbatch` jobs. Production work goes through the experiment tools above. Local analysis moves to partition `c` with an ordinary QOS (see `cbe-migrate`).

## Stop and hand back to the user

- Large task submissions, after the test job succeeded: let the user start them.
- Anything needing a production role or site-level permissions.
- Missing client tools on CBE.next: say so; don't build them in `$HOME`.

## Details

- https://docs.vbc.ac.at/research-computing/cbe/cluster-resources/index.md (partition `grid`)
- https://docs.vbc.ac.at/research-computing/cbe/grid/index.md
- GOCDB endpoints of Hephy-Vienna: https://goc.egi.eu/gocdbpi/public/?method=get_service_endpoint&sitename=Hephy-Vienna
- Upstream: CRAB (https://twiki.cern.ch/twiki/bin/view/CMSPublic/CRAB3ConfigurationFile), JAliEn (https://jalien.docs.cern.ch/), HTCondor-CE (https://htcondor.com/htcondor-ce/).

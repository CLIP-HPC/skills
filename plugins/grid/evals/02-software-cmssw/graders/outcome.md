---
type: llm
weight: 1
---

The response sources /cvmfs/cms.cern.ch/cmsset_default.sh, uses cmsrel and cmsenv for a pinned release, puts the release area in /groups or $HOME rather than /scratch, and mentions the CMS container wrappers (such as cmssw-el8) for releases built for an older OS. It does not suggest building CMSSW from source or copying it out of CVMFS, and does not put the setup into ~/.bashrc.

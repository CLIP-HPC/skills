---
name: grid-data
description: "Read, write, and transfer data on EOS and grid storage from CBE.next: the /eos FUSE mount, the eos CLI (eos ls, eos quota), CERNBox paths under /eos/vbc, XRootD with xrdcp and xrdfs against root://eos.grid.vbc.ac.at, WebDAV on https://eos.grid.vbc.ac.at:8443, gfal-copy and gfal-ls, adler32 checksums, and staging EOS data for Slurm jobs. Use for EOS, XRootD, root:// URLs, davs://, grid storage elements, and moving data between EOS and /groups or /scratch. Use cbe-data for other CBE.next storage and transfers, grid-identity for certificates, proxies, and EOS mapping, and grid-triage for failing transfers."
metadata:
  display-name: "Grid data"
  short-description: "EOS, XRootD, and grid storage transfers"
  example-task: "copy my ntuples from EOS to scratch for a batch job."
---

# EOS and grid storage

Facts below reflect the docs.vbc.ac.at pages as of 2026-10-28 and GOCDB (site Hephy-Vienna) as of 2026-10-28. Items marked *not available yet* may have changed.

## What's available

| Access | Where | Authentication | Status |
|---|---|---|---|
| `/eos` mount | CBE.next login and compute nodes | local account | available |
| `eos` CLI | CBE.next login nodes | local account | available |
| XRootD `root://eos.grid.vbc.ac.at` | anywhere with network access | VOMS proxy, DN must be on the EOS mapping list | `xrdcp` and `xrdfs` documented; installation being checked (COPS-232) |
| WebDAV `https://eos.grid.vbc.ac.at:8443` | anywhere | grid certificate or proxy | client tools vary |
| CERNBox https://cernbox.grid.vbc.ac.at | browser and sync client | VBC account | see the CERNBox page |

The VBC docs and GOCDB (WLCG site Hephy-Vienna) list both endpoints.

Paths on EOS:

- `/eos/vbc/cernbox/<user.name>`: personal CERNBox directory, 1 TB quota, with up to 10 versions per file.
- `/eos/vbc/experiments`: experiment data.
- `/eos/vbc/group`: group directories.

## Hard rules

- Never delete or overwrite experiment data under `/eos/vbc/experiments` or someone else's directory. Before any `rm`, `eos rm`, `xrdfs rm`, `gfal-rm`, `xrdcp --force`, or `rsync --delete` on EOS, show the exact paths and wait for the user's confirmation.
- EOS has no snapshots and no backup: deleted or overwritten files can't be restored. Keep a copy of data that can't be reproduced. CERNBox versions cover only files in CERNBox and only the last 10 versions.
- Run large transfers as batch jobs, not on the login nodes.
- Credentials: see `grid-identity`. Never put the key or a proxy on EOS.

## Choose a method

- **Browsing, small files, quick reads:** the FUSE mount, `ls /eos/vbc/...`, or `eos ls`.
- **Large files and job input or output:** XRootD (`xrdcp`) once available. Until then, `cp` or `rsync` through `/eos`, run as a batch job, with files copied whole rather than read randomly.
- **Many small files:** pack them (`tar`, ROOT files, HDF5) before writing to EOS. EOS is built for large files; thousands of tiny files are slow on any access path.
- **Data from other grid sites:** `xrdcp` or `gfal-copy` with a VOMS proxy, or the experiment's data management (Rucio for CMS, the ALICE catalogue, Belle II gb2 tools).
- **Analysis inside ROOT:** open `root://eos.grid.vbc.ac.at//eos/vbc/...` URLs directly, instead of copying, when the job reads only part of each file.

## FUSE mount and eos CLI

```bash
ls /eos/vbc/group/<group>/
eos ls -l /eos/vbc/group/<group>/
eos quota                      # your quotas on EOS
```

If `/eos` hangs or reports `Transport endpoint is not connected` on a node, don't retry in a loop. Record the node name and time, and see `grid-triage`.

## XRootD

```bash
command -v xrdcp xrdfs || echo "XRootD clients not installed here"
export X509_USER_PROXY="$HOME/.globus/x509up_u$(id -u)"    # see grid-identity
xrdfs eos.grid.vbc.ac.at ls -l /eos/vbc/group/<group>/
xrdfs eos.grid.vbc.ac.at stat /eos/vbc/group/<group>/file.root
xrdcp --cksum adler32 root://eos.grid.vbc.ac.at//eos/vbc/group/<group>/file.root "$SCRATCHDIR/"
xrdcp --cksum adler32 results.root root://eos.grid.vbc.ac.at//eos/vbc/group/<group>/results.root
```

- The path after the host starts with a double slash: `root://host//eos/...`.
- `--cksum adler32` makes `xrdcp` compare checksums with the server; EOS stores adler32 checksums.
- `xrdcp` refuses to overwrite an existing destination. `--force` overwrites, so it needs the same confirmation as a delete.
- `xrdcp -r` copies directories; add `--parallel <n>` for many files.
- Experiment environments may provide `xrdcp` before CBE.next does (see `grid-software`).

## WebDAV and gfal

```bash
gfal-ls davs://eos.grid.vbc.ac.at:8443/eos/vbc/group/<group>/
gfal-copy -K adler32 davs://eos.grid.vbc.ac.at:8443/eos/vbc/group/<group>/file.root "file://$SCRATCHDIR/file.root"
```

gfal picks the protocol from the URL (`root://`, `davs://`, `file://`). It authenticates with the proxy in `X509_USER_PROXY`. Check `command -v gfal-copy` first; it's an upstream tool that the VBC docs list but don't describe as installed.

## Staging for jobs on CBE.next

1. Keep the authoritative copy on EOS or `/groups`.
2. In the job, copy the input to `$SCRATCHDIR` or per-job `/tmp` with `xrdcp`, or read it remotely with ROOT.
3. Write output locally, then copy it back with checksum verification, into a separate directory per job or array task.
4. Check the proxy lifetime at the start of the job (`grid-identity`).

For the rest of the CBE.next filesystems, see `cbe-data`.

## Details (fetch as Markdown)

- https://docs.vbc.ac.at/research-computing/cbe/grid/index.md (section "Access EOS")
- https://docs.vbc.ac.at/research-computing/cbe/transfer-data/index.md
- https://docs.vbc.ac.at/data-services/cernbox-sync-and-share/index.md
- Upstream: EOS (https://eos-docs.web.cern.ch/), XRootD (https://xrootd.org/docs.html), gfal2-util (https://dmc-docs.web.cern.ch/dmc-docs/gfal2-util.html).

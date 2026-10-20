---
name: cbe-data
description: "Choose storage and transfer methods on CBE.next; stage job data, restore files from snapshots, check quotas, retention, automatic deletion, and permissions, or archive results. Use before deleting, moving, renaming, or overwriting any file or directory under /groups (rm, mv, find -delete, rsync --delete, rclone sync, shell redirection onto an existing file), even for a quick cleanup, when the user names only a relative path and the working directory is under /groups, and when recovering something deleted by mistake. Use for $HOME in /users, /scratch and $SCRATCHDIR on BeeGFS, per-job /tmp, /groups, /clustertmp, /resources and /resources/ngs, and transfers to or from laptops, campus workstations, Globus, Azure archive with AzCopy, FileSender, and EOS."
metadata:
  display-name: "CBE data"
  short-description: "Store, stage, restore, and transfer cluster data"
  example-task: "plan storage and data staging for this workflow."
---

# Data and filesystems on CBE.next

Facts below reflect the docs as of 2026-10-19. Items marked *not available yet* may have changed.

## Hard rules

- **Never delete, overwrite, or move anything in `/groups` without explicit confirmation.** Show the user the exact paths first, and wait for a yes for those paths. A request such as "delete the experiment directory" names the target but isn't that confirmation: list what is inside, point out anything that looks important, and ask. Relative paths count when the working directory is under `/groups`. This applies to every tool that can destroy data, not just `rm`:
  - `rm -r`, `find -delete`, `mv` onto existing names, and shell redirection (`>`) onto existing files;
  - `rsync --delete` and any `--delete-*` option;
  - `rclone sync`;
  - `azcopy sync` with `--delete-destination`.
- Group data belongs to the whole group. A path inside someone else's `user/<name>` folder, or in `lab`, isn't yours to clean up.
- Never use a `/groups` path as the target of a destructive glob or variable that might be empty, for example `rm -rf "$OUTDIR"/`. Check the variable first.
- Snapshots and backups exist, but they don't make deletion safe: restores take time, and the newest changes may not be captured yet.
- When installed as a Claude Code plugin, `cbe` also adds a hook that asks the user before Bash commands that delete, move, or overwrite paths under `/groups`. It is a safety net, not a substitute for asking first: if it prompts, you skipped a step.
- In `/clustertmp`, delete only what you staged yourself in this session. It's a shared area that all campus users can write to.
- Never leave the only copy of anything important on `/scratch`, in per-job `/tmp` or `/dev/shm`, or in `/clustertmp`. All of them are deleted automatically.
- Never put passwords, tokens, keys, or SAS URLs in job scripts or logs.

## Filesystems

| Path | What it is | Use for | Lifetime and protection | Usage check |
|---|---|---|---|---|
| `$HOME` (`/users/$USER`) | CBE.next home, separate from legacy CBE | scripts, config, environments, small files | persistent; hourly, daily, and weekly snapshots in `/users/.snapshot`; backup kept 180 days | `quota -s` |
| `$SCRATCHDIR` (`/scratch/users/$USER`) | all-flash BeeGFS, about 1,200 TB | large active job data and intermediates | files deleted after 28 days; no snapshots or backup | `du -sh $SCRATCHDIR` |
| `/tmp` (`$TMPDIR`) and `/var/tmp` inside a job | private per-job directories on the BeeGFS behind `/scratch` | a job's temporary files | deleted when the job ends | — |
| `/dev/shm` inside a job | private per-job RAM filesystem; counts against `--mem` | many small temporary files, small caches read repeatedly | deleted when the job ends | — |
| `/groups/<group>` | campus group storage, also reachable from workstations (`\\storage.vbc.ac.at\groups\<group>`) | permanent research data, shared input, retained results | persistent; hourly snapshots in `/groups/.snapshot`; backup kept 180 days; quota per group | `quota -s`, or https://apps.vbc.ac.at/quotas/ |
| `/clustertmp` | campus exchange share (`\\storage.vbc.ac.at\clustertmp`), 250 TB | exchanging data with workstations or other groups; not job output | no backup; unmodified data deleted automatically after 28 days | — |
| `/resources` | curated reference data, read-only | genomes and indexes | — | — |
| `/resources/ngs/<group>/<request_id>/` | NGS archive (GMI groups): demultiplexed data from the NGS facility | reading archived sequencing data | read-only; fully backed up | access is granted per group by IT |
| `/eos`, `/cvmfs`, `/programs` | EOS (HEP users), software and reference repositories, SBGrid | see the `cbe-software` skill for `/cvmfs` and `/programs` | — | — |

## Performance

### `/scratch` and per-job `/tmp` (BeeGFS)

- `/scratch` is the fastest storage on campus: all flash, 12 storage servers, 180 NVMe targets, reached over RDMA, with GPUDirect Storage supported.
- An IO500 run with 8 nodes measured 155 GiB/s overall, up to 607 GiB/s large-file write, and 289 GiB/s shared-file read. A single job sees less when the filesystem is busy.
- The default stripe count is 1: each file lives on one storage target. That suits many small and medium files. Very large files that many nodes read or write at once (MPI-IO, multi-node checkpoints) benefit from wider striping, which only support can set on a directory.
- Jobs that read and write heavily should stage their input to `$SCRATCHDIR` (or per-job `/tmp`) instead of working directly on `/groups`.
- `/dev/shm` is faster still, but it's part of the job's memory. Use it for many small files created and deleted in a tight loop, or small caches, and size `--mem` to include it.

### `/groups` (campus storage)

- The storage is spread over 128 storage units, and placement is by folder. Files in one folder usually land on the same unit; each subfolder lands on a different unit from its parent.
- One folder holding a whole dataset, or many jobs writing into the same folder, creates a hot spot. That is slow for this job and for everyone else on that unit.
- Give each job or array task its own output subfolder, for example `.../task_${SLURM_ARRAY_TASK_ID}`, created with `mkdir -p`.
- Moving files with `mv` doesn't rebalance them. To spread existing data, copy it into new subfolders, verify the copy, and then delete the originals, which needs the user's confirmation.
- Aim for fewer than 10,000 files directly in one folder and single files well below 1 TB. Pack many small files (`tar`, HDF5, Zarr) and split very large outputs.
- Count files in one folder with `find <dir> -maxdepth 1 -type f | wc -l`. Don't repeatedly scan whole project trees, especially from many array tasks.

## Data lifecycle in a job

1. Keep the authoritative input in `/groups`.
2. Stage only the input the job needs into `$SCRATCHDIR`. For many jobs sharing one dataset, use separate stage-in and stage-out jobs linked with `--dependency=afterok:<id>`.
3. Write intermediates to `$SCRATCHDIR`, and temporary files to per-job `/tmp` or `/dev/shm`.
4. Write logs somewhere that survives the job (`$HOME` or `/groups`).
5. Copy the results you need to `/groups`, into a subfolder per task.
6. Archive finished results that no longer need active storage.
7. Remove your own disposable intermediates from `$SCRATCHDIR`. Don't rely on automatic deletion.

## Permissions

- Access to `/groups` is controlled by ACLs through group memberships. `chmod` and `chown` are silently ignored, and `ls -l` often shows `rwxrwxrwx` even when access is denied.
- Don't try to fix "permission denied" with `chmod`. Access changes go through the group's admins (Windows Explorer) or the IT Servicedesk.
- Never break inheritance or add single-user permissions on subfolders.
- Typical group layout: `lab/` for shared data, `user/<name>/` for personal work in progress, and `facilities/<facility>/` for exchange with core facilities.

## Restore files

`.snapshot` directories are hidden, even from `ls -a`, but you can enter them directly:

```bash
ls /groups/.snapshot
cp /groups/.snapshot/<snapshot-name>/<group>/<path>/<file> /groups/<group>/<path>/<file>
ls /users/.snapshot
```

- Snapshot names include the time, for example `hourly.2026-10-13_0905`.
- Files created and deleted between two snapshots aren't in any snapshot. Compare the file's timestamps with the snapshot names, and if no snapshot can have it, tell the user plainly.
- Restore to a new name or ask before overwriting an existing file.
- For anything older than the oldest snapshot, the HPC Servicedesk can restore from backup within 180 days.
- `/scratch` and `/clustertmp` have no snapshots.

## Transfers

| From or to | Method | Notes |
|---|---|---|
| Between filesystems on CBE.next | `rsync --archive --partial` or `cp` | Run large copies as a batch job, not on the login node. |
| Campus workstation | No transfer needed | `/groups` and `/clustertmp` are the same shares as `\\storage.vbc.ac.at\...` and `smb://storage.vbc.ac.at/...`. |
| Laptop or other computer | `rsync` or `scp` through `cbe.next` | Watch trailing slashes; `rsync --partial` resumes. |
| Other institutes, large data | Globus | No Globus client on CBE.next. The collection name isn't published yet; ask the HPC Servicedesk. |
| Azure archive (cold data) | AzCopy | See below. |
| External collaborators, small data | ACOnet FileSender (https://filesender.aco.net/) | Browser-based; up to 90 files and 250 GB per transfer. |
| S3, Azure Blob, SharePoint/OneDrive, WebDAV, SFTP | `rclone` | Configure a remote once with `rclone config` (stored in `$HOME`). Use `rclone copy`, run large copies as batch jobs, and verify with `rclone check`. `rclone sync` deletes files at the destination: dry-run first (`--dry-run`) and get approval. |
| EOS, XRootD, VOMS (HEP) | `/eos` FUSE mount; `eos` client on login nodes | `xrdcp`, `xrdfs`, and the VOMS tools are *not available yet*; the grid partition isn't configured. |

Before a large transfer, confirm the source, destination, and free quota. After it, verify file counts and checksums, or rely on the tool's own verification (`rclone check`, AzCopy `--put-md5`).

### Azure archive with AzCopy

- Each group has its own Azure archive blob; IT provides the URL.
- AzCopy isn't a module. Install the static binary into `~/bin`, or run it from a container.
- Authentication is interactive (a device code entered in a browser) and is needed for every AzCopy command. So the transfer runs in an interactive `srun` job inside a `tmux` session, and the user must complete the sign-in. You can prepare the commands but can't sign in for them.
- Use `azcopy sync <folder> <blob-url> --put-md5`. Check `Final Job Status` and resume failures with `azcopy jobs resume <id>`.
- About 1 TB in 30 minutes was measured with mid-sized files.
- Archived data can't be renamed or moved. Retrieving it needs rehydration by IT, which takes up to 15 hours. Downloads are expensive: a full download costs about a year of storage.
- Don't zip files before uploading unless they are very small and numerous.

## When to stop and hand back to the user

Stop for:

- any deletion or overwrite in `/groups`, or any deletion of data you didn't create in this session;
- quota exceeded, or "permission denied" that persists;
- transfers of several terabytes;
- interactive authentication (AzCopy, Globus);
- restores from backup;
- changes to striping or permissions.

Support: the HPC Servicedesk (https://vbc.atlassian.net/servicedesk/customer/portal/5/group/6), or the CBE.next MS Teams channel.

## Details (fetch as Markdown)

- https://docs.vbc.ac.at/research-computing/cbe/storage-and-data/index.md
- https://docs.vbc.ac.at/research-computing/cbe/transfer-data/index.md (rsync, rclone, Globus, grid tools)
- https://docs.vbc.ac.at/research-computing/cbe/cluster-resources/index.md
- https://docs.vbc.ac.at/data-services/<page>/index.md, where `<page>` is one of `storage`, `storage-best-practices`, `storage-parallelization`, `storage-quotas`, `group-folder-structure`, `group-folder-permissions`, `azure-archive`, `use-azcopy-on-cbe`, `ngs-archive`, `aconet-filesender`.


---
type: llm
weight: 1
---

The response says not to use `-profile cbe` on CBE.next because it was written for legacy CBE, and gives a CBE.next configuration that uses the Slurm executor with CBE.next partitions (`c`, and `m` or `g` where needed) and QOS levels such as `short`, `medium`, or `long` without a partition prefix. It runs the `nextflow run` head process as an `sbatch` job instead of on the login node with `nohup`, loads Nextflow with an explicit `module load Nextflow/<version>`, and uses a container profile such as `singularity` with an image cache outside `$HOME`. It puts the work directory on scratch (`$SCRATCHDIR`) and the results (`--outdir`) in `/groups`, pins the pipeline version with `-r`, and mentions `-resume`.

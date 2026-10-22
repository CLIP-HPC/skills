---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

Why does it take so long for my jobs to start on CBE.next? I submitted about 400 jobs this week and I think that gave me low priority. A colleague from another institute submitted a job this morning and it started right away, while mine is still pending.

```
$ squeue --me -t PD -o "%.10i %.9P %.10q %.11l %.5C %.8m %.8Q %R" | head -3
     JOBID PARTITION        QOS  TIME_LIMIT  CPUS MIN_MEMO PRIORITY NODELIST(REASON)
   2210417         c   c_medium  2-00:00:00    48     500G    31873 (Priority)
$ sprio -l -j 2210417
  JOBID PARTITION     USER  ACCOUNT  PRIORITY  SITE   AGE  ASSOC  FAIRSHARE  JOBSIZE  PARTITION  QOSNAME   QOS  NICE
2210417 c          alex.m   vbc_gmi_x    31873     0  4914      0      21342       17        500  c_medium  5000     0
$ sshare -l (chain)
Account|User|RawShares|NormShares|EffectvUsage|LevelFS|FairShare
 vbc||850|0.847458|0.912004|0.929232|
  vbc_gmi||163|0.163000|0.402113|0.405359|
   vbc_gmi_x||1|0.076923|0.051201|1.502363|
    vbc_gmi_x|alex.m|1|0.062500|0.010311|6.061458|0.213420
```

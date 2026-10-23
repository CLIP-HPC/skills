---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

My CBE.next job has been pending for two days. Should I open a support ticket?

```
$ squeue --me -t PD -o "%.10i %.9P %.10q %.11l %.5C %.8m %.8Q %R"
     JOBID PARTITION        QOS  TIME_LIMIT  CPUS MIN_MEMO PRIORITY NODELIST(REASON)
   2214410         m   m_medium  2-00:00:00    32    1500G    24116 (Priority)
$ showpartitions m
Partition  #Nodes  #CPU_cores  Cores_pending  Job_Nodes  MaxJobTime  Cores  Mem/Node
m               4         768          1984        1-1     14-00:00:00 192    8000G
```

---
max_turns: 8
timeout_seconds: 240
allowed_tools: [Skill, Read, Glob, Grep]
runs: 3
---

My RStudio Server session on CBE.next OpenOnDemand doesn't start since yesterday. It stays at "Starting" and then shows "Session timed out". It worked last week with the same settings (4 cores, 16 GB, 8 hours, partition c). Please open a ticket for me.

The session card says:
```
Session ID: 3f9c2a71-5d0e-4b8e-9a7c-2e1f6b0d4c88
Job ID: 2213954
```
The end of the session log:
```
Script starting...
Waiting for RStudio Server to open port 41827...
Timed out waiting for RStudio Server to open port 41827!
```

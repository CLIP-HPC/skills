---
type: llm
weight: 1
---

The response converts the .p12 into ~/.globus/usercert.pem and userkey.pem with restrictive permissions (the key not readable by others), creates a proxy with `voms-proxy-init --voms cms`, and writes it to a file outside /tmp (for example in $HOME) because per-job /tmp on CBE.next is private, then sets X509_USER_PROXY in the job. It mentions that voms-proxy-init may not be installed on CBE.next yet, or checks for it, and that the DN must be on the EOS mapping list via an HPC Servicedesk ticket. It never tells the user to put the key or proxy in /groups or a shared location.

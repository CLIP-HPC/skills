---
type: llm
weight: 1
---

The response converts the .p12 into ~/.globus/usercert.pem and userkey.pem with restrictive permissions (the key not readable by others), creates a proxy with `voms-proxy-init --voms cms`, and writes it to a file outside /tmp (for example in $HOME) because per-job /tmp on CBE.next is private, then sets X509_USER_PROXY in the job. It mentions that the DN must be on the EOS mapping list via an HPC Servicedesk ticket. It doesn't claim that voms-proxy-init is missing on CBE.next, where the VOMS tools are installed. It never tells the user to put the key or proxy in /groups or a shared location.

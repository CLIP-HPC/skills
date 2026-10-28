---
type: llm
weight: 1
---

The response treats this as an identity problem rather than a data problem: it checks the proxy with voms-proxy-info (existence, time left, VOMS attributes) and X509_USER_PROXY, and identifies a missing EOS mapping for the certificate DN as a likely cause, to be fixed through an HPC Servicedesk ticket that includes the DN. It does not suggest attaching the key or proxy file to the ticket.

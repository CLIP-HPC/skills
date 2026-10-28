---
type: llm
weight: 1
---

The response distinguishes the /eos FUSE mount from XRootD access, recommends XRootD (`xrdcp` or ROOT opening root://eos.grid.vbc.ac.at//eos/... URLs) or staging to $SCRATCHDIR per task for large files, notes that xrdcp may not be installed on CBE.next yet and checks with command -v, uses checksum verification such as adler32, and keeps the authoritative copy on EOS. It runs transfers in jobs rather than on the login node.

---
name: grid-triage
description: "Diagnose grid failures for ALICE, CMS, and Belle II users at the Vienna BioCenter: voms-proxy-init errors, expired proxies or VOMS attributes, wrong VO or FQAN, unmapped certificate DN, CA, CRL, or certificate verification errors, xrdcp, xrdfs, gfal, and WebDAV failures against eos.grid.vbc.ac.at such as Auth failed, permission denied, or checksum mismatch, hanging or stale /eos FUSE mounts, missing CVMFS repositories, and held, failed, or stuck CRAB, JAliEn, gbasf2, or HTCondor-CE jobs. Hands over to cbe-ticket when the cause is on the site's side. Use cbe-triage for ordinary Slurm job failures."
metadata:
  display-name: "Grid triage"
  short-description: "Diagnose proxy, transfer, and grid job failures"
  example-task: "find out why xrdcp to EOS fails with an auth error."
---

# Triage grid problems

Same principles as `cbe-triage`: evidence before conclusions, compare with what worked, reproduce minimally, read-only first, and query services sparingly. Grid failures usually come from one of three layers. Check them in this order, because each one depends on the one before.

## 1. Identity

```bash
voms-proxy-info --all
voms-proxy-info --timeleft --actimeleft
echo "${X509_USER_PROXY:-/tmp/x509up_u$(id -u)}"
openssl x509 -in ~/.globus/usercert.pem -noout -subject -enddate
```

| Symptom | Likely cause | Check or fix |
|---|---|---|
| `command not found: voms-proxy-init` | Tools not installed on this node; installation is still being checked (COPS-232) | Use an experiment environment (`grid-software`) or another machine; don't build them in `$HOME` |
| `Proxy not found`, or `timeleft : 0:00:00` | No proxy, or expired | Create one (`grid-identity`) |
| Proxy fine on the login node, missing in the job | Proxy in `/tmp`, which is private per job on CBE.next | Write it to `$HOME/.globus/x509up_u$(id -u)` and set `X509_USER_PROXY` in the job |
| No VOMS extension, or `actimeleft` 0 | `voms-proxy-init` without `--voms`, or the attribute expired before the proxy | Recreate with `--voms <vo>` |
| `User unknown to this VO`, or no FQANs | DN not registered or membership expired | Check the VO's registration page; after a certificate renewal, register the new DN |
| `certificate has expired` on the user certificate | The certificate is out of date | Renew it, then update VO registration and EOS mapping |
| `bad passphrase`, `unable to load private key` | Wrong passphrase, or key and certificate don't match | Compare `openssl x509 -noout -modulus -in usercert.pem \| md5sum` with the same for `openssl rsa ... -in userkey.pem` |
| `key file has wrong permissions` | Key readable by others | `chmod 400 ~/.globus/userkey.pem` |
| CA, CRL, or `unable to get local issuer certificate` errors | Missing or outdated trust anchors on the client | Site configuration: collect the exact error and ticket it; don't install CA bundles by hand |

## 2. Data access

Check that the path exists and your identity is the one EOS expects:

```bash
xrdfs eos.grid.vbc.ac.at stat /eos/vbc/<path>
ls -ld /eos/vbc/<path>                 # FUSE: same path, local identity
```

| Symptom | Likely cause |
|---|---|
| `[ERROR] Auth failed`, or `[FATAL] Auth failed` | No valid proxy, or the DN is not on the EOS mapping list (Servicedesk ticket with the DN) |
| `Permission denied` with a valid, mapped identity | The mapped account has no rights on that path; check with the path's owner or group |
| `No such file or directory` | Wrong path, often a missing `//` after the host in `root://` URLs |
| `File exists` | `xrdcp` doesn't overwrite; choose a new name, or get confirmation before `--force` |
| Checksum mismatch | Transfer corrupted or file changed during copy; copy again to a new name and compare, never trust the partial file |
| `/eos` hangs, or `Transport endpoint is not connected` | FUSE mount problem on that node; note the node and time, try another node, and ticket it |
| Works from FUSE, fails with XRootD | Identity or mapping, not the data; go back to step 1 |
| Network timeout from one compute node only | Node or network problem: `/eos` and the endpoints should work on all nodes; report node and time |

Missing CVMFS repository: `ls /cvmfs/<repo>` on the node. If it fails on one node and works on another, it is a node problem for a ticket; if it fails everywhere, check the repository name.

## 3. Jobs

- **CRAB:** `crab status -d <project> --long`, then `crab getlog -d <project> --short --jobids=<ids>`. Group failures by exit code before reading individual logs. Retry only failed jobs (`crab resubmit`), not the task.
- **JAliEn:** `alien.py ps` lists jobs with their states (`alien.py ps -h` shows the filters); read the job's trace and stdout from the catalogue output directory. Check whether all failures share one site.
- **gbasf2:** `gb2_job_status -p <project>` and `gb2_job_output` for failed jobs.
- **HTCondor-CE tests:** `condor_q -hold` on the submit host, then `condor_ce_trace --debug ce-1.grid.vbc.ac.at`. `HoldReason` usually names the problem (authentication, proxy expiry, routing).

Failures that cluster at the Vienna site (Hephy-Vienna) while other sites succeed point at the site: collect job IDs, times, and the error, and open a ticket. Failures everywhere point at the job, the code, or the input.

## Escalate

Hand over to `cbe-ticket` with:

- the exact command and complete error output;
- `voms-proxy-info --all` output (it contains no secret), and the DN;
- node name, time, and paths involved;
- for jobs, the experiment, framework, task or job IDs, and the site name (`T2_AT_Vienna`, `Vienna`, or `LCG.HEPHY.at`).

Never attach `userkey.pem` or a proxy file. EOS mapping requests and missing grid tools also go to the HPC Servicedesk.

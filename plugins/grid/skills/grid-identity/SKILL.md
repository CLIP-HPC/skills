---
name: grid-identity
description: "Set up and check a grid identity for ALICE, CMS, or Belle II work at the Vienna BioCenter: request a CERN grid certificate, convert the .p12 into ~/.globus/usercert.pem and userkey.pem, fix file permissions, join a VO (VOMS or IAM), create and inspect VOMS proxies with voms-proxy-init and voms-proxy-info, use X509_USER_PROXY in Slurm jobs on CBE.next, renew proxies, and get the certificate DN mapped for EOS. Use for grid certificate, DN, VOMS, proxy, FQAN, and X509_* questions; use grid-data for transfers, grid-jobs for submission, and grid-triage for failures."
metadata:
  display-name: "Grid identity"
  short-description: "Grid certificates, VO membership, and VOMS proxies"
  example-task: "set up my grid certificate and create a CMS VOMS proxy."
---

# Grid certificates and VOMS proxies

Facts below reflect the docs.vbc.ac.at pages as of 2026-10-28. Items marked *not available yet* may have changed.

The grid identity has three layers, and most problems come from mixing them up:

1. **Certificate:** a personal X.509 certificate from a grid CA. Its subject (the DN) identifies the person. Valid for about a year.
2. **VO membership:** the experiment (ALICE, CMS, Belle II) registers the DN in its VOMS or IAM service. The VO, its groups, and its roles appear as FQANs, for example `/cms/Role=NULL/Capability=NULL`.
3. **Proxy:** a short-lived certificate signed by the user's own certificate, carrying a VOMS attribute certificate. Grid tools authenticate with the proxy, not with the certificate.

## Hard rules

- The private key `userkey.pem` never leaves the user's own accounts: never copy it to `/groups`, `/clustertmp`, `/eos`, a job script, a ticket, or a chat. Never print it.
- Never create or share certificates or proxies for another person. Service and robot certificates need the HPC Servicedesk.
- A proxy is a credential too: keep it mode 600, outside shared directories, and don't attach it to tickets.
- Ask the user to type passphrases themselves. Never put them in commands, scripts, or files.

## Get a certificate

The VBC docs describe a CERN grid certificate, which needs a CERN account:

1. Request it at https://ca.cern.ch/ca/user/Request.aspx?template=EE2User and download the `.p12` file.
2. Copy the `.p12` to the machine that uses it, then extract certificate and key:

   ```bash
   mkdir -p ~/.globus && chmod 700 ~/.globus
   openssl pkcs12 -in myCert.p12 -clcerts -nokeys -out ~/.globus/usercert.pem
   openssl pkcs12 -in myCert.p12 -nocerts -out ~/.globus/userkey.pem
   chmod 644 ~/.globus/usercert.pem
   chmod 400 ~/.globus/userkey.pem
   rm myCert.p12
   ```

   The VBC docs add `-nodes`, which stores the key unencrypted. Without `-nodes`, `openssl` asks for a new PEM passphrase and the key stays encrypted on disk; `voms-proxy-init` then asks for it each time. Prefer the encrypted key, unless the user needs unattended proxy creation and accepts the risk.
3. Check the result:

   ```bash
   openssl x509 -in ~/.globus/usercert.pem -noout -subject -issuer -enddate
   ```

Other IGTF-accredited CAs, such as a GÉANT TCS personal certificate from the home institute, also work for the grid when the experiment accepts them. Renew before `-enddate`; a new certificate with a new DN needs re-registration in the VO and a new EOS mapping.

## Join a VO

Registration happens with the experiment, not at the VBC: the user signs in to the VO's registration service with the certificate loaded in the browser (import the `.p12`) and waits for approval.

- CMS: the CMS IAM, https://cms-auth.cern.ch/
- ALICE: the ALICE IAM, https://alice-auth.cern.ch/
- Belle II: follow the Belle II computing newcomer instructions; registration uses the Belle II VOMS at KEK.

Check the experiment's own documentation for the current procedure, which changes as VOs move from VOMS-Admin to IAM.

## Create and inspect a proxy

`voms-proxy-init` and `voms-proxy-info` are *not available yet* on CBE.next (docs, COPS-232). Check first:

```bash
command -v voms-proxy-init voms-proxy-info
```

If they're missing, an experiment environment from CVMFS may provide them (see `grid-software`); otherwise create the proxy on another machine with grid clients, or tell the user the tools aren't installed yet and point to the HPC Servicedesk. Don't install CA bundles or VOMS configuration by hand into `$HOME`.

```bash
voms-proxy-init --voms cms --valid 96:00     # or: alice, belle
voms-proxy-info --all                        # identity, FQANs, timeleft
voms-proxy-info --timeleft --actimeleft      # seconds left: proxy, VOMS attributes
```

- The VOMS server caps the attribute lifetime; asking for more prints a warning and gives less. `--actimeleft` is the one that matters for grid storage and job submission.
- `--voms cms:/cms/Role=production` requests a role; regular users don't need one.
- Some experiment tools create proxies themselves: CRAB calls `voms-proxy-init`, Belle II uses `gb2_proxy_init -g belle`, and ALICE JAliEn uses the certificate in `~/.globus` to obtain its own token, without a VOMS proxy.

## Proxies in Slurm jobs on CBE.next

The default proxy file is `/tmp/x509up_u$(id -u)`. On CBE.next, each job has a private `/tmp`, so a job can't see a proxy created on the login node there. Write the proxy to `$HOME` and point the job at it:

```bash
voms-proxy-init --voms cms --valid 96:00 --out "$HOME/.globus/proxy.pem"
chmod 600 "$HOME/.globus/proxy.pem"
```

```bash
#SBATCH ...
export X509_USER_PROXY="$HOME/.globus/proxy.pem"
voms-proxy-info --exists --valid 2:00 || { echo "proxy expires too soon" >&2; exit 1; }
```

- Request a proxy that outlives the job, including queue time. If a job runs longer than the VOMS attribute can last, split the job or stage its data before the proxy expires.
- Don't put the proxy in `/groups`, where group members could read it.
- Grid jobs submitted through an experiment framework handle proxy delegation themselves; see `grid-jobs`.

## EOS mapping

XRootD and WebDAV access to `eos.grid.vbc.ac.at` needs the certificate DN on the EOS mapping list. Get the DN with:

```bash
openssl x509 -in ~/.globus/usercert.pem -noout -subject -nameopt RFC2253
```

Then open an HPC Servicedesk ticket with the DN and the EOS path needed; the `cbe-ticket` skill drafts it. A new certificate with a different DN needs a new mapping.

## Tokens

WLCG is moving from X.509 proxies to tokens (WLCG JWTs from the VO's IAM). Experiment tools adopt them step by step, and the VBC docs don't describe token access to EOS yet. Use proxies unless the experiment's documentation for the specific tool says otherwise.

## Details (fetch as Markdown)

- https://docs.vbc.ac.at/research-computing/cbe/transfer-data/index.md (section "Grid, EOS, XRootD, and VOMS")
- Support: the HPC Servicedesk (https://vbc.atlassian.net/servicedesk/customer/portal/5/group/6).

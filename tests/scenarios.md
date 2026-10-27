# Manual behavior checks

Run these in a fresh conversation after installing the plugin in each host.
In Claude Code, `plugins/cbe/evals/` automates these checks; see the README. Here they are review scenarios. Use supplied
scripts and logs rather than connecting to a production cluster for the check.

| Prompt | Expected behavior |
|---|---|
| “Adapt this sbatch script for CBE.next.” Attach a small CPU script. | Select `cbe-next`; use an explicit time limit, suitable partition, and modules inside the script. Prepare a reviewable change. |
| “This CBE.next job was killed. Diagnose it.” Attach logs and accounting data showing `OUT_OF_MEMORY`. | Select `cbe-triage`; use the evidence, propose a small reproduction, and draft a fix. Avoid rerunning production or creating a ticket without authorization. |
| “Move this legacy CBE workflow to CBE.next.” Attach a script with `/scratch`, `/scratch-cbe`, and a legacy QOS. | Select `cbe-migrate`; distinguish the old exchange share from new scratch, translate a copy, and flag needed transfers. |
| “Can we make this working CBE.next job faster?” Attach a script and resource measurements. | Select `cbe-tuning`; propose changes backed by the supplied measurements and a small test plan. |
| “Why does my CBE.next job take so long to start? Did submitting many jobs give me low priority?” Attach `sprio` and `sshare` output. | Select `cbe-queue`; explain priority from the supplied numbers, correct the many-jobs misconception, name the account level that lowers fair-share, and mention backfill and age. |
| “My RStudio session on OpenOnDemand never starts. Open a ticket.” Attach the session log. | Select `cbe-ticket`; collect the session ID, job ID, form values, log excerpt, and browser. If they show a cause the user can fix, offer to fix it first; otherwise ask for what is missing, show the draft, and create it only after approval. |
| “My job has been pending for two days with reason `Priority`. Should I open a ticket?” | Select `cbe-queue`; explain the wait and say that it isn't a reason for a ticket unless the evidence points to a scheduler fault. |
| “Where should this CBE.next job store intermediates and retained results?” | Select `cbe-data`; distinguish temporary scratch from retained group data and preserve the documented storage rules. |
| “How do I find and load this tool on CBE.next?” | Select `cbe-software`; begin with the documented software sources and environment checks. |
| “Set up a reproducible conda environment for this CBE.next project.” | Select `cbe-python`; check the user's dotfiles and quota, write a tracked `environment.yml` with conda-forge and Bioconda, create it by path, and commit a `conda-lock.yml`. No `conda init`, `defaults` channel, or `/scratch`. |
| “Explain an ordinary local Python function.” | Do not activate an unrelated CBE skill. |

Also select each of the nine skills explicitly in the host's picker and check
that the expected instructions load. If a specialist skill references a sibling,
confirm that the sibling is available in the installed bundle.

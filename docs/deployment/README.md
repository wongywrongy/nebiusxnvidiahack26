# Public deployment — October 28, 2026

**[Open SpecCheck](https://speccheck-wongywrongys-projects.vercel.app)** · [Frozen configuration](final-deployment.json) · [Public smoke, browser captures and accounting](../customer-feedback/release-20261028/README.md)

The customer-feedback build is deployed on Nebius endpoint `aiendpoint-e01fxw4c8jd1yq6nn5` in eu-west1, cpu-d3 / 2 vCPUs / 8 GB, with a 32 GiB container disk. Runtime source `14ddb6d` is frozen at image digest `d5b22ed554d26dac83808ea53155d8a28d03bd3f2c6623171cb6b5321093bb07`. [Native origin](https://port8000-j0946t8fwr9bm40.tunnel.applications.eu-west1.nebius.cloud). Vercel rewrites the stable URL to that origin; no new Vercel functions or secrets were added.

The original filesystem `computefilesystem-e01syzwfv7rqexfcys` remains mounted at `/state`. Before and immediately after replacement, the ledger retained exactly $1.12675158 / 313 credits, plus the actual GitHub Actions re-check report and existing uploads. The old endpoint was stopped before the replacement started writing, then deleted with explicit approval after public checks passed.

No-admin fresh smoke and all five public browser journeys passed, together with the printable memo, updated Scoreboard and a fresh Check approved now result. The latter correctly flags the watched Lithonia 2TL4 as discontinued. Screenshots and unmodified traces are in the release evidence directory. The full live panel is now **4/8 calls, 4/6 problems, 0/2 major false alarms, 0/5 passing replacements**, with **0/14 wrong-spec approvals**. This is a small known set with cached calls; the strict case evidence gate fails and the regression is disclosed.

The GitHub Actions fallback was commissioned successfully at 07:22:37 UTC on October 28. Its settled isolated ledger charged **$0.06667272 / 13 credits**, with no holds. The 09:00 UTC daily schedule is enabled, capped at $0.50 / 40 credits per execution and stops provider calls after December 15, 20:00 UTC. A manual workflow execution is proved; a cron-triggered execution has not yet been observed. No Nebius Serverless Job execution is claimed. [Setup and real run](../../deploy/nebius/recheck-job.md).

Additional measured charges for this continuation: **$0.69773058 model USD / 70 Tavily credits** across local recording, the GitHub job and hosted checks. Final judging allowance remaining: **$73.84025352 / 5,676 credits**; daily caps remain $8 / 600, run $3, concurrency 2. Cloud/CI billing was not measured. Planned availability continues through December 15, 2026, 20:00 UTC.

[October 27 deployment record](final-deployment-20261027.json) and the older health/smoke files in this folder are historical. Current proof and the freeze timestamp are in the October 28 release directory.

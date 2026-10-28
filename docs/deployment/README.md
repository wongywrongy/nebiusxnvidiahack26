# Public deployment — final release, October 28, 2026

**[Open SpecCheck](https://speccheck-wongywrongys-projects.vercel.app)** · [Frozen configuration](final-deployment.json) · [Public checks and screenshots](../release-final/README.md)

Source `3d35d10` (branch `release/final`: master `30ca3ec` + per-item scores fix `4138a41` + custom-checklist fix `1e7f436` + smoke probe `20cca85`) is deployed by digest `sha256:4be93dc8eeb1de118218e5e16f96e2ead88aaf6ce4cc32cf31211111f77878e1` on Nebius endpoint `aiendpoint-e01cg2e1rfwpvfpnb0` in eu-west1 (cpu-d3, 2 vCPUs, 8 GB, 32 GiB disk). The [native origin](https://port8000-gysms8dcks7n3zb.tunnel.applications.eu-west1.nebius.cloud) sits behind Vercel deployment `dpl_68tw1EwhVyfmwJUXLnhp6JCtJicY`, which rewrites the stable URL to it.

The filesystem `computefilesystem-e01syzwfv7rqexfcys` stays mounted at `/state`. The previous endpoint `aiendpoint-e01y93s8ffx7g7wern` was stopped at 19:44:58 UTC, before the new one wrote anything. The stable URL served the new endpoint from 19:52:00 UTC, about 7 minutes later. The old endpoint was deleted only after every public check passed. The ledger read exactly **$1.82596578 / 388 credits** before and after the swap, with no holds.

## What the Scoreboard shows

Recorded run `20261028-173729-554074` (arm A of the [same-day A/B](../customer-feedback/accuracy-arms-20261028/README.md)) was recorded on `4e6066b`, the code on master. The deployed source adds only:
- a fix to how per-item time and cost are averaged;
- the custom-checklist drafting fix;
- a verification-tool change.

Every model request for the eight stock cases is byte-identical between the two ([parity](../release-final/stock-request-parity.json)).

| Right calls | Problems caught | Clean cases wrongly flagged | Unnecessary notes | Passing replacements |
| --- | --- | --- | --- | --- |
| 6 / 8 | 5 / 6 | 1 / 2 | 0 | 0 / 5 |

Wrong-spec check: 0 of 14 approved (13 not applicable, 1 sent back), run `20261028-183608-dfa1b9`. Run-to-run variance: the same-day PR #20 run `20261028-171142-5ca0fc` differed only on c05; c05 flips between runs. The strict case gate fails, and no passing replacement or Investigator rescue is claimed.

## Public checks (no admin token, through the stable URL)

Smoke, five browser journeys (off-topic upload, Try-one upload, UBC spec → draft → Schlage, tray scan → matrix → Review → Outcome, one product under two specs), the memo/PDF and Scoreboard, and a fresh Check approved now all passed. They cost **$0.2844459 / 21 credits**. The judging allowance left is **$72.88958832 / 5,591 credits**; daily caps stay at $8 / 600, $3 per run, concurrency 2. Cloud and CI billing were not measured.

## Daily re-check

The GitHub Actions fallback keeps its pinned image. Its October 28 manual run is proved ($0.06667272 / 13 credits, Lithonia discontinued). The first cron event fired at 15:37 UTC ([run 40717808721](https://github.com/wongywrongy/nebiusxnvidiahack26/actions/runs/40717808721)) and skipped providers because that day's report already existed. No Nebius Serverless Job execution is claimed. [Setup](../../deploy/nebius/recheck-job.md).

## History

- [Afternoon `a81d9d2` deploy](final-deployment-20261028-afternoon.json), with its [evidence](../customer-feedback/accuracy-release-20261028/README.md).
- [Morning manifest](final-deployment-20261028-morning.json).
- [October 27 manifest](final-deployment-20261027.json).

# Accuracy release evidence — October 28, 2026 (afternoon)

PR #20 (grounded extraction identity, numbered-list repair, bounded drafts) recorded live on the merged code, `dd878da` tree. One full recording, shared local ledger and cache, production judging caps (run $3, item 60 credits, concurrency 2, one fix candidate). No second full run.

## Live recording

`runs/recorded/20261028-171142-5ca0fc/`: eight cases plus s3 and s4. All ten results are live and valid, with no warnings. Log: [record.log](record.log).

| Measure | October 22 | October 28 (morning) | October 28 (this run) |
| --- | --- | --- | --- |
| Right calls | 6/8 | 4/8 | **6/8** |
| Planted problems caught | 5/6 | 4/6 | **5/6** |
| Major false alarms on clean cases | 0/2 | 0/2 | **0/2** |
| Passing replacements | 0/5 | 0/5 | **0/5** |
| Unnecessary notes | 1 | 2 | **1** |
| Wrong-spec approvals | — | 0/14 | **0/14** |

This restores the October 22 panel; it does not exceed it.

### Every changed decision

| Item | Expected | Oct 22 | Oct 28 morning | This run |
| --- | --- | --- | --- | --- |
| c01 | approve | approve | approve with note | **approve** |
| c04 | send back | send back | approve with note | **send back** |

- **c01 versus Oct 28: approve with note → approve.** Only explicit option claims now produce Specify lines, and the printed model binds the document's display name. Same decision as Oct 22.
- **c04 versus Oct 28: approve with note → send back.** The numbered penetrating-item list is kept whole, so the steel-pipe requirement fails against the plastic-pipe system again. Same decision as Oct 22.
- **Versus Oct 22: no decision changed** for any of the ten items.
- c02, c03, c05, c06, c07, c08, s3 and s4 hold the same decision in all three runs. c05 (approve with note vs approve) and c06 (approve with note vs send back) remain wrong; c06's planted currency problem is still missed, as the PR handoff states. c08 took 314 s.

The strict case evidence gate still **fails**: two wrong calls, one missed problem, one unnecessary note, no evidenced passing replacement, no demonstrated Investigator rescue. The answer key and reviewed checklists were not changed.

## Wrong-spec check, re-run on the new code

Extraction changed, so the fixed 14-document set was re-run live under a hard $0.50 ceiling (run `20261028-171959-1f6c87`, [log](wrong-spec.log)): **0/14 approved**, 13 not applicable, **1 other**. That one is w-c05: the LED troffer checked against firestop section 07 84 00 was **sent back** (fails test standards) instead of being marked not applicable. It is not an approval, so the false-approval measure holds, but the off-topic guard let it through; on the morning build all 14 were not applicable. The block is written into the recorded `scores.json`.

## Daily fallback: first cron event

[GitHub Actions run 40717808721](https://github.com/wongywrongy/nebiusxnvidiahack26/actions/runs/40717808721) was **cron-triggered** (`event: schedule`). GitHub started the 09:00 UTC slot at 15:37:17 UTC. Because the 07:22 manual report was already today's live GitHub Actions report, the re-check step was **skipped**: no provider calls, $0 / 0 credits, public ledger unchanged at $1.15974648 / 324. A cron event is now observed; a cron-triggered re-check that actually ran providers is not yet. [github-recheck-cron.json](github-recheck-cron.json).

## Accounting

Shared local ledger: **$2.20976732 / 159 credits** before; recording **$0.72872730 / 19**; wrong-spec **$0.11095470 / 8**; after **$3.04944932 / 186**, no holds. Incremental **$0.83968200 model USD / 27 Tavily credits**. [accounting.json](accounting.json), [before](local-ledger-before.json), [after](local-ledger-after.json). Hosted commissioning, including failed attempts: **$0.66621930 model USD / 64 Tavily credits**. Public total: **$1.82596578 / 388**, no holds; judging remaining **$73.17403422 / 5,612 credits**. Cloud and CI billing are not measured.

## Deployment

**[Open SpecCheck](https://speccheck-wongywrongys-projects.vercel.app)**. Frozen **October 28, 18:43:03 UTC**, before the October 29, 02:00 UTC deadline. Runtime source `a81d9d2` follows handoff source `8f91ae9`; [the public draft regression and fix](public-gate-fix.md) explain the change. The Git source and docs are committed locally on `deploy/accuracy-release`; no Git push or new CI run was performed, per the handoff.

- Image: `ghcr.io/wongywrongy/speccheck@sha256:a7a6dab1a2460e5ba745ee29b3060f4e44ded3e563aa3f8eccb597348e25166f` (`accuracy-a81d9d2`).
- Endpoint: `aiendpoint-e01y93s8ffx7g7wern`, cpu-d3 / 2vcpu-8gb / 32 GiB, port 8000, auth none, unchanged MysteryBox references and judging caps.
- Filesystem: `computefilesystem-e01syzwfv7rqexfcys` at `/state`. Ledger before/after the fixed swap: exactly **$1.59951768 / 360**, no holds. Existing watch report and prior upload survived.
- [Native origin](https://port8000-d38t85f0yhyyzek.tunnel.applications.eu-west1.nebius.cloud); Vercel production deployment `dpl_4BwLP7PxhBiaykM2JMSf7cfCN94Z` rewrites the unchanged stable URL to it.
- Both superseded endpoints were stopped before their replacements wrote, then deleted only after every public check passed. The filesystem remains.

### Public acceptance on the fixed image

| Check | Result | Incremental model USD / credits | Evidence |
| --- | --- | --- | --- |
| No-admin bounded smoke, real new PDF probe | Pass; fresh Nano and Super calls | $0.00069840 / 0 | [run 20261028-183136-799436](public/smoke-results.json), [stdout](public/smoke.txt) |
| a: off-topic upload | Pass | $0 / 0 | [trace](public/a-trace.json) |
| b: Try-one product sheet | Pass | $0 / 0 | [trace](public/b-trace.json) |
| c: fresh UBC draft → edit/delete → Schlage → scoped review | Pass; 2 matched rules, 4 grounded claims, 25 excluded rules | $0.03820680 / 0 | [trace](public/c-trace.json) |
| d: seven-item tray → review → Outcome | Pass | $0.09265830 / 8 | [trace](public/d-trace.json) |
| e: correct versus wrong spec | Pass | $0 / 0 | [trace](public/e-trace.json) |
| Memo/PDF and Scoreboard | Pass; recording `20261028-171142-5ca0fc` | $0 / 0 | [proof](public/memo-scoreboard.json), [PDF](public/memo.pdf), [Scoreboard](public/scoreboard.png) |
| Check approved now | Pass; real fresh web, quoted discontinued status | $0.09488460 / 15 | [proof](public/check-approved.json), [capture](public/check-approved.png) |

The first `8f91ae9` deployment attempt cost **$0.43977120 / 36 credits** and remains in `public-8f91ae9-attempt/`, including failed c and the initial b stream disconnect. On the fixed image, two original smoke attempts correctly failed cached-only freshness; the fresh-web attempt spent **0 USD / 5 credits**. Those attempts remain in `public/`. Two browser-inspector upload failures before Check approved started any scan cost $0 / 0 and are also retained. Total hosted increment: **$0.66621930 / 64 credits**. All acceptance ledger holds are settled. [Accounting](accounting.json).

The displayed **6/8, 5/6, 0/2, 0/5** panel is the saved afternoon recording on `8f91ae9`, retained in the fixed image. The fix leaves all 13 stock extraction batches' prompts, schemas and contexts identical; it changes custom-checklist extraction and drafting. No new eight-case accuracy recording is claimed. The public tray is a workflow check: c01 produced approve with note there, while the saved recording has approve. The known c05/c06 errors, missed c06 problem and 0/5 passing replacements remain disclosed; the strict case gate still fails.

Full image-source mock suite: **797 passed, 2 skipped**; standalone smoke tool: **10 passed**. The clean image has 13 hash-locked public PDFs, the 10-result recording, no `runs/scores.json`, no configured secret values, and passed its network-disabled API/package/PNG/memo proof. [Acceptance](acceptance.json), [freeze](freeze.json), [deployment manifest](../../deployment/final-deployment.json).

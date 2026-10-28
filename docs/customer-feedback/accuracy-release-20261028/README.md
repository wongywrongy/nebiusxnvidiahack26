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

Shared local ledger: **$2.20976732 / 159 credits** before; recording **$0.72872730 / 19**; wrong-spec **$0.11095470 / 8**; after **$3.04944932 / 186**, no holds. Incremental **$0.83968200 model USD / 27 Tavily credits**. [accounting.json](accounting.json), [before](local-ledger-before.json), [after](local-ledger-after.json). Hosted verification charges are added after deployment. Cloud and CI billing are not measured.

## Deployment

Pending: new pinned image from this commit, replacement endpoint on `computefilesystem-e01syzwfv7rqexfcys` at `/state`, Vercel rewrite to the new tunnel, then public smoke, the five journeys and memo. See [HANDOFF.md](HANDOFF.md).

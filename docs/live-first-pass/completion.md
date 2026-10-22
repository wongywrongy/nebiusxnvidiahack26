# First live pass completion audit — 2026-10-22

The authorized first pass is complete with disclosed accuracy limitations. Kyle directed continuation through
handoff on October 22 after the four allowed full evaluations. No checklist row, answer-key expectation,
deployment or cloud resource was changed to obtain a better score. **Recommendation: do not deploy on Oct 22.**

| Panel | Original mock baseline | Recorded live cases |
| --- | ---: | ---: |
| Right calls | 8/8 | 6/8 |
| Problems caught | 6/6 | 5/6 |
| Major false alarms | 0/2 | 0/2 |
| Passing fixes | 2/5 | 0/5 |

Live samples: 1/4 right calls, 0/2 problems, 0/3 major false alarms, 0/1 passing fix. Unnecessary notes are
wrong calls even when the major-false-alarm counter is zero. Final case gates kept 149/185 claims and 27/40
web values (19.5% / 32.5% dropped). No cap/provider warning invalidated either final evaluation.
Final case timing was 3.365 s/item warm-cache and $0.033602 usage-equivalent/item, not an uncached benchmark.
Two primary investigations ran: one found a revision, none resolved the missing planted problem, none capped.
Four replacement investigations ran without caps; no passing replacement resulted.

## Phase evidence

| Work | Result / repository evidence |
| --- | --- |
| Setup / documents | Master 9568d1c baseline, four user files untouched, all 13 manifest PDFs readable with native text. [Dated notes](../live-first-pass.md). |
| Models / tools / hosts | NVIDIA IDs listed, schema-valid JSON, one native tool call with JSON arguments, thinking-off reasoning 0 in spikes; manufacturer extracts usable with host-specific exceptions. [FEEDBACK](../../FEEDBACK.md), model/host evidence beside this file. |
| Spec review | Exactly Kyle's four firestop/five lighting rows saved, reviewed_at 2026-10-21. String normalization tested. No expectations edited. [Review](checklist-review.md). |
| Live cases / samples | Four full evaluations used, 3/8 → 5/8 → 6/8 → 6/8. Targeted retries and stage diagnoses include swallowed caps/provider checks. [Final roots](gate4-review.md). |
| Recording | [20261022-181611-a9d0b5](../../runs/recorded/20261022-181611-a9d0b5/scores.json): c01–c08 plus s3/s4, cases-only scoreboard. All responses cached from this live pass, $0/0 fresh recording spend. |
| Replay | GET scores serves live recording; explicit replay returns ten results; zero-cap full public tray/watched scan replays all eight requested IDs. [API](phase5-api.json), [low cap](phase5-low-cap.json), [restored caps](phase5-cap-restored.json). |
| Secret handling | Both keys and admin token absent from every recorded file, boolean check per file. [Scan](phase5-secret-scan.json). Final artifact check is boolean-only. |
| Judge walk | Inbox → Scan → Review → Outcome, manual approved re-check, Specs, Scoreboard, real unseen public PDF, screenshots and remaining misleading lines. [Walk](judge-walk/README.md). |
| Smoke | Live local run 20261022-182735-a950f9 passed, including a deliberately fresh Nano call. [Output](phase6-smoke.txt), [ledger](phase6-smoke-ledger.json). |
| Handoff | README/SUBMISSION show live panel; FEEDBACK has dated redacted requests, responses and repro. Branch live/first-pass targets master. PR link is recorded below. |

Local checks used **127.0.0.1:8001**, because unrelated software owned 8000. That service was left alone.
Private `.env` has requested production caps: $3/run, $8/day, 60 credits/item, 600/day, concurrency 2.
Validated process-only retry settings: output 32,768; investigate 24 steps / 30 shared credits; fix 40 credits.
Code/config quality defaults remain unchanged. Public uploads are not part of the committed demonstration key.

## Spending and billing

October 21 ledger **$1.048778 / 291**; October 22 **$0.009827 / 7**; pass total **$1.058605 / 298 credits**.
Owner dashboard checkpoint before October 22 checks was **$1.05 / 288**. Computed dollars agree to cent
precision; the three-credit gap is unresolved. Three early estimated search credits match the gap numerically,
but causality/account scope are unproven and the ledger was not altered. This is not a final account invoice.
[Redacted usage/ledger summary](phase6-live-summary.json). Both pass ceilings were respected.

## Remaining work, ranked for Kyle

1. **Missed defects: c06 and tray sample s3.** Resolve exact manufacturer-document identity and selected product
   configuration before comparing old/current values. Do not treat a different family variant as proof.
2. **Zero passing live fixes.** Replacement discovery and candidate evidence remain weak; absent original failed
   requirements now block an apparent pass. Do not demo a successful live replacement.
3. **Unnecessary notes and long extraction.** Clean c05/s2 lose L70/warranty/DLC evidence; page excerpts crop
   real text and option selection is unresolved. s3 emitted 25,484 output tokens with thinking off.
4. **Requirement/semantic limits.** F04 missing-pair applicability needs an explicit policy; product-type scoping
   remains future work. 90G9 revision metadata, power-as-lumens, and G21 “Class 0” parsing remain documented.
   c01's generated “all requirements” summary is broader than the checks establish.
5. **Billing and cloud proof.** Reconcile the three-credit gap with scoped dashboard data when available.
   Deployment, nightly execution, persistence and a public URL/video still require their separate authorized pass.

No deployment, endpoint/job/bucket/secret creation, real nightly run, mobile audit or cold eight-case benchmark
was performed. The owner-provided October 30 submission and December judging dates were not independently
revalidated; this pass concerns the existing repository and local/live provider evidence.

## Reproduce

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/speccheck-mock.json
(cd web && npm run test:presentation && npm run build)
.venv/bin/python scripts/fetch_docs.py
.venv/bin/python scripts/check_pdfs.py
.venv/bin/python scripts/spike_models.py --yes --tools
.venv/bin/python scripts/spike_tavily.py
export MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40
.venv/bin/python scripts/eval.py --case c03
.venv/bin/python scripts/eval.py --case c07
.venv/bin/python scripts/eval.py --out /tmp/speccheck-live.json
.venv/bin/python scripts/eval.py --samples --out /tmp/speccheck-samples.json
.venv/bin/python scripts/record_live.py
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8001
# Separate shell; ADMIN_TOKEN privately in environment:
.venv/bin/python scripts/smoke.py http://127.0.0.1:8001
```

Live commands spend on cache misses; these document reproduction and do not authorize a fifth Phase 4 full
run in this pass. Retain reviewed checklists; drafting again is unnecessary for replay. Read both UTC ledgers
for the pass total. Never echo credentials or commit `.env`, `.cache/`, `data/raw/` or unrecorded runs.

Final validation: **247 passed, 2 skipped in 12.42 s**; mock eval `20261022-183901-964db3` **8/8**,
6/6 problems, 0/2 major false alarms, 2/5 fixes; 45/48 claims, 19/20 web values retained.
Presentation assertions passed and the production web build completed in **5.76 s**.

PR: [#12 — first live pass](https://github.com/wongywrongy/nebiusxnvidiahack26/pull/12), `live/first-pass` → `master`.
All first-pass code, reviewed checklists, recorded replay, diagnostics and judge captures are committed.
The PR remains for review; it was not merged or deployed.

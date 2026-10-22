# Judge readiness — implementation ledger

Kyle approved the comprehensive refinement plan on 2026-10-22. Historical first-pass evidence and answer keys stay unchanged.

## Locked decisions

- Full review → fix → watch; strict release gate.
- Independent AI audit plus Kyle's spec and practical review; no independent human-study claim.
- Browser approvals have manual re-check; scheduled monitoring covers bundled watched samples only.
- Missing assembly ratings on product-data-only packages appear as pending proof, without changing the product-data verdict. Submitted assemblies with missing ratings remain unconfirmed.
- NVIDIA Nano/Super only; exact source quotes, numeric bounds, metric identity and product configuration remain mandatory.
- Cumulative provider ceiling $20 / 2,000 credits; baseline $1.058605 / 298. Engineering allocation at most $10 / 1,000 additional; retain $8.941395 / 702 for final validation and judging.
- Keep Endpoint + Serverless Jobs. No deployment/resources until a concrete manifest, current cost/credit-expiry review and Kyle's separate approval.

## Gates

| Gate | Acceptance | Status |
| --- | --- | --- |
| G1 | Validity and fresh-spend accounting, configuration manifests, CI, assembly-policy regressions | Implemented; awaiting Kyle's gate review |
| G2 | General extraction/identity/freshness fixes; verified replacement and genuine Investigator rescue | Pending |
| G3 | Unchanged-key cases/samples, independently prepared blind packages, independent AI audit | Pending |
| G4 | Approved hosted rollout, restart/storage proof, public smoke, real manual and scheduled jobs | Pending owner deployment approval |
| G5 | Full public recording, screenshots/video, truthful submission, reviewed release PR | Pending |

## Process

Diagnose result → check stage validity and ledger → fix one general cause → regression checks → affected live items.
Do not reopen the four-run first pass. The follow-up allows two full scoring-set evals plus one final recording, inside the cumulative ceiling.
Every source/expectation contradiction needs Kyle's dated URL/quote adjudication. An unresolved contradiction blocks readiness; never rewrite the key.
No new track, extra spec sections, Ultra experiment, email integration, durable approval enrollment or visual redesign.

## Remaining implementation

1. Complete document chunks with page-grounded quotes; bounded merge and semantic numeric/identity checks.
2. Pending assembly scope and deterministic report coverage; compatible API/browser states.
3. Original web fetch times, 24-hour cache age and fresh approved/scheduled checks; preserve model cache by content.
4. Replacement evidence bundles and per-check citations; distinct Investigator retrieval/resolution outcomes.
5. Durable campaign reservations, failed/retried usage accounting and job leases; authenticated idempotent controller-only job launches and report publication.
6. Browser journey/failure tests, independent source-labelled validation set, current pricing/credit manifest, release build document preflight.
7. Targeted live validation, final case/sample/blind panels, recorded evidence and updated PR/submission.

## Assembly-policy consequence

The first-pass mock c03 replacement appeared to pass because absent F/T proof was skipped. With explicit pending assembly proof, that replacement remains unconfirmed. The original 2/5 mock-fix panel stays historical; current mocks must still make all 8/8 calls correctly, but no test should restore an unsupported replacement pass. No source, checklist or answer-key expectation is edited for this correction.

## G1 evidence — 2026-10-22

The independent AI reviewer identified uploaded-assembly scoping, omitted pending proof in drafts, unchecked public recording extras, malformed paid-response accounting and missing answer-key hashes. Those findings are fixed with regressions. The final replay finding is handled in the UI: historical summaries and newly generated approval drafts cannot repeat the old blanket coverage claim; the original recording remains unchanged.

Validation in this session:

- `SPECCHECK_MODE=mock .venv/bin/python -m pytest -q`: **262 passed, 2 skipped** (12.52 seconds).
- `SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/speccheck-readiness-g1.json`: **8/8 calls, 6/6 problems, 0/2 major false alarms, 1/5 passing fixes**, 0 invalid items, 0 unnecessary notes. [Full scoreboard](judge-readiness/g1/mock-scores.json), run `20261022-194346-d0279a`.
- Quote gates: **45/48 claims**, **19/20 web values**. These are fixture results, not fresh live evidence.
- `cd web && npm run test:presentation && npm run build`: passed, including pending/legacy approval-draft checks.
- `git diff --check`: clean.

Mock evaluation fresh charges: **$0 / 0 credits**. Actual date ledgers remain October 21 **$1.048778 / 291** and October 22 **$0.009827 / 7**; cumulative **$1.058605 / 298**. No fresh provider calls were made for G1.

G1 adds typed invalidity, failed-attempt time/spend, fresh versus usage-equivalent reporting, guarded recording of every public item, manifests hashing runtime settings/code/checklists/answer-key inputs, and PR/image regression workflows with pinned dependency constraints. [GitHub checks passed for implementation commit `2fcc0d0`](https://github.com/wongywrongy/nebiusxnvidiahack26/actions/runs/39842769408), including clean dependency installation, pytest, mock eval, presentation checks and web build on Node 22.

G1 does **not** establish new live accuracy, a passing live replacement, an Investigator rescue, durable campaign reservations, browser journey coverage or deployment readiness. The release gate therefore remains closed. The historical dashboard discrepancy is still unresolved; no billing ledger has been adjusted.

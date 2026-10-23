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
| G1 | Validity and fresh-spend accounting, configuration manifests, CI, assembly-policy regressions | Accepted by Kyle on 2026-10-22 |
| G2 | General extraction/identity/freshness fixes; verified replacement and genuine Investigator rescue | In progress |
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

The first-pass mock c03 replacement appeared to pass because absent F/T proof was skipped. With explicit pending assembly proof, that replacement remains unconfirmed. The original 2/5 mock-fix panel stays historical; no test should restore an unsupported replacement pass. Kyle's later selection-policy adjudication below supersedes the original 8/8 mock acceptance requirement without changing the raw key or release gate.

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

## G2 policy checkpoint — 2026-10-22

Kyle explicitly chose: **require a selected configuration in submitted evidence; leave unselected options unconfirmed**. An ordering example, blank catalog field or family-only inbox label does not select a configuration. The original answer key and reviewed requirements remain unchanged.

That policy exposes a conflict with the original requirement that the mock panel remain 8/8. The measured checkpoint is [run `20261022-210601-d5edbe`](judge-readiness/g2/mock-scores.json): **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**, no invalid items, one note on an originally clean item. Quote gates keep **48/65 claims and 8/20 web values**. Fresh charges are **$0 / 0 credits**. Kyle authorized the disclosed policy exceptions and targeted live validation on 2026-10-22 ("ok lets do that i give permission for live validation"). This remains a raw-key disagreement, not a passed G2 or a successful live run.

| Package | Original key | Strict result | Source evidence and cause |
| --- | --- | --- | --- |
| c05 (and s2 using its fixture) | approve | approve_with_note | [BLT sheet](https://michaelsforms.eastus2.cloudapp.azure.com/prod_image/blt-2x4.pdf), page 2: `EZ1` / `eldoLED dims to` / `1% (0-10 volt dimming)`; a separate `GZ10` option dims to 10%. The catalog field is blank. A 1% value belongs to EZ1, not every BLT. |
| c06 | send_back for currency | approve_with_note | [Submitted LDN6 sheet](https://assets.usesi.com/product-media/specification-sheets/USESI_531911_specification_sheets.pdf), page 1 prints an ordering example, not a selected SKU. Page 3 performance depends on target lumens and CCT. [Current source](https://dublinohiousa.gov/alpha/wp-content/uploads/2023/01/C1_Lighting.pdf) quotes a different revision, but no selected matching performance configuration is established. |
| c07 replacement | originally passing BLT in mock | no passing replacement | The same unselected EZ1 dimming option cannot satisfy a replacement check for the whole product. It needs a specified configuration and its evidence. |

The [full suite at this checkpoint](judge-readiness/g2/pytest.txt) reported **344 passed, 9 failed, 2 skipped** in **14.93 seconds**. The nine failures are existing assertions requiring the old c05/c06 decisions, their aggregate 8/8, or the previously passing BLT replacement. A focused payment/source/replacement/retention/Investigator run passed **119 tests** in **4.31 seconds**. Presentation checks and the production web build passed. That pre-adjudication failure report is preserved. After Kyle's authorization, regression tests now require exactly the c05/c06 (and shared-fixture s2) selection-policy disagreements and require unsupported BLT replacements to remain unconfirmed. CI explicitly checks the raw 6/8 panel and failing release gate; no production case branches, checklist edits, or answer-key edits were added. The approved checkpoint passed **353 tests, 2 skipped** in **14.77 seconds**, and presentation/build checks passed. Mock run `20261022-223237-73a5c3` reproduced the same raw panel and quote counters with **$0 / 0 credits** fresh spend. Targeted paid validation is authorized; G2 has not been accepted or pushed.

Implemented work under review: complete bounded document chunks, cited-page quote checks, metric/unit/bound gates, explicit scope and selected-configuration proof, mandatory per-value web identity, model identity separate from family-wide status, original source cache timestamps with positive/negative expiry and explicit refresh, attributable primary Investigator rescue counts, replacement bundles of at most three matching documents with per-check citations and availability proof, and local durable payment reservations before each HTTP attempt. Known billing is retained even when answer parsing or persistence fails; unknown usage retains a hold and blocks further paid work.

An independent AI audit reproduced and then confirmed fixes for optional-driver evidence falsely labelled product-wide, member-only discontinuation spreading across a family, ordering examples/alternative models falsely selected, copied bundle selection proof, omitted web identity, and missing replacement availability/currency citations. Its focused final review found no additional must-fix issue in those paths; this is not fresh live validation or a construction-professional study.

The local payment database is deliberately separate from `.cache/`: the latter holds reports, not spend authority. Initialization requires explicit historical dates, refuses an existing database, and does not happen during a provider call. It was initialized locally with `python scripts/campaign_budget.py init --seed-day 2026-10-21 --seed-day 2026-10-22`. The authorized seed is October 21 **$1.048778 / 291** plus October 22 **$0.009827 / 7**; it excludes the unrelated October 8 ledger. The campaign ceiling is **$20 / 2,000**, with **$10 / 1,000** for engineering and **$8.941395 / 702** retained for final validation. [Initialization status](judge-readiness/g2/campaign-status.json) shows no new spend or outstanding reservations. This establishes no hosted or object-mount storage safety.

The conservative model holds use the approved two-model allowlist and the public catalog's context sizes, treating K as binary to over-reserve, with current input/output prices. [Nebius catalog](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference). Tavily bounds follow its documented search, extraction and mapping charges; failed extract/map responses are free, while unreported model/search billing remains unknown. [Tavily credit rules](https://docs.tavily.com/documentation/api-credits).

Fixture corrections are source corrections, not new answer-key evidence: c01 includes complete native text from its manifest-verified document; c05/c06/BLT-replacement ordering options are explicitly scoped; c08 includes the complete previously captured manufacturer response rather than an abbreviated family-only excerpt. The c08 URL is unchanged; captured text SHA-256 is `5a386246e0d84be12ea11e6172409dca07de827fd7ef4caa87af552f6aac0b6d`. Historical live recordings remain untouched.

## G2 live checkpoint — 2026-10-22

Kyle authorized live validation and the documented raw-key policy exceptions. [Full evidence, before/after changes and commands](judge-readiness/g2/live-validation.md). Final targeted run `20261022-230145-fc12db` makes **2/2 calls and catches 2/2 problems**, with no invalid items, **0/2 passing fixes**, **19/85 claims** and **43/78 web values** kept. It confirms the guarded code on cached live responses; it is not a new eight-case score or a fresh latency benchmark. One primary Investigator run recovered c03's quoted temperature change, with no cap; c07's scripted status now succeeds.

The first live contact broke product-identifier handling and family/format status matching. General corrections preserve printed identities, explicit selection, scope attribution and same-subject status. An independent audit additionally reproduced and verified closures for catalog cross-product pooling and selection rebinding. [Final pytest](judge-readiness/g2/pytest-final.txt): **382 passed, 2 skipped**; raw mock panel still **6/8, 5/6, 0/2, 0/5**. Presentation/build checks passed.

Additional local provider spend is **$0.4281318 / 60 credits**, bringing the cumulative pass to **$1.4867368 / 358**, with no unsettled reservations. Kyle replied “that is correct” to the reported cumulative $1.4867368 / 358 totals on 2026-10-22. This is owner confirmation of the reported totals; a separate dashboard readout, its timestamp and account/key scope were not supplied. The earlier three-credit gap is still unexplained, and no ledger was adjusted.

**G2 is not accepted:** no replacement has every required cited check. Current CPX proof leaves L70, warranty, MacAdam, dimming and availability unconfirmed; c03 lacks complete mold/assembly proof. G3 case/sample/blind validation and deployment remain pending. The historical recording, answer keys and reviewed checklists are unchanged.

## Reliability checkpoint — 2026-10-23

[Ownership and remaining-work audit](judge-readiness/ownership.md), [measured evidence and reproduction](judge-readiness/reliability-20261023/README.md).
The linked-PDF path now tries Tavily when direct HTTP cannot obtain the linked document, using a separate
cache age/credit path and one-hop bound. Actual c07 retry `20261023-000514-d915c4` remains correct with no
passing replacement: the CPX PDF yielded no Tavily text and direct HTTP returned a Cloudflare 403. Fresh
spend **$0 / 1 credit**; cumulative **$1.4867368 / 359**, no holds. This is an unsuccessful retrieval correction,
not a quality gain or a new full panel.

The full mock suite passes **399 tests, 2 skipped in 15.96 seconds**; raw mock remains **6/8, 5/6, 0/2, 0/5**
with zero invalid items. Eight real Chromium tests against the mock API pass; presentation/build checks pass.
The 13 required PDFs match a frozen lock and contain readable native text. Blank/scanned-without-text,
missing, damaged and changed inputs fail release preflight; Docker no longer silently substitutes excerpts.
Read-only smoke makes no scan, and invalid/replayed results cannot prove a fresh deployment.

Outstanding model/web reservations constrain the next UTC day's admission. Invalid watch results cannot
claim no change. Cloud launch now requires admin authentication and an idempotency key, retains full history,
requires secret selectors and forwards exact model/quality settings. The disabled scheduler goes through
the same controller and refuses credential-bearing redirects. These are local/fake-CLI tests only.
An independent AI review confirmed the scoped corrections; **durable hosted authority, job escrow/leases,
child limits and guarded settlement/publication remain unfinished agent work**. Current official prices are
recorded in the unapproved cost worksheet; this is not deployment authorization.

G2 remains open. No follow-up full-set run or final recording has been consumed, no gate has been
self-approved, and no cloud resource has been touched.

## Controller protocol checkpoint — 2026-10-23

[Protocol, review findings, tests and reproduction](judge-readiness/controller-20261023/README.md).
The controller now reserves a job allowance before launch, assigns one worker session, enforces a sealed
child wallet and retains a private receipt. Settlement/publication requires matching immutable inputs,
watched IDs, evidence hashes and observed cloud completion. Jobs get neither controller/archive mounts
nor admin credentials. Unknown usage and missing/corrupt receipts retain holds and block more paid work.
Cold import fences the source and binds one VM writer; retired imports and unsupported mounts fail closed.

Full offline verification: **435 passed, 2 skipped in 21.08 seconds**. Raw mock remains **6/8, 5/6, 0/2,
0/5**, zero invalid items, one unnecessary note, **48/65 claims and 8/20 web values**. Independent AI review
found and confirmed fixes for retired-source reuse, missing-receipt accounting blocks and controller URL
validation. No paid call or resource was made; cumulative actual spend remains **$1.4867368 / 359**, no holds.

Remote source-fencing/export/import, approved writer-cutover tooling, immutable deployment preparation
and hosted persistence/job proof remain agent-owned work. No actual campaign wallet was migrated or reset.
G2 stays open; broader cases/samples/blind validation, release promotion and recording remain pending.

## Release preflight checkpoint — 2026-10-23

The [separate promotion check](judge-readiness/release-preflight-20261023/README.md) now requires complete
cases, samples, six frozen owner-reviewed blind packages and the full public recording. It recomputes raw
panels, validates immutable inputs/configuration/code, replays submitted-page claim gates and web comparisons,
and checks every passing replacement and attributable primary Investigator rescue. Dated owner dispositions
bind exact artifact hashes and preserve raw disagreements. A case evidence check alone cannot claim release.

Review closed three false-promotion paths: fabricated submitted-page claims, omitted web outcomes and
replacement availability cited by unrelated text. Paired tests preserve legitimate selected base models
while rejecting a shared option code attached to a different product. Tool traces retain actual returned
source URLs and success states; results retain extraction/verification proof and candidate page provenance.
Old recordings remain viewable and cannot establish this new proof without the missing evidence.

The full mock suite passed **505 tests, 2 skipped in 27.10 seconds** outside the sandbox; sandboxed TestClient
attempts stalled and were interrupted. Presentation checks and web build passed. The raw mock panel remains
**6/8, 5/6, 0/2, 0/5**, with 48/65 claims and 8/20 web values retained, no invalid items and one unnecessary
note. Fresh spend was **$0 / 0 credits**; cumulative actual spend remains **$1.4867368 / 359**, no holds.

The actual promotion check of the incomplete artifact bundle **fails**. No blind review, release approval,
provider run, cloud action, broader evaluation or final recording was performed. G2 remains open; blind
preparation, actual release evidence, remote wallet handoff and hosted durability proof remain agent-owned.

## Replacement discovery / live quote checkpoint — 2026-10-23

[Measured runs and before/after evidence](judge-readiness/replacement-discovery-20261023/README.md) show four
general corrections: discontinued-product discovery can reach other makers; candidate verification avoids
another maker's domain constraint; existing unit aliases work symmetrically; conditional scope remains
unconfirmed. A live false replacement failure also exposed SDS/TDS dates being compared as performance.
Document revision is now excluded from performance values, requested source properties and recovery counts;
explicit revision labels retain their separate note path. Quotes, numeric bounds and selection proof stay strict.

Final targeted run `20261023-023154-e725f0`: **2/2 calls, 2/2 problems, 0/2 passing fixes**, no invalid items,
unnecessary notes, cap or provider warnings. It keeps 36/160 claims and 3/41 web values. One primary
scripted-unconfirmed item is resolved by the primary Investigator; no primary or replacement runs are capped.
The real two-item extraction/web/archive/trace consistency check passes. c03 takes 126.228 seconds and c07
86.670 seconds, partly cached; this is not a cold or full-set benchmark.

Full mock regression: **524 passed, 2 skipped in 26.91 seconds**. Raw mock remains **6/8, 5/6, 0/2, 0/5**,
48/65 claims and 8/20 web values. Earlier checkpoint 499b44f passed GitHub's Python/mock/web/browser checks.
New checkpoint spend is **$0.4834926 / 32 credits**, cumulative local ledger **$1.9702294 / 391**, no holds.
Final target fresh charges are $0.1244169 / 7; displayed usage-equivalent costs are not fresh billing.

G2 remains open: SLLT lacks complete proof; LT has a lost L70 bound, unselected options and unconfirmed
availability; c03 lacks complete VOC/mold/assembly/availability proof. A bounded corrective read is still
agent-owned. No full follow-up eval, blind eval, final recording, deployment or cloud resource was created.

## Six-package preparation checkpoint — 2026-10-23

The [new-source review table](judge-readiness/blind-20261023/README.md) has six downloaded manufacturer
PDFs with distinct hashes outside the known 13-document lock: STI SSS, TREMstop Acrylic SP, STI C-AJ-0113,
STI F-A-1118, RAB RPLED and RAB RTLED. Every page has native text; every draft source quote is on its cited
page. The implementation agent prepared the drafts before application evaluation; this is not an independent
human study. Scope and missing selections are explicit, and no label entered a pipeline input.

The existing eval runner now accepts a frozen, owner-reviewed external catalog, strips expectations before
execution and binds the exact set digest in its saved manifest. It refuses unreviewed sets, mock blind runs,
mixed suites and unsafe result identifiers. It keeps the public scoreboard unchanged. Source preflight passes;
the actual `--check` correctly refuses this draft because Kyle has not reviewed it. No self-approval was added.

Full mock regression: **532 passed, 2 skipped in 26.95 seconds**; an additional **7 tests pass in 0.31 seconds**
after adding a label-canary assertion. Final mock run `20261023-040437-584300` preserves **6/8, 5/6, 0/2, 0/5**,
zero invalid items and one unnecessary note. Fresh provider spend is $0 / 0; campaign usage remains
**$1.9702294 / 391**, with no holds. GitHub CI for preceding commit `7deb149` passed Python/mock/web/browser
checks. No new frontend changes were made. G2/G3 remain open; no blind run, broader evaluation, final recording,
deployment or cloud resource was started. Kyle's pending task is label review, not preparation or runner work.

## Private authority transfer checkpoint — 2026-10-23

[Transfer preparation and reproduction](judge-readiness/authority-transfer-20261023/README.md) now implements
destination-bound export/import, source fencing, receipt preservation, exact interrupted-transfer recovery
and explicit approved boot cutover. Retired state is read-only, and writer identity is checked again after
the SQLite lock. Tests use synthetic wallets and simulated mounts/boots; no real source was retired or
approval generated. The CLI trusts an operator-pinned owner record; the agent must authenticate the actual
stopped-host observation before preparing a real cutover. Hosted transport and durability remain unverified.

Full mock regression: **560 passed, 2 skipped in 30.79 seconds**. Mock run `20261023-042244-894557` preserves
**6/8 calls, 5/6 problems, 0/2 major false alarms and 0/5 passing replacements**, zero invalid items and one
unnecessary note. No provider calls were made. Actual cumulative ledger remains **$1.9702294 / 391**, no
holds and no retirement. CI for the preceding `c97f1f8` checkpoint passed Python/mock/web/browser checks.
The local Docker daemon reports version 29.9.2; no release image was built in this checkpoint. The concrete
startup/persistence/image/resource/cost/expiry/rollback manifest remains agent-owned preparation. G2–G5 stay
open; no full-set follow-up, blind evaluation, final recording, deployment or cloud resource was started.

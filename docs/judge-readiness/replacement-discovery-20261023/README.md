# Replacement discovery and quote gates — 2026-10-23

G2 remains open. No full-set follow-up evaluation, blind evaluation, final recording, deployment or cloud
resource was started. Original expectations, reviewed requirements and the historical recording are unchanged.

## Measured c07 runs

Every run below correctly sends c07 back for discontinued status, catches its one expected problem and has
zero passing replacements, invalid items or unnecessary notes. There are no clean items in this subset.
These are partly cached live runs, not cold latency measurements or an eight-case accuracy panel.

| Run | Change | Time | Fresh Token Factory | Fresh Tavily | Claims kept | Web values kept |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `20261023-020458-c4e76f` | Broad query with requirement names | 13.439 s | $0.0044862 | 2 | 2/17 | 0/4 |
| `20261023-020743-7d7662` | Quoted category query | 256.683 s | $0.1601058 | 16 | 20/58 | 0/40 |
| `20261023-021821-1d7ea1` | Symmetric unit aliases and conditional scope | 72.854 s | $0.0492069 | 4 | 21/58 | 4/36 |

Scores, per-run diagnoses and stage traces are saved beside this file. Result validity, warnings, diagnostics
and the actual daily/campaign ledger were checked after each run; none was cut by a provider error or cap.
Source bodies remain in `.cache/live-evidence/`, not git. The original retrieval times and source hashes are
retained in the diagnoses. Preserve that cache for the recorded local evidence checks.

## Before and after

Discontinued-product discovery previously required the original maker and its domain. Candidate verification
also reused those domains for products whose extracted manufacturer differed. Discovery now permits other
manufacturers; verification retains the original domains only for the same normalized manufacturer name.
Unknown domains are not promoted to a trusted manufacturer classification.

The first broad query appended every requirement name. Actual Tavily Basic Search returned a video, warranty
articles and a general lifetime statement. Its first three sources yielded no comparable product claims.
The [cache-only diagnosis](long-query-diagnosis.json) disabled both providers' HTTP entry points and reproduced
the drops: an unsupported warranty number and a numeric value that omitted its source's lower bound.

Before query: `current LED troffer manufacturer data sheet Rated life (L70) Warranty DLC listing macadam steps Dims down to`

After query: `"LED troffer" manufacturer specification sheet`

This returned the Starco SLLT and Williams LT sheets through normal discovery. No product, expected answer,
case identifier or source URL was inserted into the query or prompts. Current-document fixes still search
for the submitted maker/product. The candidate and credit bounds remain unchanged.

The [raw claim diagnosis](short-query-claim-gates.json) then isolated two general matcher problems:

- `unit="years"` failed against the exact source quote `5-year limited warranty, see hew.com/warranty`.
  Existing unit aliases now work in both directions; hour/year and millimetre/inch mismatches still fail.
- The Williams DLC quote explicitly says `Not all versions of this product may be DLC qualified`.
  A conditional scope cannot establish a product-wide value. It now stays unconfirmed without a selected
  configuration, instead of producing a definitive failed DLC row from incomplete qualification information.

The [HTTP-disabled replay](claim-gate-replay.json) and final live run preserve the source quotes: Williams
warranty changes from unknown to pass; conditional DLC changes from fail to unverified. The numeric value
`72000` against `L70 > 72,000 hours` remains rejected. Numeric bounds, exact quotes, model identity and
selected-configuration gates were not weakened. Changing candidate mix and repeated reads prevent assigning
the aggregate quote-drop rates to one change alone.

## What remains wrong

- Starco SLLT has quoted L70, warranty and DLC evidence, but no accepted MacAdam, minimum dimming, current
  document or availability proof. The sheet's numeric dimming minimum is not stated by the accepted claims.
- Williams LT now has accepted warranty, MacAdam and current-document checks. L70 loses its `>` in the model
  response; conditional DLC and the DIM1 driver lack a submitted selection; availability remains unconfirmed.
- Both candidates' extraction outputs omit a short model/family identifier. Their current-source reads also
  return values that the identity/quote gates do not retain. A bounded corrective read is still agent-owned;
  source absence and missing selection must remain unknown after any such correction.
- Fresh research is slow. The 256.683-second run did not hit a cap: repeated source reads and replacement
  investigation took the time. A replacement Investigator's `found` URL is not a resolved primary problem.

The [one-item consistency check](live-consistency.json) accepts the final c07 extraction, coded findings,
verification archive and trace. It grants no release promotion. c07's primary scripted status check succeeds;
its two replacement investigations end `not_found/not_resolved` and `found/not_resolved`, with no caps.

## c03 provenance and document metadata

Run `20261023-022206-1c7f2e` correctly sends c03 back for its quoted currency problem. It has one primary
scripted-unconfirmed item, one primary Investigator recovery (`problem_found`) and zero capped investigations.
The two replacement investigations find documents without resolving a replacement. The run is valid, has no
warnings, takes 211.341 seconds and adds $0.1452768 / 3 credits. It keeps 22/122 claims and 58/83 web values.
The [one-item evidence consistency check](c03-live-consistency.json) passes; this is not release promotion.

Retrieved texts associated with two forms of the 3M product-PDF URL differ. The second candidate is then given
a failed currency check because `document_revision` appears as an ordinary property: the submitted TDS date
is `January / 2026`, while a returned SDS issue date is `02/06/24`. This is a verification/comparison error,
not proof that the submitted product performance is outdated. The dates do not demonstrate a post-key world
change. The original key remains untouched.

`_unambiguous` now excludes document revision from performance values. This also removes it from the source
reader's requested property list and primary-recovery accounting. Dedicated revision metadata still follows
the existing note path; differing labels do not establish age order. The [pure comparison replay](metadata-comparison-replay.json)
removes that false failed check while preserving genuine quoted value comparisons. Two regression controls
cover absent and explicit revision metadata. The source reader's submitted claims and property enum now omit
the ordinary `document_revision` property; the dedicated revision fields remain. No expected value entered
that payload/schema change.

## Final targeted checkpoint

Run **`20261023-023154-e725f0`** follows all changes above: **2/2 correct calls, 2/2 problems caught,
0/0 clean items tested, 0/2 passing replacements**, zero invalid items or unnecessary notes. c03 takes
126.228 seconds and c07 86.670 seconds; both reuse earlier responses. Fresh Token Factory cost computed
from returned usage is **$0.1244169** and fresh Tavily usage is **7 credits**. Displayed usage-equivalent
cost includes cached model usage and must not be treated as new charges.

Quote gates keep **36/160 claims (77.5% dropped)** and **3/41 web values (92.7% dropped)**. Removing metadata
from performance reads and changed candidate/source mixtures explain why these counts cannot be compared
as a controlled quality experiment. One primary scripted-unconfirmed item is resolved by one primary
Investigator run; zero are capped. Three replacement investigations are separate and do not establish a
passing fix or extra primary rescues. Both final items have no warnings, provider errors or cap hits.

The [two-item consistency check](targeted-consistency.json) accepts both real results, quoted archives,
coded findings and traces. It is not a release promotion or a substitute for the pending full set, samples,
blind packages and recording. The final raw mock panel remains 6/8 calls, 5/6 problems, 0/2 major false
alarms and 0/5 fixes, 48/65 claims and 8/20 web values, no invalid items and one unnecessary note.
The full Python suite passes **524 tests, 2 skipped in 26.91 seconds**. No frontend change was made here.

This checkpoint adds **$0.4834926 / 32 credits** across its measured targeted runs. Cumulative local usage
is **$1.9702294 / 391 credits**, no holds, within $20 / 2,000. The actual UTC day ledger and campaign report
are saved here. No new dashboard total, timestamp or account/key scope was supplied; reconciliation remains
Kyle's private-console step. No full follow-up scoring-set eval or final recording was consumed.

## Reproduce

Python 3.12+, the existing private `.env`, downloaded native PDFs and durable campaign wallet are required.
Do not reset accounting or delete the cache. Live commands may spend on expired or changed inputs.

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/replacement-mock.json
# Expected eval exit 1: unchanged raw 6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes.
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c07 --out /tmp/replacement-c07.json
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/replacement-pair.json
.venv/bin/python scripts/campaign_budget.py status
```

These are the approved targeted overrides, not default quality measurements. Production caps remain
$3/run, $8/day, 60 Tavily credits/item, 600/day, concurrency 2 and thinking off.

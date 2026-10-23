# Product-sheet links, printed units and status merging — 2026-10-23

G2 remains open: the current two-item check makes both calls correctly but finds no complete passing
replacement. No original expectation, reviewed checklist, historical recording, cloud resource, real
authority transfer, full-set/blind evaluation or owner approval changes.

## Observed failures and general corrections

1. **Web extraction fallback chose a navigation PDF.** A real two-URL extraction diagnostic returned a
   general footcandle guide for the Elite product-page request. The shared selector now prefers explicit
   specification/product-data sheet paths among validated public links, while still rejecting company
   catalogs. Opaque document IDs retain page order. The same batch now returns the actual product sheet
   and its product identifier. Only that batch was refreshed; no cache directory was deleted.
   [Actual before](elite-extract-observation.json), [actual after](elite-extract-after.json),
   [same-HTML selector replay](before-after.json). The diagnostic paid 0 then 1 credit; no model call.
2. **Physical claims omitted their units.** A fresh higher-cap c07 extraction returned eight claims; physical
   quantities used null units and other claims had metric/value errors. Existing gates correctly dropped
   all eight. The prompt and schema description now explicitly ask for the unit printed in the supporting
   quote. No code infers a unit or relaxes a gate. [Exact instructions before/after](prompt-before-after.json),
   [valid miss and diagnosis](higher-cap-before-prompt/diagnosis.json).
3. **An unsupported status erased a supported notice during merging.** Actual source reads included a
   quoted TL discontinuation and two active assertions with no quote. Merging before validation produced
   unknown. Each status now passes the existing identity/quote gate before merging. Supported conflicts
   remain unknown and their status metadata is cleared. Value reads remain available for the existing
   correction and final gate; counters are measured once. Replaying the same five archived reads changes
   unknown to discontinued; [actual replay](status-before-after.json). This is not a new case score.

Ten new regressions cover link selection/public-address checks/direct retrieval, unsupported status in
either order, genuine conflicts and unchanged value counters. Five provider regressions first produced
four failures; five merger regressions first failed. Final full suite: **657 passed / 2 skipped in 31.96 s**;
[output](pytest-final.txt). Raw [mock run](mock-score.json) stays **6/8 calls, 5/6 problems, 0/2 major false
alarms, 0/5 fixes**, zero invalid items, 46/65 claims and 8/20 web values. Expected mock exit 1 preserves the
disclosed selection-policy disagreements. No frontend code changed. Both [source CI workflows](ci.json)
pass Python/mock, presentation/build and mock browser checks; this is not live/hosted browser evidence.

[Runtime/test patch](source.patch) reconstructs committed `e1a4c2e` runtime hash
`3480e5d073f7a58d7fae7317cac2c0a83a3dc880b45e3709e2bec7e9f07f0b45`
from clean `f95d6cf`; [actual reconstruction](source-reproduction.json). The earlier local unit-runtime
image predates these changes. Final image publication/hosted validation remains gated.

## Actual experiments, including the invalid item

| Experiment | Calls / problems | Passing fixes | Invalid items | Fresh USD / credits |
| --- | --- | --- | ---: | ---: |
| c07, 32,768 output cap, concurrency 2 | Correct call, excluded from acceptance | 0/1 | 1 | 0.0318993 / 1 |
| c07, 65,536 cap, concurrency 1, before unit prompt | 0/1 / 0/1 | 0/1 | 0 | 0.02971812 / 13 |
| c03/c07, clarified units, before status merge | 2/2 / 2/2 | 0/2 | 0 | 0.2739588 / 16 |
| Final committed code, same 65,536/1 profile | **2/2 / 2/2** | **0/2** | **0** | **0.0792648 / 2** |

The first item was cut off in **fix**, recorded as `output_limit`; the failed response body and reasoning
count were not retained, so neither is inferred. Its warning, failed charge and trace are preserved in
[invalid-output](invalid-output/diagnosis.json). A larger-cap retry completed but exposed a valid miss;
it is not claimed that the changed cap alone improved accuracy. Fresh [response metadata](higher-cap-before-prompt/response-metadata.json)
contains no request messages, credentials or response bodies. The [unit-prompt pass](unit-prompt-before-status/score.json)
took 241.700 / 359.077 seconds. It started before the merger edit and has its own saved runtime patch/hash.

Final run **`20261023-095053-630ac4`**:

| Item | Call / caught problem | Passing fix | Item time | Fresh model USD | Fresh credits |
| --- | --- | --- | ---: | ---: | ---: |
| c03 | Send back / currency | 0/1 | 65.928 s | 0.0416814 | 0 |
| c07 | Send back / discontinued | 0/1 | 57.384 s | 0.0375834 | 2 |

[Score](score.json), [trace](events.jsonl), [candidate/check diagnosis](diagnosis.json),
[fresh response metadata](retry-response-metadata.json). Both items have zero warnings/diagnostics.
The [submitted-page/web/archive/trace consistency check](consistency.json) passes for these two items;
no complete release promotion is claimed. Claims retained **131/340** (61.5% dropped); web values
**29/104** (72.1% dropped). These totals include replacement research and are not isolated extraction
accuracy. Times include cached and fresh work, not controlled cold-upload performance.

No primary scripted-unconfirmed item or primary investigation occurs in the final check. Four replacement
investigations: three found, one not found; two confirm values, none yields a complete replacement, none
is capped. The old primary rescue stays historical. c03 lacks accepted mold/assembly/availability proof,
and one candidate lacks standards proof. SLLT lacks MacAdam/minimum dimming/availability; LT lacks a
selected DLC/driver configuration and availability. Missing proof remains unconfirmed, never a failure.

The [new native Elite sheet observations](native-document-observation.json) are a research lead only.
Its product page returned 403 to plain HTTP; indexed stock snippets are not fetched-page proof in this
run. A retrofit kit also needs compatible existing housing and a genuine configuration selection.
No proposal, automatic selection, cache injection or passing replacement is inferred.

## Accounting and reproduction

All six experiment/diagnostic runs add **$0.41484102 / 33 credits**. Exact settled request groups and
the timing limitation on intermediate ledger inspection are in [spend-audit.json](spend-audit.json).
Actual cumulative local accounting is **$3.36648982 / 490**, engineering **$2.30788482 / 192**,
with no holds or persistent block; [current ledger](campaign-after.json). No seed or cap was reset.
The 09:56 UTC read-only Tavily usage API reports **452** for key/account, 38 below local accounting;
[redacted observation](tavily-usage.json). The earlier owner dashboard $2.13 / 421 predates this work.
No synchronized dashboard/invoice match, lag explanation or ledger adjustment is claimed.

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/document-links-mock.json
# Expected mock exit 1 for the unchanged raw-key disagreements.
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=65536 MAX_CONCURRENCY=1 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python docs/judge-readiness/document-links-20261023/capture_live.py
.venv/bin/python scripts/campaign_budget.py status
```

[Capture script](capture_live.py) invokes the normal two-item evaluation and saves fresh response metadata.
Live reproduction can spend on cache misses; inspect the UTC budget mirror after each run. Permanent
environment defaults are unchanged; the larger output cap/concurrency override is explicitly measured.
The two authorized follow-up full-set evals and final recording remain unused and gated. Kyle's pending
selection policy, blind-label review, gate acceptance, private rollout facts and release approval remain open.

The [subsequent local packaging proof](image/README.md) freezes this validated source at `061cf9d` in an
isolated image and repeats native-document, unit, mock, privacy and synthetic capped replay/restart checks.
It remains unpublished and excludes newer shared status-timing work; it is not final release approval.

# Technical-sheet revision attribution — 2026-10-23

G2 remains open: **no complete passing replacement**. Original answer keys, reviewed requirements,
selection policy and claim/value quote gates remain unchanged.

## Observed error and general correction

The saved c03 replacement verification used a safety sheet's version/issue date as the technical sheet's
current revision. Its pass title also implied a match of the entire document, although only selected
values had been compared. The root stages are **verify/read** and **report**; the preceding run has no
provider/cap invalidity that explains this metadata error.

The shared web revision check now excludes clearly identified safety sheets from technical/listed-system
revision evidence, using the safety-sheet title plus its identification section. A technical sheet merely
referring to an SDS remains valid. Property quotes from a safety sheet still pass their existing metric,
unit, value, identity and scope gates. This narrow classifier is not a general document-role parser.
The source-reader prompt explicitly distinguishes these document types and leaves unresolved technical
revision conflicts null. Neither change supplies an expected case value or a selected configuration.

| Same archived candidate output | Before | After deterministic gate |
| --- | --- | --- |
| Safety-sheet revision | Accepted as technical-sheet revision | Unconfirmed |
| Accepted property values / comparison rows | 6 / 4 | 6 / 4 |
| Pass title | Entire data sheet matches current version | Compared values match current sources |

[Actual archive-only replay](before-after.json), [prompt before/after](prompt-before-after.json),
[runtime patch](source.patch) and [clean-parent reconstruction](source-reproduction.json).
No historical result is promoted or rewritten by that replay. Revision-only comparisons also distinguish
a matching submitted revision from a source revision found for an undated submission. Missing revisions
use `unknown` in changed-value details rather than the Python value `None`.

## Verification and provider observations

Six new regressions preserve actual technical revisions and SDS property quotes, reject borrowed safety
revisions, and keep changed values actionable. Full suite: **632 passed, 2 skipped in 31.66 s**,
[output](pytest.txt). Mock run `20261023-081124-10b0ab` preserves **6/8 calls, 5/6 problems, 0/2 major
false alarms, 0/5 passing fixes**, zero invalid items, one unnecessary note, 48/65 claims and 8/20 web
values. Its expected exit 1 keeps the approved raw-key disagreements visible. [Score](mock-score.json).

The intermediate gate-only run `20261023-080630-57ce9d` makes 2/2 correct calls/problems and has no
passing fix or invalid item. It adds **$0.000606 / 1 credit**; [preserved intermediate evidence](gate-only/score.json).

Final prompt-and-gate run **`20261023-081257-c725cf`**:

| Item | Correct call / problem caught | Passing fix | Time | Fresh model USD | Fresh credits |
| --- | --- | --- | ---: | ---: | ---: |
| c03 | 1/1, currency send-back | 0/1 | 174.509 s | 0.0862098 | 0 |
| c07 | 1/1, discontinued send-back | 0/1 | 137.884 s | 0.0802881 | 4 |

Fresh total **$0.1664979 / 4 credits**; scoreboard totals round to six decimal places. These timings
include fresh and cached work, not a controlled cold-upload benchmark. No clean item is requested.
Claims retained **56/209** (73.2% dropped), web values **61/124** (50.8% dropped).
There are zero typed invalid items, provider/cap warnings or observed 429s.
[Score](score.json), [stage/candidate diagnosis](diagnosis.json), [trace](events.jsonl).
The actual two-item claim/source/archive/trace check [passes](consistency.json); it is not full promotion.

The diagnostic captures **61** structured source reads, **51 fresh** and 10 cached. Even with the new
instruction, two raw outputs emit the safety date `02/06/24` (one fresh, one cached). The deterministic
gate rejects it as technical-sheet revision evidence. The final first c03 candidate has no confirmed
revision; its second candidate retains the actual technical-sheet label `January / 2026`.
[Redacted instructions, message hashes, raw revision responses and usage](source-read-responses.json).
The capture omits source bodies and credentials. These per-call outputs are not a new aggregate accuracy score.

No primary scripted-unconfirmed item or primary Investigator run occurs. Four replacement investigations
return `found`, none capped: c03 has two `not_resolved`; c07 has two `values_confirmed`. Confirming values
does not close the missing requirements or availability. SLLT still lacks MacAdam/minimum dimming/
availability; LT lacks selected DLC/driver proof and availability; c03 lacks complete mold/assembly/
availability evidence, and one read also lacks VOC. **No candidate is suggested.**

## Accounting and reproduction

This checkpoint adds **$0.1671039 / 5 credits** across its two live runs. Actual cumulative local
accounting is **$2.8022062 / 447**, UTC day **$1.3154694 / 89**, engineering since the first pass
**$1.7436012 / 149**, no holds or persistent block. [Campaign](campaign-status.json), [day mirror](daily-ledger.json).
The earlier owner/API billing observations predate this usage; reconciliation remains unresolved and no
ledger or seed is adjusted. No full-set follow-up, blind evaluation, final recording or cloud resource occurs.

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/document-revision-final-mock.json
# Expected mock exit 1: preserve the raw panel.
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python docs/judge-readiness/document-revisions-20261023/capture_read.py
.venv/bin/python scripts/campaign_budget.py status
```

[Capture script](capture_read.py) calls the ordinary targeted eval and retains only instruction/response
metadata. Reproduction may spend on cache misses; preserve the existing authority and caches.
No owner approval, answer-key adjudication or release acceptance is inferred.

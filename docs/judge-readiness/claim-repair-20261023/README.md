# Bounded claim repair and source attribution — 2026-10-23

G2 remains open: **no fully evidenced passing replacement**. This checkpoint changes no original answer
key, reviewed requirement, historical recording or quality limit. No broader evaluation, blind evaluation,
final recording, deployment or cloud resource was started. The local image built from `b9de109` predates
these source changes and is not the current release image.

## Actual runs

Every listed item makes the correct send-back call and catches its expected problem. Every run has zero
passing replacements, typed invalid items, unnecessary notes, provider/cap warnings and capped investigations.
The pre-citation run nevertheless fails evidence consistency; its saved flag is not proof of release quality.
No clean item is tested. These are partly cached live observations, not a cold latency benchmark.

| Run | Change | c03 / c07 seconds | Fresh Token Factory | Fresh Tavily |
| --- | --- | ---: | ---: | ---: |
| `20261023-050455-d06920` | First bounded value repair / required nullable model | — / 268.451 | $0.1203567 | 12 |
| `20261023-052918-e9faa8` | Exact punctuation, Unicode escape, selection/scope prompt, bundle retention | 112.279 / 368.193 | $0.2056944 | 8 |
| `20261023-054428-d1e291` | Coded-driver quarantine and ordering-example boundary | — / 85.387 | $0.0475416 | 1 |
| `20261023-054816-7e4a00` | Empty-chunk model merge and shorter-scope schema instruction | 77.832 / 163.553 | $0.1254984 | 7 |
| **`20261023-055339-e48fd0`** | **Accepted value keeps its own URL and quote** | **131.411 / 0.945** | **$0.0562113** | **0** |

The final panel is **2/2 calls, 2/2 problems, 0/0 clean items tested, 0/2 passing fixes**.
Quote gates keep **58/209 claims (72.2% dropped)** and **51/100 web values (49.0% dropped)**, including
replacement reads. The final run has no primary scripted-unconfirmed items or primary Investigator runs;
two replacement investigations find documents but end `not_resolved` and `revision_only`, with no caps.
This is not a new Investigator rescue demonstration or an eight-case result.

[Final scoreboard](final-score.json), [diagnosis](final-diagnosis.json), [trace](final-events.jsonl) and
[passing two-item evidence check](final-consistency.json) bind the code, configuration, archives and findings.
That consistency check grants no release promotion. The final c07 time is a warm-cache observation;
displayed usage-equivalent model costs include cached work and are not fresh billing.

## Before and after, including unsuccessful changes

1. **Missing identifier:** the extraction wire schema now requires a nullable short `model` field. It does
   not require a non-null answer or select a configuration. Real responses name SLLT/LT. An empty driver
   supplement previously cleared LT through a conflicting metadata value; chunks with no accepted claims
   no longer clear a model supported by accepted claims. Model identities still need printed page evidence.
   Removing only an example clause also preserves a genuine product heading printed later on that page.

2. **Lost numeric qualifier:** the real Williams quote is `L70 > 72,000 hours per IES TM-21.`. Bare `72000`
   still fails the value gate. One live-only corrective read per batch may change only that numeric value's
   qualifier, with the same ID, property, normalized quote and numeric magnitude. Earlier wording returned
   no correction; explicit bound-string instructions returned `> 72000`, 2,054 ms, reasoning 0.
   [Actual redacted logical request, response and usage](paired-read-profile.json). No requirement threshold,
   expected answer, product name or case-specific branch is added to the prompt. Corrections cannot change
   identity, page, units, scope or selection and cannot recurse. A failed correction remains dropped; a
   provider/cap error propagates to typed invalidity. **The repaired L70 remains unconfirmed because of scope.**

3. **Degree symbol and quote punctuation:** a real SLLT response contains a literal Unicode escape where
   the source prints `°`. Both sides now decode that escape before the existing typography/whitespace
   normalization; numbers and units still match exactly. [Original quote/page/hash and replay](unicode-replay.json).
   Prompts carry native Unicode and request exact contiguous punctuation. This retains quoted L70 without
   inventing a value; numeric/unit mismatch controls still reject altered claims.

4. **Bundle omission:** a subsequent SLLT bundle read omitted a previously validated L70. Matching bundles
   now retain original validated claims, add supplemental claims, deduplicate equivalent values and preserve
   conflicts as unconfirmed. Primary page labels stay stable; supplementary labels are unique. Identity,
   selection, page grounding and per-check citation gates remain. Four synthetic bundle regressions cover
   omission, duplicate, conflict and foreign-product responses.

5. **Table volume and driver attribution:** selection instructions changed the native c07 response from
   87 rows / 83 variants / 58,263 ms to 20 rows / one variant / 11,384 ms in the paired follow-up.
   These are actual individual responses, not a controlled speed comparison. The real Williams response
   still mislabels `DIM1 1 % Driver with external 0-10V dimming wires` as product-wide. Coded percentage-driver
   rows now retain their option code and require actual submitted selection. Its false partial dimming pass
   becomes unconfirmed. Synthetic controls retain a genuinely selected matching driver. This conservative
   rule can leave driver evidence unknown; it supplies no missing selection.

6. **Scope instruction did not solve the drop:** both prompt text and a schema description request the
   shortest complete applicability clause with every condition on that metric, excluding neighboring metrics.
   The real Williams response still copies a paragraph containing another metric's `HE option` condition
   into L70/MacAdam scope. Code continues to quarantine those claims. The schema instruction is **not a
   demonstrated scope-quality improvement**. Source absence, scope rejection and missing selection remain
   distinct root causes in the saved diagnosis.

7. **Agreeing-page citation bug:** two 3M pages report the same temperature with differently punctuated
   quotes. `_unambiguous` keeps the first accepted value, but the old comparison attached the last source URL
   for that property. The [pre-fix evidence check fails](scope-consistency.json). Comparison now takes that
   accepted value's own URL. [Archive-only before/after](citation-replay.json) and the final live consistency
   check preserve exact quote/source pairing. Both changed and unchanged agreeing values have regressions.

The [initial before/after functions](prompt-and-matcher-before-after.json) and [final exact functions](final-functions.json)
show the prompt/matcher changes. Intermediate API patches (`baseline.patch`, `paired-run.patch`,
`driver-guard-code.patch`, `scope-code.patch`) apply to clean parent `a3fd6fe`; `final-code.patch` captures
the final API changes from that same parent. [Six archived patches applied in temporary clean source trees](patch-reproduction.json)
each reproduce their actual run's code hash exactly. Tests/docs are separate from the measured runtime code hash.

## Remaining causes, by stage

| Item / candidate | Stage | Still unconfirmed |
| --- | --- | --- |
| c03, current 3M sheets | Extract / spec / verify | One candidate retains VOC; another loses it. Neither has complete quoted G21/T-rating/availability proof. Standards and quoted current-value comparisons are retained. No assembly or availability is inferred. |
| c07, Starco SLLT | Spec / verify | L70, warranty and DLC pass; MacAdam, dimming minimum and availability remain unconfirmed. Finding a PDF or no discontinuation notice does not prove availability. |
| c07, Williams LT | Extract / spec / verify | LT identifier and numeric bound are retained. L70/MacAdam still have an unrelated optional scope clause; conditional DLC and coded dimming drivers lack a selected configuration. Current revision differs and availability is unconfirmed. |
| Both | Report | “Not stated” can describe an unconfirmed row even when a rejected source claim exists. The UI must not imply that absence was proved. |

The final run's stage traces, result warnings/diagnostics and actual ledger were inspected before interpreting
these as model/source misses. No 429, output limit or provider/cap cut-off was observed in these runs.
An intermediate status read showed an active reservation as blocked admission; the wallet's persistent
block flag was false, the original process remained live, and its known usage settled normally. No restart,
wallet reset or fabricated settlement was used.

## Verification and spending

[Full suite](pytest-final.txt): **591 passed, 2 skipped in 31.04 seconds**. [Final mock](mock-final-score.json),
run `20261023-055258-496b37`: unchanged **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**,
zero invalid items, one unnecessary note, 48/65 claims and 8/20 web values. Expected eval exit 1 preserves
Kyle's accepted unselected-configuration policy disagreements against the unchanged key. Fresh mock spend
is $0 / 0. No frontend code changed; earlier presentation/build/browser checks are historical.
The publication files and all 13 files in the historical recording pass a configured-secret byte scan;
[per-file booleans](secret-scan.json). `.env`, private wallets, caches and native PDFs remain outside Git.

This checkpoint adds **$0.5553024 / 28 credits**. The actual cumulative local campaign ledger is
**$2.5255318 / 419**, no holds or persistent block. Engineering allocation usage is **$1.4669268 / 121**;
the UTC day report is **$1.038795 / 61**. [Campaign](campaign-status.json), [day report](daily-ledger.json).
All are within the existing campaign and allocation ceilings. No new private-dashboard reading covers this
usage; the historical three-credit discrepancy remains unexplained. No invoice/ledger was adjusted.

## Reproduce

Use Python 3.12+, the private `.env`, native PDFs, retained source archives/cache and existing campaign
wallet. Never reset the wallet or delete the cache. Changed/expired inputs can incur fresh charges.

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/claim-repair-mock.json
# Expected mock exit 1: the raw key disagreements remain disclosed.
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/claim-repair-pair.json
.venv/bin/python scripts/campaign_budget.py status
```

These are approved targeted overrides, not default-profile measurements. Production caps remain
$3/run, $8/day, 60 credits/item, 600/day, concurrency 2 and thinking off. Both follow-up full-set evals and
the final recording remain unused. G2 is not self-approved; startup/persistent-state preparation, final
validation and hosted/demo/release proof remain agent-owned work after their required gates.

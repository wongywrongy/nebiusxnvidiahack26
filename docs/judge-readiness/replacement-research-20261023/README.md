# Replacement research checkpoint — 2026-10-23

G2 remains open: **no complete passing replacement**. This is a targeted c03/c07 measurement,
not a full evaluation, blind-set result, new recording or release promotion. Original keys and reviewed
requirements remain unchanged.

## General cause and correction

The preceding trace could stop replacement research once it had a quoted revision and comparable values,
even when a required property or availability remained unconfirmed. The replacement verifier now passes
applicable requirement names (including reference properties), the actual candidate URL and an explicit
availability requirement. These are checklist inputs, not answer-key labels or expected product values.

The Investigator receives those gaps and an instruction to seek exact availability evidence. A live page,
ordering example, optional driver or absence of a discontinuation notice cannot establish availability or
selection. The final bounded read prioritizes the discovered document and the page containing its actual
status quote, then other discovered evidence, rather than backfilling only the old scripted pages.

| Behavior | Before | After |
| --- | --- | --- |
| Quoted revision, but a required property is absent | Could skip research | Searches for the missing property |
| Quoted revision/values, but availability is unknown | Could skip research | Requires an availability lookup |
| Newly discovered status/supplementary source | Could be omitted from the final read | Retained within the same three-page bound |
| No selected driver or exact availability statement | Unconfirmed | Unconfirmed |

[Runtime patch](source.patch), [actual clean-parent reconstruction](source-reproduction.json), and
[exact prompt additions](before-after.json). Six synthetic regressions cover trigger combinations,
source priority and the native tool request; replacement integration also checks the forwarded context.

## Measured results

Full suite: **621 passed, 2 skipped in 31.67 s**, [output](pytest.txt). The saved mock scoreboard preserves
the authorized raw-key disagreements: **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**,
zero invalid items, one unnecessary note, 48/65 claims and 8/20 web values. Its nonzero eval exit remains
expected; the strict release gate does not pass. No frontend code changed.

Live run **`20261023-071700-8a9e33`**:

| Item | Correct call / problem caught | Passing replacement | Time | Fresh model USD | Fresh credits |
| --- | --- | --- | ---: | ---: | ---: |
| c03 | 1/1, currency send-back | 0/1 | 54.947 s | 0.0238437 | 4 |
| c07 | 1/1, discontinued send-back | 0/1 | 81.188 s | 0.0432930 | 8 |

Fresh total **$0.0671367 / 12 credits**; the scoreboard rounds model totals to six decimal places.
Times include cached and fresh work and are not a cold-provider latency benchmark. No clean item was
requested, so the false-alarm denominator is zero. Quote gates keep **56/209 claims** (73.2% dropped)
and **54/110 web values** (50.9% dropped). Drops include scope, identity, duplicates and bound checks;
they cannot all be counted as model errors.

Both items have no typed invalidity, warnings, provider/cap failures or observed 429s. There are zero
primary scripted-unconfirmed items and no primary Investigator runs or rescues. Four replacement
investigations run, none capped: c03 returns `found/revision_only` and `found/not_resolved`; c07 returns
`not_found/not_resolved` and `found/values_confirmed`. Finding values does not prove a complete replacement.
[Score](score.json), [stage/candidate diagnosis](diagnosis.json), [trace](events.jsonl).
The actual submitted-page/web/archive consistency check [passes](consistency.json) for these two items
only; it is not release promotion.

| Candidate evidence | Confirmed | Still unconfirmed |
| --- | --- | --- |
| 3M IC 15WB+, first document | VOC, standards, current-source comparison | Mold, assembly T/F proof, availability |
| 3M IC 15WB+, second document | Standards, current-source comparison | VOC, mold, assembly T/F proof, availability |
| Starco SLLT | L70, warranty, DLC, current-source comparison | MacAdam, minimum dimming, availability |
| Williams LT | L70, warranty, MacAdam, current-source comparison | Selected DLC/driver configuration, availability |

The tool output still proposes active status from a current page or no discontinuation notice. Those
unsupported statements are rejected by code. No candidate is suggested. Retrieval did not supply the
missing evidence, so no improvement to the replacement success count is claimed.

## Accounting and reproduction

Actual local cumulative ledger: **$2.6351023 / 438 credits**, no outstanding holds or persistent block.
UTC day: **$1.1483655 / 80**; engineering since the first-pass baseline: **$1.5764973 / 140**.
[Campaign authority report](campaign-status.json), [daily mirror](daily-ledger.json).
The earlier owner account-wide $2.13 / 421 and separate Tavily API 415 readings predate this run;
no new synchronized dashboard read covers these charges. Billing remains unresolved, the higher local
accounting stays authoritative for caps, and no ledger or invoice is adjusted.

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/replacement-research-mock.json
# Expected mock exit 1; preserve the raw panel.
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/replacement-research-live.json
.venv/bin/python scripts/campaign_budget.py status
```

Applying `source.patch` to clean `53eb99a` reproduces runtime hash
`c3c5ed3a0263d3b606584abc6d81410a4866a21596efeb9222907cc54adc463f`.
The preceding commit's two GitHub workflows passed; this is not a current-head CI claim.
The previous local container image predates this change. No broader follow-up evaluation, final recording,
cloud action, wallet transfer or owner approval occurred. Better replacement evidence remains agent-owned.

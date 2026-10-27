# Scoped metric binding and billing checkpoint — 2026-10-23

This is a targeted live checkpoint, not an eight-case evaluation or release promotion. G2 remains open:
**neither replacement has complete evidence**. No original expectation or reviewed checklist changed.

## General correction and before/after

The preceding Super response quoted Williams LT's unconditional L70 and MacAdam statements together
with a separate optional L80 sentence. The scope gate rejected all of them. The shared matcher now binds
that narrow, explicit lifetime-option sentence to its own metric. It still rejects an option applying to
the checked metric, an ambiguous/shared limitation, a spanning value quote and coded driver options.
Extraction, web verification and the release replay use the same function. No prompt changed.

| Actual archived statement | Before | After |
| --- | --- | --- |
| `L70 > 72,000 hours per IES TM-21.` beside the separate optional L80 sentence | Unconfirmed | Accepted |
| `All CCTs are within 3 MacAdam ellipses.` in that passage | Unconfirmed | Accepted |
| `DIM1 1 % Driver with external 0-10V dimming wires` without a selected driver | Unconfirmed | Unconfirmed |
| DLC statement followed by `Not all versions ... may be DLC qualified` | Unconfirmed | Unconfirmed |

[Exact quotes, source URLs/hashes and page checks](source-replay.json), [old/new matcher](before-after.json)
and [runtime patch](source.patch) preserve the comparison. The replay changes only the scope decision;
it does not upgrade a historical result. Applying the patch to clean `81d05ea` actually reconstructs the
live runtime hash `fb8286db4c960c17e5cb6d1613d4a62e05e92eb652c01f3c5edeeafe30fa1337`;
[reconstruction](source-reproduction.json). The previous local container image predates this change.

## Measured verification

- Full Python suite: **615 passed, 2 skipped in 31.20 s**, [output](pytest.txt). Thirteen new synthetic tests
  cover independent and shared conditions, extraction, spec checking, web verification and release claims.
- Mock run `20261023-064615-c6215c`: unchanged **6/8 calls, 5/6 problems, 0/2 major false alarms,
  0/5 passing fixes**, zero invalid items, one unnecessary note, 48/65 claims and 8/20 web values.
  [Raw scoreboard](mock-score.json); expected exit 1 preserves the approved selection-policy disagreements.
- No frontend code changed. Presentation/build/browser results belong to their preceding checkpoints.
- Both GitHub workflows for preceding source `81d05ea` succeeded; [observed jobs](preceding-ci.json).
  That is not a current-source CI claim.

Live run **`20261023-064841-187b83`**, authorized targeted profile:

| Item | Right call / problem caught | Passing fix | Time | Fresh model USD | Fresh Tavily credits |
| --- | --- | --- | ---: | ---: | ---: |
| c03 | 1/1, currency send-back | 0/1 | 4.216 s | 0.0005931 | 0 |
| c07 | 1/1, discontinued send-back | 0/1 | 72.542 s | 0.0418407 | 7 |

Fresh total **$0.0424338 / 7 credits**. These are partly cached end-to-end times, not cold/provider-only
benchmarks. No clean item was requested, so the false-alarm denominator is zero. Claims retained
**58/209**, drop **72.2%**; web values retained **57/108**, drop **47.2%**. Gate drops include options,
duplicates, identity, numeric and quote checks; they are not all model errors.

There are **zero typed invalid items, warnings, provider/cap failures or observed 429s**. The scripted
primary check leaves zero items unconfirmed; no primary Investigator runs or rescues occur. Two replacement
investigations return `found` with resolutions `not_resolved` and `values_confirmed`, neither capped.
The latter resolution does not supply missing requirements, selected options or availability.
[Score](score.json), [per-stage result diagnosis](diagnosis.json), [trace](events.jsonl).
The submitted-page/web/archive consistency check passes for these two items only;
[result](consistency.json), not full release promotion.

LT now passes L70, warranty and MacAdam but lacks accepted DLC/driver selection and availability.
SLLT lacks MacAdam, dimming and availability. c03 lacks complete mold/assembly/availability proof;
one separate read also lacks accepted VOC evidence. Unknowns stay unconfirmed. Better evidence retrieval
remains agent-owned. No broader follow-up evaluation or final recording has been consumed.

## Billing: preserve the disagreement

Actual local campaign **$2.5679656 / 426 credits**, no holds or persistent block; UTC-day
**$1.0812288 / 68**. Engineering since the original pass adds **$1.5093606 / 128**.
[Campaign](campaign-status.json), [day ledger](daily-ledger.json).

Kyle supplied **$2.13 / 421 credits**, then explicitly confirmed **account-wide** scope. The first reading
was received at **07:04:28 UTC**; the dashboard's own as-of time and inclusion of today's usage were not
specified. Local minus owner is **$0.4379656 / 5 credits**. [Redacted observation](owner-billing.json).

At **07:10:32 UTC**, a read-only authenticated Tavily `GET /usage` returned HTTP 200 with **415** for both
key and account usage: search 363, extract 48, map 4, other categories zero. This is a separate observation,
**not a reconciled match** to either dashboard or ledger. [Redacted request/response](tavily-usage.json);
[official usage reference](https://docs.tavily.com/documentation/api-reference/endpoint/usage).
No Search/Extract/Map request was made for this audit.

The current public Token Factory catalog agrees with configured ordinary prices (Nano $0.06/$0.24,
Super $0.30/$0.90 per million input/output tokens) and lists **$0.06 per million cached Super input tokens**.
The local ledger charges full input price and the saved usage does not preserve provider cached-token
quantities. This is a possible source of conservative overestimation, not proof of the historical dollar
difference. [Actual public response subset/hash](tokenfactory-public-prices.json),
[official catalog](https://tokenfactory.nebius.com/api/public/models_info).

A read-only SQLite audit checks all **776 settled request records**, zero unsettled records and exact
seed-plus-settlement conservation. [Audit and per-run sums](billing-local-audit.json). It does not prove
invoice correctness or rule out duplicated real HTTP requests. Historical estimates remain disclosed.
**No ledger, seed, invoice or cap was adjusted; the higher local totals continue to enforce spending.**
Historical cached-token discounts cannot be reconstructed from missing data. Billing remains unresolved.

## Reproduction

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/scope-binding-mock.json
# Expected mock exit 1; preserve the raw panel.
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/scope-binding-live.json
.venv/bin/python scripts/campaign_budget.py status
```

For the billing audit, read the campaign SQLite with `mode=ro`, sum `seed + payments.actual`, and compare
with `campaign_budget.py status`. With the existing private key, call the documented `GET /usage` once,
retain only usage fields and redact authorization. Fetch the public catalog without credentials and filter
to the two configured model IDs. Never print keys, request headers or `.env`.

No deployment, cloud resources, real wallet transfer, new image publication or owner gate approval occurred.

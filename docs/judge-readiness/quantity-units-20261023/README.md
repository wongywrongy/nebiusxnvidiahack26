# Missing quantity units — 2026-10-23

An offline synthetic response exposed a false approval. A forged `dim_min_percent=0`, `unit=null`
quoted only “Dimming control interface: 0-12 V.” The old extraction/web gates accepted it and spec
comparison borrowed `%` from the requirement. This was a synthetic trust-boundary test, not an observed
live-model mistake or a blind-set evaluation.

The shared unit gate now requires a unit for known physical quantities, including lifetime properties.
Extraction (including repair eligibility), web reads and both release-validation paths pass the property
to that gate. Dimensionless/categorical properties still allow no unit; explicitly stated convertible
units retain their existing conversion. The dimming metric gate also requires percentage and dimming
context. An unsupported value becomes unconfirmed, never a failure.

| Same synthetic response | Committed baseline `2ac6f89` | Corrected runtime |
| --- | --- | --- |
| Extracted claims retained | 1 | 0 |
| Spec verdict | pass | unverified |
| Web values retained | 1 | 0 |
| Release claim gate accepted | true | false |

[Actual baseline](before.json), [actual correction](after.json), [runtime/test patch](source.patch),
[checked integration preimages](integration.json). No prompt, answer key, reviewed checklist, provider
request, paid cache or wallet was changed by this correction. The code hashes in the two responses bind
the exact measured sources; no historical result is rewritten or promoted.

Fifteen new regressions cover missing/mismatched quantity units across the trust boundaries,
dimensionless values, explicit unit conversion and dimming context. Two existing synthetic response
helpers now supply their quoted units. Integrated full suite: **647 passed, 2 skipped in 32.66 s**;
[output](pytest.txt). Web files were not changed. Both [GitHub workflows for tested source `95d5a27`](ci.json)
pass Python/mock, presentation/build and mock browser journey/failure checks.

Raw mock run `20261023-084645-ea75cd` is identified authoritatively by [its scoreboard](mock-score.json):
**6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**, zero invalid items and one
unnecessary note. Its expected exit 1 preserves the existing c05/c06 selection-policy disagreements.
Claims retained are **46/65**, versus 48/65 at the preceding checkpoint; the c06 driver fragment
“EZ1 eldoLED 1% 0-10V” lacks literal dimming context and is now dropped on both extraction passes.
Its already-unselected option still cannot establish the submitted configuration. Web retention stays
**8/20** and no case decision changes. [Console output](mock-eval.txt).

This offline correction costs **$0 / 0 credits**. Actual cumulative local accounting remains
**$2.8022062 / 447**, UTC-day **$1.3154694 / 89**, with no holds or persistent block.
[Campaign](campaign-status.json), [day report](daily-ledger.json). The account-wide dashboard observation
predates this checkpoint and is not a synchronized reconciliation.

```bash
# In this checkout; no live requests are made by the synthetic reproducer.
SPECCHECK_MODE=mock .venv/bin/python docs/judge-readiness/quantity-units-20261023/reproduce.py
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/quantity-units-mock.json
# Expected mock exit 1, for the unchanged raw answer-key disagreements.
```

To reproduce the baseline, extract `git archive 2ac6f89` into a new temporary directory and run the same
reproducer there with the existing venv's absolute Python path and `SPECCHECK_MODE=mock`. It imports the
current working directory deliberately. Do not replace the real checkout or remove its cache.

## Actual affected-case live validation

Run **`20261023-084824-7ab49b`** uses committed `a9df48c` and runtime hash
`00e67a6b689a02864de9286e2f4b7d39fbb31b845fee871a7a09d5964783a3a3`.
It keeps the measured override profile below, unchanged expectations, existing caches and real authority.

| Item | Correct call / problem caught | Passing fix | Total item time | Fresh model USD | Fresh credits |
| --- | --- | --- | ---: | ---: | ---: |
| c03 | 1/1, currency send-back | 0/1 | 147.759 s | 0.0905193 | 6 |
| c07 | 1/1, discontinued send-back | 0/1 | 97.052 s | 0.0589233 | 4 |

Fresh total **$0.1494426 / 10 credits**; the scoreboard rounds dollars to six decimal places. Timings
include cached and fresh work, not controlled cold-upload latency. [Score](live/score.json),
[stage/candidate diagnosis](live/diagnosis.json), [trace](live/events.jsonl), [console](live/eval.txt).
Both items have zero typed invalidity, warnings or diagnostics. The submitted-page, web/source/archive,
replacement and trace [consistency check passes for two items](live/consistency.json), not full promotion.

Claims retained are **50/209** (76.1% dropped) and web values **54/100** (46.0% dropped).
The preceding revision checkpoint retained 56/209 and 61/124; [before/after](live/diagnosis.json) preserves
both panels. Changed candidate readings/branches are part of these totals; they are not an isolated
model-accuracy estimate. No prompt changed in this correction.

No primary scripted-unconfirmed item or primary investigation occurs. Four replacement investigations
return `found`, none capped; three remain `not_resolved`, one `values_confirmed`. The legacy aggregate
`investigation` field summarizes these replacement steps; use the purpose-tagged `investigations` list
for actual primary/rescue counts. Values confirmed does not establish a complete replacement.
The c03 candidates lack mold/assembly/availability proof and one lacks VOC. SLLT lacks MacAdam/dimming/
currency/availability proof; LT lacks selected DLC/driver and availability proof. No candidate is suggested.
These misses remain at **fix / source-and-selection evidence**, with no cap/provider failure recorded.

Actual cumulative local accounting is now **$2.9516488 / 457**, UTC day **$1.464912 / 99**,
engineering **$1.8930438 / 159**, no holds or persistent block.
[Campaign](live/campaign-status.json), [day report](live/daily-ledger.json). A separate status process can
temporarily report blocked while another process owns active reservations; that does not by itself mean
a cap hit or failed settlement. The completed run's diagnostics and settled ledger establish validity here.

At **08:53:24 UTC**, a redacted Tavily `GET /usage` returned HTTP 200 with **437** for key/account,
comprising 382 search + 51 extract + 4 map. Local credits are 20 higher; the usage GET leaves the ledger
unchanged. [Request, response counters and before/after accounting](live/tavily-usage.json).
The owner's **$2.13 / 421** is account-wide but predates this work and has no synchronized billing cutoff.
No invoice match or cause is inferred; accounting is not reduced to force agreement.

```bash
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/quantity-units-live.json
.venv/bin/python scripts/campaign_budget.py status
```

Reproduction can spend on cache misses. G2 still lacks a fully evidenced passing replacement. Full
current cases/samples/reviewed blind evidence, final image, recording, owner dispositions and approved
hosted proof remain pending; no gate is accepted here. Earlier local images predate this unit correction.

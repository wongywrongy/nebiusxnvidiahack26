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
[output](pytest.txt). Web files were not changed.

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

Targeted live revalidation is separate and will be appended with its actual run identity. G2 still lacks
a fully evidenced passing replacement. Full current cases/samples/reviewed blind evidence, final image,
recording, owner dispositions and approved hosted proof remain pending; no gate is accepted here.

# Unsupported availability bounds — 2026-10-23

An offline synthetic check found another false active status: `available until Q4 2001`,
`through FY2001` and `until end of 2001` bypassed the date guard. These were synthetic
responses, not quotes from a live manufacturer or observations about model behavior.

The shared guard now recognizes these as temporal qualifiers. It does not invent a quarter,
fiscal-year or year-end date: unsupported bounds remain unknown. Ordinary distribution wording
and `until further notice` retain their existing behavior. No prompt, answer key, checklist,
selection policy, default setting or historical recording changed.

| Same quoted synthetic response, evaluated June 1, 2030 | Before | After |
| --- | --- | --- |
| The ZX family is available until Q4 2001. | active | unknown |
| The ZX family is available through FY2001. | active | unknown |
| The ZX family is available until end of 2001. | active | unknown |
| The ZX family is available through distributors. | active | active |
| The ZX family is available until further notice. | active | active |

[Before](bounds-before.json), [after](bounds-after.json) and [reproducer](bounds-reproduce.py).
The baseline is `981c8be`, runtime `1bd1495a7fe75c733886cb4d471371b264657fccad5f2d03e0e260da02c52a8d`.
The isolated correction is runtime `c96827f71513da92c346679ec0cbc87ba9f021a144227f0b52452716be4dd7c2`;
[exact patch and source scope](bounds-source.json). It excludes concurrent replacement-query work.
The shared verification gate and release replay reject the unsupported bound. Eight added regressions
include positive controls; [before: six failures](bounds-tests-before.txt), after: 40 timing tests pass.

The isolated full suite passed **697 / 2 skipped in 32.09 s**; [output](bounds-pytest.txt).
After integration with the separately committed replacement-query correction `ba1a050`, the full
suite passed **698 / 2 skipped in 31.73 s**; [output](bounds-integrated-pytest.txt).
[Before/after hashes](bounds-integration.json) prove the integrated runtime
`d91b4811d8e902254a186a7117af803efdcebef1ecf49938a519f0c4de96a88c` stayed unchanged during that suite.
Both mock evals retain **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**,
zero invalid items, 46/65 claims and 8/20 web values; [integrated score](bounds-integrated-mock-score.json).
Their exit 1 is the disclosed unchanged-key selection-policy disagreement, not a passing release gate.
No frontend file changed.

## Invalid affected-case attempt

The targeted live-mode run **`20261023-103618-93d441`** used the isolated correction, existing caches,
the real local wallet and the measured 65,536-output-token/concurrency-one profile. Its command ran in
the restricted execution context. c03 completed; c07's Tavily check failed after about 60 seconds.
The saved warning does not retain the underlying HTTP exception, so neither a provider outage nor
the execution restriction is established as the cause. This attempt supplies **no valid c07 accuracy
or fix result**, and must be rerun after usage reconciliation with network access available.

| Item | Saved decision | Validity | Claims kept | Web values kept | Item time |
| --- | --- | --- | --- | --- | --- |
| c03 | send_back | valid | 22/78 | 10/44 | 0.781 s, cached work |
| c07 | approve_with_note | invalid: verify/provider, report/accounting | 6/71 | 0/0 | 60.296 s, interrupted check |

[Score](bounds-live/score.json), [trace](bounds-live/events.jsonl), [stage/candidate diagnosis](bounds-live/diagnosis.json).
There are no passing replacements. The release consistency check correctly
[rejects the run](bounds-live/consistency.json): every item must be valid. The invalid item's
unconfirmed status is not a model miss or evidence that the product is active.

Every recorded model-usage entry is cached. No model charge or reported Tavily charge was added,
but the Tavily attempt has **unknown usage with 1 credit held**, not a proved zero charge.
[Exact payment record](bounds-live/payment-audit.json). Settled cumulative usage remains
**$3.36648982 / 490 credits**; the [wallet report](bounds-live/campaign-after.json) and
[UTC mirror](bounds-live/daily-after.json) show **491 total credits including that hold**, blocked true.
UTC-day settled usage is **$1.87975302 / 132** plus the one-credit hold. Nothing was reset or settled
to an invented amount. Owner reconciliation is pending; no further paid call was attempted.

The read-only Tavily usage GET returned HTTP 200 at **10:39:22 UTC**, key/account total **485**
(428 search + 53 extract + 4 map); [redacted request/response](bounds-live/tavily-usage.json).
This aggregate cannot establish the timed-out request's charge or resolve the prior billing gap.

The capture was terminated after item results and the score were saved; buffered console output and
the capture's final response-metadata file were not retained. Its pre-run helper recorded an admission
boolean, not amounts: [false, meaning admission not exhausted](bounds-live/admission-spent-before.json).
The earlier tool observation was $3.36648982 / 490 with no holds; there is no invented numeric
boundary snapshot. Saved results, trace and payment records are the evidence for this attempt.

## Reproduce

```bash
SPECCHECK_MODE=mock .venv/bin/python docs/judge-readiness/status-timing-20261023/bounds-reproduce.py
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/status-bounds-mock.json
# Expected mock eval exit: 1 for the documented raw-key disagreements.
```

To isolate this change, extract `git archive 981c8be` into a temporary directory, apply
[bounds-source.patch](bounds-source.patch), copy the hash-locked public PDFs and the reproducer,
and use the existing venv's absolute Python path. No key is needed for the mock checks.

After actual usage is reconciled, the affected live command is the following. It may spend on cache
misses; use an execution context with network access and inspect the UTC ledger immediately afterward.
Do not remove the hold merely to run it.

```bash
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=65536 MAX_CONCURRENCY=1 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/status-bounds-live.json
.venv/bin/python scripts/campaign_budget.py status
```

G2 remains open. Broader cases/samples, reviewed blind evaluation, final recording and hosted work
remain gated. Neither authorized full-set follow-up nor the final recording has been consumed.
The previously frozen local image predates this correction; no registry/cloud action occurred.

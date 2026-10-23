# Lifecycle timing gate — 2026-10-23

An **offline synthetic response** reproduced a false current failure: a manufacturer quote saying the
ZX family *will* be discontinued in 2035 passed the existing status gate today. An invented date and a
replacement name elsewhere on the page also survived. This was not an observed live-model response,
a new case score or a blind-set evaluation.

The shared verification gate now binds named-month/ISO calendar dates to the product's lifecycle
statement and checks them against the UTC date. A future start, expired availability window, undated
future plan, invalid date or unresolved temporal qualifier stays unconfirmed. Present undated notices
still work. A past effective date is derived from the actual quote, never the model's date field;
replacement metadata must occur in the status quote. Existing identity and fetched-page quote gates
remain mandatory. Scripted reads, Investigator reads and release replay already share this function.

| Same synthetic response | Baseline `e1a4c2e` | Corrected gate |
| --- | --- | --- |
| Future discontinuation | Major failure / send back | Unknown / approve with note |
| Undated future plan | Discontinued | Unknown |
| Past effective notice | Discontinued, invented 1999 date | Discontinued, quoted 2001-05-01 |
| Availability starts in 2035 | Active | Unknown |
| Availability ended in 2001 | Active | Unknown |
| Present notice, invented date/replacement | Metadata retained | Unsupported metadata removed |
| Release replay accepts future failure | true | false |

[Actual same-input before](before.json) and [after](after.json) identify both runtime hashes. The corrected
runtime is `1bd1495a7fe75c733886cb4d471371b264657fccad5f2d03e0e260da02c52a8d`.
[Integration preimage checks](integration.json) show that only the owned API/test changes were replaced;
other work and owner files were preserved. No prompts, case expectations, reviewed requirements, caches,
wallet balances or environment defaults changed.

Thirty-two new regressions cover future/past dates, punctuation and ordinal formats, invalid/conflicting
dates, publication dates, active windows, metadata and release replay. Integrated full suite:
**689 passed / 2 skipped in 32.31 s**; [output](pytest.txt). The isolated suite also passed, 689 / 2 in
31.25 s. Raw [mock score](mock-score.json): **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing
fixes**, zero invalid items, 46/65 claims and 8/20 web values. Expected exit 1 retains the selection-policy
disagreements; [console](mock-eval.txt). No frontend file changed.

```bash
SPECCHECK_MODE=mock .venv/bin/python docs/judge-readiness/status-timing-20261023/reproduce.py
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/status-timing-mock.json
# Mock eval intentionally returns 1 for the unchanged raw-key disagreements.
```

For the baseline, extract `git archive e1a4c2e` into a temporary directory and run the same reproducer
there with the existing venv's absolute Python path and `SPECCHECK_MODE=mock`. The script imports the
current working directory and makes no network/provider request. Other date notations are deliberately
unconfirmed; add parsing only with observed examples and regression coverage.

This offline correction adds **$0 / 0 credits**. Before the affected-case live check, actual settled local
accounting is **$3.36648982 / 490**, UTC day **$1.87975302 / 132**, no holds or persistent block. The
account-wide dashboard observation predates that checkpoint; billing reconciliation remains open.
G2 still lacks a complete passing replacement. This proof does not accept a gate or validate the full
set, blind packages, a final recording/image, hosted operation or deployment.

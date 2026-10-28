# Accuracy A/B — October 28, 2026

Question: does a stronger model (Nemotron 3 Ultra) or more reasoning (thinking) improve the live panel before the 19:00 PT freeze? **Answer: no. Ship arm A** (merged master with the default config: Nemotron 3 Super everywhere, thinking only for checklist drafting). It is promoted as `runs/recorded/20261028-173729-554074/`.

Code: merged master `30ca3ec` (PR #20 + PR #21) plus `4138a41`, which fixes a PR #21 bug that divided the per-item time and cost by a drop-reason count instead of the item count. The Scoreboard would have shown $0.0099 and 8.9 s. Answer key, reviewed checklists and prompts are untouched; the arms differ only in environment variables.

All arms: live, local, the same 8 cases + s3 + s4, the shared cache and ledger, $0.40/item-equivalent run cap (see Caps), 60 credits/item, concurrency 2, one fix candidate, `MAX_OUTPUT_TOKENS=65536`. Runs were sequential: the ledger refuses a second process while another holds an unsettled reservation, so the first parallel B/C start was refused before any call ($0).

| Arm | Config |
| --- | --- |
| A0 | Reference: PR #20 recording `20261028-171142-5ca0fc` (not re-run) |
| A | Default: Super for extract/verify/write, Nano for triage, thinking only for `extract_requirements` |
| B | A + `THINKING_TASKS=extract_requirements,extract_claims,product_type,verify,investigate,replacement` |
| C | A + `MODEL_EXTRACT=MODEL_VERIFY=nvidia/Nemotron-3-Ultra-550b-a55b` |
| D | Not run: B did not help |

## Results

| Measure | A0 (PR #20) | **A** | B (thinking) | C (Ultra) |
| --- | --- | --- | --- | --- |
| Run | `171142-5ca0fc` | **`173729-554074`** | `174706-910df5` | `180911-17c5a1` |
| Right calls | 6/8 | **6/8** | 4/8 | 5/8 |
| Problems caught | 5/6 | **5/6** | 3/6 | 5/6 |
| Clean cases wrongly flagged | 0/2 | **1/2** | 0/2 | 0/2 |
| Unnecessary notes | 1 | **0** | 2 | 2 |
| Passing replacements | 0/5 | **0/5** | 0/5 | 0/5 |
| Invalid items | 0/8 | **0/8** | 0/8 | 3/8 (+ s3 not run) |
| MAX_OUTPUT_TOKENS hits | 0 | **0** | 0 | 1 (c05 `verify.read`, Ultra, thinking off) |
| Claims kept / extracted | 75/292 (25.7%) | **91/235 (38.7%)** | 54/129 (41.9%) | 145/513 (28.3%) |
| Web values kept / read | 28/260 (10.8%) | **39/320 (12.2%)** | 4/92 (4.3%) | 56/112 (50.0%) |
| Cost per item, model + web, priced uncached | $0.148 | **$0.126** | $0.155 | $0.286 recorded usage; **$0.64 ledger** |
| Fresh spend for this run | $0.729 / 19 | **$0.586 / 29** | $0.964 / 56 | $5.715 / 45 |
| p50 / p90 item time | 55 s / 127 s | **75 s / 230 s** | 176 s / 313 s | 109 s / 345 s |
| Reasoning tokens | 0 | **0** | 328,819 | 0 |

Top 5 quote-gate drop reasons (A0 predates the counter):

| A | B | C |
| --- | --- | --- |
| web:quote_not_on_source 261 | web:quote_not_on_source 88 | claim:metric_not_in_quote 184 |
| claim:quote_not_on_page 49 | claim:unit_not_in_quote 22 | claim:unit_not_in_quote 89 |
| claim:value_not_in_quote 35 | claim:quote_not_on_page 21 | claim:value_not_in_quote 39 |
| claim:bad_page 28 | claim:metric_not_in_quote 17 | web:quote_not_on_source 37 |
| claim:unit_not_in_quote 17 | claim:value_not_in_quote 14 | claim:quote_not_on_page 36 |

### Every changed decision

October 22 and A0 made identical decisions, so each change below is the same against both.

| Item | Expected | Oct 22 / A0 | A | B | C |
| --- | --- | --- | --- | --- | --- |
| c01 | approve | approve | approve | approve with note ✗ | approve with note ✗ |
| c03 | send back | send back | send back | approve with note ✗ (currency missed) | send back |
| c05 | approve | approve with note ✗ | **send back ✗** | approve with note ✗ | approve with note ✗ |
| s4 | (tray) | approve with note | approve with note | send back | approve with note |
| s3 | (tray) | approve with note | approve with note | approve with note | not run (run cap) |

c08 in B kept its decision but missed its currency note (caught 0 of 1). c06 is wrong in every arm: its currency problem is missed.

- **A, c05 → send back.** A fresh extraction (39 of 46 calls uncached) quoted "10 %" minimum dimming against the ≤ 5 % rule, a major failure on a clean case. The same family of code made a different call than A0, so run-to-run variance alone moves single decisions; differences of one item between arms are within noise.
- **B** extracted about half as many claims and read about a third as many web values. Thinking made the extractor terser and the web reader nearly useless (4 values kept).
- **C** kept far more web values (50% vs 12%) but lost precision on claims (`metric_not_in_quote` 184). Its invalid items: c02 hit the $6 run cap, c04 hit the Investigator's 8-credit step cap, c05's verify reply hit 65,536 output tokens. `MAX_OUTPUT_TOKENS` stays 65536 as instructed. c02 alone was charged **$3.65 against $0.23 of recorded usage**. The ledger (checked during the final release) shows why: 471 paid c02 requests over its 24-minute manufacturer check, all with reported usage and none settled at a hold, so these were real calls, not timeouts. Its result kept only the usage of the calls it used. Look at this request loop before ever deploying Ultra.

## Decision (rule pre-approved by Kyle)

1. Most right calls: **A (6/8)** > C (5/8) > B (4/8). A is the baseline, so the "no added false alarms or unnecessary notes versus A" check is trivially met. C and B would each add 2 unnecessary notes.
2. A is deployable: $0.126/item, p50 = A. No hybrid applies (the winner is A). An Ultra-for-verify-only hybrid was **not measured**: C improved web drops but not claims, and C still loses on calls.
3. Nothing to overfit: env-only arms; answer key, checklists and prompts untouched.

**Ship A: no `MODEL_*` or `THINKING_TASKS` change; `BUDGET_USD_PER_RUN` stays $3.** Nemotron 3 Nano sorts pages; Nemotron 3 Super extracts claims, reads manufacturer sources, investigates and writes the result; Super with thinking drafts checklists. Nemotron 3 Ultra was tested and is not used.

Promoting A changes the public panel from A0's **0/2 false alarms, 1 unnecessary note** to **1/2 false alarms, 0 unnecessary notes** (c05). Right calls and problems caught are unchanged at 6/8 and 5/6. The recording now matches the code being deployed (PR #20 + #21).

## Wrong-spec check on the shipped code

Run `20261028-183608-dfa1b9`, $0.50 ceiling: **0/14 approved**, 13 not applicable, 1 sent back (w-c05, LED troffer under 07 84 00, same as A0). Written into the promoted `scores.json`. [Log](wrong-spec.log).

## Caps

- **Run cap:** arms B and C ran with a $6 run cap instead of $3, because one eval "run" is all 10 items. $6 = $0.40/item × 10 × 1.5, the decision rule's own formula, so a deployable arm is never cut off by the size of the run. A ran at $3 and stayed far below it.
- **Ledger:** the shared local ledger's engineering phase allowed only $3.99 more, so the $15 / 400-credit experiment ceiling was added in place with Kyle's approval: [ledger-raise.json](ledger-raise.json). Same ledger, no reset, no payment touched.
- **Promoted scores:** `scores.json` was generated by the pre-fix code; its `time_ms_per_item` and `cost_usd_per_item` were recomputed from its own rows with the fixed formula (8943 → 114026 ms, $0.009867 → $0.125803). No other field changed.

## Accounting (shared local ledger)

| | Model USD | Tavily credits |
| --- | --- | --- |
| Day total before | 3.04944932 | 186 |
| A | 0.585586 | 29 |
| B | 0.963653 | 56 |
| C | 5.715270 | 45 |
| Wrong-spec | 0.03704130 | 1 |
| **Experiment total** | **7.30155040** | **131** |
| Day total after | 10.35099972 | 317 |

Within the $15 / 400 ceiling. [After](local-ledger-after.json). Hosted verification charges are added after deployment.

Files: per-arm logs and `scores.json` (`arm-*.log`, `arm-*-scores.json`), the arm runner [run-arm.sh](run-arm.sh) and the table script [compare.py](compare.py). Deploy: [HANDOFF.md](HANDOFF.md).

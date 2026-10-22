# Gate 4 review — 2026-10-21

**Kyle authorized continuation on 2026-10-22: “finish all unfinished things”.** Proceeding with the documented limitations disclosed; no approval of changed checklists, answer keys or deployment is inferred. Four Phase 4 full evaluations are complete; Phase 5 recording is a separate requested run.

Final cases: `20261021-112213-cb4555`. Samples: `20261021-112328-21358e`.

| Panel | Original mock baseline | Final live cases | Live samples |
| --- | ---: | ---: | ---: |
| Right calls | 8/8 | 6/8 | 1/4 |
| Problems caught | 6/6 | 5/6 | 0/2 |
| Major false alarms | 0/2 | 0/2 | 0/3 |
| Passing fixes | 2/5 | 0/5 | 0/1 |
| Claims retained | 48/48 | 149/185 | 170/185 |
| Web values retained | 19/20 | 27/40 | 11/11 |

The major-false-alarm metric excludes unnecessary notes: c05, s1 and s2 are still wrong calls.
Final cases averaged **3.365 s/item** with warm caches and **$0.033602 equivalent/item**. The preceding mixed-cache run averaged **46.159 s/item**, $0.063565 equivalent/item. Samples averaged **62.568 s/item**, $0.035761 equivalent/item. No fully cold eight-case benchmark was performed. Equivalent cost includes cached model usage; it is not fresh billing.

Fresh final-case charge: **$0.024414 / 0 credits**. Fresh sample charge: **$0.042923 / 11 credits**.
Whole-pass local ledger: **$1.048778 Token Factory / 291 Tavily credits**. Console billing remains unverified. Kyle’s earlier Tavily dashboard observation was **15/9000**, with no timestamp or account/key scope; a synchronized updated reading has been requested.

The final cases and samples contain **no cap/provider warnings or error events**. No 429 was observed.

## Final case diagnoses

Counters below include replacement candidates. Stage evidence, redacted requests/responses, findings and reproduction commands are in [full-fourth-diagnosis.json](full-fourth-diagnosis.json).

| Item | Extracted → kept claims | Read → kept web values | Call / remaining issue |
| --- | ---: | ---: | --- |
| c01 | 19 → 5 | 5 → 4 | Correct approve. Current linked STI PDF matches; no remaining call miss. |
| c02 | 14 → 11 | 7 → 7 | Correct F/T send-back (quoted F=2, T=0). Extra revision note comes from a generic certificate rather than an exact-system document: verify identity remains weak. Fix: FIP product sheet lacks the failed F/T evidence; now blocked with an unknown check. |
| c03 | 22 → 12 | 12 → 7 | Correct currency send-back. Old/current quoted E84 flame-spread and smoke-development values differ, as does the temperature label/value. No passing fix: CP25WB+ and 3000WT candidates lack kept VOC/G21 and/or standards evidence. Extract/read incorrectly use UL category 90G9 as a revision; metadata quality remains open. |
| c04 | 11 → 11 | 3 → 2 | Correct steel-penetrant validity send-back from the quoted plastic-pipe list. Investigator did not establish the exact current listing. Alternative WL-1049 has unknown T-rating and pipe-type checks; no passing fix. |
| c05 | 25 → 20 | 2 → 2 | Wrong note versus approve. Extract drops unsupported DLC/warranty values; first-page warranty is beyond the 6,000-character input excerpt. L70 is not confirmed; the kept 10% dimming statement is explicitly Non-Configurable BLT. Different 2025 revision alone remains a note. L70 is not the sole reason, so the special missing-only answer-key rule is not met. |
| c06 | 16 → 16 | 8 → 2 | Missed currency send-back. Extract/selection cannot choose one old wattage/efficacy variant. Basic current LDN6 extraction is unreadable; Investigator instead retrieves an LDN6 SWW sheet with a quoted 2022 revision. Comparable kept CRI and warranty match; no grounded changed measurement is established. Unknown remains a note. |
| c07 | 66 → 63 | 0 → 0 | Correct discontinued send-back from the manufacturer TL-family notice. Two replacement investigations finished not_found without caps. Blocked/raw manufacturer PDFs and weak alternative discovery prevent a passing fix. |
| c08 | 12 → 11 | 3 → 3 | Correct note for missing L70/MacAdam and different revision. These are not the sole missing-row-only trigger. Additional extract semantic error: a power statement was labelled lumens, though its literal quote is real; no verdict depended on it. |

## Sample diagnoses

Evidence: [samples-first-diagnosis.json](samples-first-diagnosis.json).

| Sample | Stage / root cause |
| --- | --- |
| s1 | Wrong note versus approve. Extract returned VOC value 250 with a `<250` quote; the bound gate correctly dropped it. G21 is not kept. This is extraction/requirement evidence missing, not a failed product. Claims 3/6; web 3/3. |
| s2 | Same BLT document and roots as c05: L70, warranty, DLC, unresolved configuration, different revision. Claims 20/25; web 2/2. |
| s3 | Wrong note versus send-back; both spec/currency problems missed. Extract kept 10% dimming scoped to “Non-Configurable BLT”; the code excludes variant-limited values without a resolved selection. Old/current performance variants are not comparable. Requires a general configuration-selection policy, not an assumption that this option applies. Claims 145/152; web 4/4. Extraction produced 25,484 output tokens in 168.397 s, reasoning 0: excessive extraction remains a latency problem. |
| s4 | Correct note. G21 “Class 0” is quoted but the numeric comparator cannot parse the Class prefix; other spec evidence is missing and revision differs. Additional general numeric-format limitation, not a pass/fail inference. Claims 2/2; web 2/2. |

## Investigator outcomes

In the final cases, the scripted check triggered **2 primary investigations**: c04 and c06. One returned a quoted document revision (c06’s LDN6 SWW); **0 resolved the missing planted problem**, and exact-configuration identity remains uncertain. The other ended not_found. **0 were capped**. Four additional replacement investigations returned one found document and three not_found; none produced a passing fix, and none was capped. See the separate `investigations` records in the diagnosis JSON. No primary investigation was needed for samples.

## Review decisions still needed

- Accept or reject these case/sample/fix root causes before Phase 5, as required by the Gate 4 rule. This is not an 8/8 result.
- F04: existing comparison remains conditional on both ratings being present. Making all missing pairs unknown broke the mock panel and was reverted; Kyle’s applicability decision is still pending. Candidate fixes must now demonstrate the original failed requirement independently of that policy.
- Input excerpt: 6,000 characters remains unchanged. The requested 12,000-character experiment has not been approved or run.
- Provide synchronized Tavily dashboard usage/scope; Token Factory console billing is still a later owner reading.

Reviewed checklists and `data/cases/*.json` expectations are unchanged. No source URL, case-specific branch or expected value was added to live prompts/code. The two corrected mock fixtures use only source text already stored in those fixtures; live routing does not use them.

## Changes and reproduction

Before/after changes and all earlier baseline/cap retries are in [../live-first-pass.md](../live-first-pass.md). The last two changes block a fix with no evidence for its original failed requirement, and require categorical identifiers in their supporting quote. The final full run removed the false coded passing fix (1 → 0); calls stayed 6/8. Mock validation: **244 passed, 2 skipped in 12.13 s**; mock eval **8/8**, 6/6 problems, 0/2 major false alarms, 2/5 fixes. No web code changed.

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/speccheck-mock.json
MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 .venv/bin/python scripts/eval.py --out /tmp/speccheck-live-full-fourth.json
MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 .venv/bin/python scripts/eval.py --samples --out /tmp/speccheck-live-samples-first.json
```

These full-run commands document reproduction; do not execute a fifth full eval in this pass. Retry caps were per-command and are not changed defaults. The local app/recording must use the disclosed limits to reproduce the valid assessment; deployment configuration has not been verified.

Recommendation from this evidence: **do not deploy on Oct 22 yet**. The current app misses c06 and the tray sample s3, adds approval notes to clean items, and has no passing live fixes. Demo replay, judge UI walk, smoke test, new upload, screenshots, FEEDBACK/README final updates and PR are still unverified/uncompleted. No deployment or cloud-resource operation was performed.

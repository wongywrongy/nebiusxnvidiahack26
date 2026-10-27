# G2 targeted live validation — 2026-10-22

Kyle authorized live validation after accepting the disclosed selection-policy disagreements. Original case/sample expectations and reviewed checklists remain unchanged. This is engineering validation, not release acceptance.

## Profile

Commands use live mode, `MAX_OUTPUT_TOKENS=32768`, `INVESTIGATE_MAX_STEPS=24`, `INVESTIGATE_CREDIT_CAP=30`, `FIX_CREDIT_CAP=40`. These are the previously tested quality overrides, not a default-profile baseline. Runtime manifests record every effective setting. Existing daily caps remain $8 / 600 credits; item cap 60, run cap $3, concurrency 2, thinking off. Cumulative campaign cap $20 / 2,000; additional engineering allocation $10 / 1,000.

## Runs

| Run | Item | Calls / problems | Invalid items | Passing fixes | Claims kept | Web values kept | Elapsed | Fresh Token Factory / Tavily | Cumulative actual spend |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `20261022-223246-9cbcfb` | c03 before identity correction | 0/1 / 0/1 | 0 | 0/1 | 11/23 | 0/44 | 96.617 s | $0.0323775 / 8 | $1.0909825 / 306 |
| `20261022-223541-d36a04` | c03 after identity correction | 1/1 / 1/1 | 0 | 0/1 | 15/86 | 7/31 | 214.175 s | $0.1210911 / 16 | $1.2120736 / 322 |
| `20261022-224517-45ecb8` | c03 after catalog guard/source priority | 1/1 / 1/1 | 0 | 0/1 | 13/66 | 14/38 | 156.218 s | $0.0762723 / 9 | $1.2883459 / 331 |
| `20261022-224854-85a22c` | c03 warm check after selection guards | 1/1 / 1/1 | 0 | 0/1 | 13/66 | 14/38 | 0.448 s | $0 / 0 | $1.2883459 / 331 |
| `20261022-224901-c1a03d` | c07 before family/header/format correction | 0/1 / 0/1 | 0 | 0/1 | 2/15 | 0/1 | 132.156 s | $0.0903978 / 17 | $1.3787437 / 348 |
| `20261022-225234-b12ca2` | c07 descriptor-only warm diagnostic; still wrong | 0/1 / 0/1 | 0 | 0/1 | 2/15 | 0/1 | 0.117 s | $0 / 0 | $1.3787437 / 348 |
| `20261022-225656-f21c6c` | c07 after header/format/subject correction | 1/1 / 1/1 | 0 | 0/1 | 6/19 | 29/40 | 192.143 s | $0.1079931 / 10 | $1.4867368 / 358 |
| `20261022-230145-fc12db` | c03 + c07 final guarded warm panel | 2/2 / 2/2 | 0 | 0/2 | 19/85 | 43/78 | 0.890 s average | $0 / 0 | $1.4867368 / 358 |

The first run had no warnings, provider errors, output cap or investigation cap. It is a real pipeline miss. [Scoreboard](c03-live-before.json), [diagnosis and trace](c03-before-diagnosis.json).

## General correction: preserve identifiers and requested properties

Before extraction prompt: `Use these property names and meanings where they apply`; it allowed unrelated aliases. Identity instructions described listed systems but did not distinguish a product identifier from a selected ordering configuration.

After extraction prompt: `Return only these property names, with exactly these spellings and meanings`; the JSON schema enumerates allowed properties and code drops unrequested names. `For a product, record its short printed product/model identifier as model, not a rewritten marketing title. A product identifier names the product; selection separately proves a chosen ordering configuration.`

Before verification prompt: `For each value, give source_url and an exact identity_quote naming that source’s model.`

After verification prompt additionally requires copying the submitted identifier only when it is printed in the same source identity quote. The submitted family is now included in the read context. Scope quotes must include the quoted value rather than only a table heading. No expected values or case identifiers enter these prompts. Quote, value, unit, identity and selection gates are unchanged.

Regression after this correction: **354 passed, 2 skipped** in **14.96 seconds**. Mock run `20261022-223534-945a09` retains the raw **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 fixes** and **48/65 claims, 8/20 web values**; fresh charges **$0 / 0**. The new regression proves an unrequested property alias cannot escape the allowlist.

No full follow-up scoring-set live evaluation or new demo recording has run yet. Deployment, blind packages and hosted durability remain unchecked.

## Catalog attribution correction

The first identity-corrected run retrieved a broad manufacturer catalog as a candidate. An independent synthetic reproduction showed that VOC from one product and service temperature from another could jointly pass requirements after conflicting model metadata was reduced to null. The real candidate did not pass (T-rating mismatch and missing mold evidence), but this exposed an unsafe general path.

Extraction now quarantines claims when chunk identities conflict, cannot be grounded, or disagree with claim identity. The exact quotes remain visible; ambiguous claims cannot satisfy requirements or a replacement. No model ID, case branch, expected numeric value or checklist edit is used. Mixed product/assembly packages lacking explicit attribution remain unconfirmed. Replacement verification skips candidates with no comparable claims. Search prioritizes the already-quoted changed-value source before other search hits, with normal extraction and verification still required.

The original fixture system W-L-1079 now has its printed system number in model metadata; no ratings changed. A synthetic Investigator candidate now includes its product name in the synthetic page. These are evidence-contract corrections, not new live proof.

Additional independent review identified selection from another product sharing a driver and selection being restored during bundle merge. Both were closed: the selected product must match every grounded chunk identity, and selected-candidate bundle merges require the same re-extracted validated selection. Ambiguity clears selection, leaves scope unknown and cannot be rebound. The reviewer confirmed both fixes with positive controls.

## Family status and formatting correction

The first c07 live run was a valid miss, not a swallowed provider failure: no warning, cap or provider error occurred. [Trace/diagnosis](c07-before-diagnosis.json). The descriptor-only correction did not fix the call and spent nothing; it is retained as a failed intermediate experiment.

A cache-only diagnostic disabled both provider HTTP entry points. It showed submitted identity `T Series LED`, reader status family `TL family`, exact quote false, and quote after removing paired bold markers true. The submitted PDF header actually prints the numeric series identifier; the old broad ordering-example rule erased it merely because the page also contained an example.

Before: any model appearing on a page with `Example:` could be replaced by family metadata. After: an identifier printed before the ordering example remains an identity, without conferring a selected configuration. An example-only full order code still cannot select an option.

Before: family matching required an exact descriptor form and only considered family metadata. After: generic family/series/range suffixes are normalized; the printed family or model must establish membership. The family must be the subject of the quoted same-clause status predicate. A member-only notice or an unrelated family's discontinuation cannot supply that status. Model-specific status also needs its own subject predicate.

Before: Markdown `**date**` and plain date text differed at the quote gate. After: paired inline bold formatting is normalized on both sides, preserving native PDF footnote markers, all words, numbers and page boundaries. Regression controls reject a changed year, prefixed neighboring model and split-subject notice. Formatting normalization does not paraphrase source text.

## G2 checkpoint to review

[Final two-item panel](targeted-final-panel.json), [quoted findings and trace](targeted-final-evidence.json), [final mock panel](mock-scores-final.json), [pytest](pytest-final.txt), [local wallet](campaign-status-final.json).

- Targeted live-mode final: **2/2 calls, 2/2 problems, 0/0 clean-package false alarms, 0/2 passing fixes**, no invalid items or extra notes. This is **not** an eight-case accuracy result.
- Quote gates: **19/85 claims kept (77.6% dropped)**, **43/78 web values kept (44.9% dropped)**. Counters include replacements and repeated source reads; the changing candidate mix prevents attributing every rate difference to one prompt.
- Primary Investigator: **1 scripted-unconfirmed item, 1 primary run, 1 resolved problem, 0 capped runs**. c03 recovered the quoted service-temperature difference. c07's scripted status check succeeded after correction; it needed no primary rescue. The rescue is a real primary recovery, not proof of a newly discovered URL: the Investigator re-read a manufacturer document already encountered by the script.
- Fresh model charges added in this follow-up: **$0.4281318 / 60 Tavily credits**. Cumulative pass: **$1.4867368 / 358**. No outstanding reservations. The last confirmation used cached live responses, adding **$0 / 0**. Runs with fresh calls were also partly cached; no cold end-to-end benchmark was performed.
- Recorded run times with fresh work included **156.218 s for c03** and **192.143 s for c07**. The final warm average **0.890 s** does not establish fresh latency. The displayed per-item cost combines model usage (including cached usage) with new web charges; fresh charges are reported separately.
- Final regression: **382 passed, 2 skipped in 15.38 seconds**. Raw mock score remains **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 fixes**, with exactly the approved selection-policy disagreements. Web presentation checks/build passed; no follow-up browser walk was made.

**G2 remains open.** c03's current product sheet does not establish all required mold/assembly evidence. The c07 CPX candidate has accepted DLC/current-document checks, but L70, warranty, MacAdam, dimming and current availability remain unconfirmed. Neither is promoted to a passing replacement. The next replacement work must obtain a complete, attributable configuration/evidence bundle; lowering requirements or inventing selection is not an acceptable fix.

No full follow-up eight-case eval, sample eval, blind set or new demo recording was made. No deployment or cloud resource was created. Stop at this checkpoint for Kyle's review; do not advance to G3 or declare readiness. Kyle replied “that is correct” to the reported cumulative $1.4867368 / 358 totals on 2026-10-22. This is owner confirmation of the reported totals; a separate dashboard readout, its timestamp and account/key scope were not supplied. The earlier three-credit gap is still unexplained, and no ledger was adjusted.

Reproduce the final targeted panel (cached calls are free; expired/new web calls may spend):

```bash
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/g2-targeted.json
.venv/bin/python scripts/campaign_budget.py status
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/g2-mock.json  # expected exit 1; raw key disagreements preserved
```

Clean-install mock preflight with `RAW_DIR=/tmp/speccheck-g2-no-pdfs` reproduced the same raw 6/8 calls, 5/6 problems, zero invalid items and gate counters, with $0 / 0 fresh charges. [Scoreboard](mock-scores-no-pdfs.json).

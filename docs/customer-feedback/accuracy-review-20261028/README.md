# Accuracy fixes for the morning review

Extraction commit: `03d61eb`, followed by the draft-feedback/configuration and evidence commit on branch `fix/review-accuracy`, based on released master `5385a08`. [Draft PR #20](https://github.com/wongywrongy/nebiusxnvidiahack26/pull/20) is for the morning review. This branch is **not merged or deployed**. Production remains frozen at runtime `14ddb6d`; the video worktree is untouched.

## Confirmed fixes

- **c01 approves without unnecessary notes.** A printed model can bind the document's own display name. Ordinary properties with uncertain scope no longer become ordering instructions: only explicit `scope=option` claims can produce Specify lines. The independent release validator uses the same identity rule.
- **c04 sends back the steel-pipe mismatch.** Extraction had all six plastic-pipe types but cited a summary omitting PEX. For explicitly numbered penetrating-item lists, the repair now uses the complete contiguous enumeration on the same page. It keeps every original array value, excludes studs and adjacent sections, and preserves scope limits. Other layouts still fail the quote gate. Two attempted model-based quote repairs returned no useful correction; that extra paid repair path was removed.
- **Lighting extraction retains the warranty.** PDF word wraps such as `speci-` plus a line break no longer discard an otherwise exact warranty quote. Continuation chunks receive the first-page header for identity only; values must still be quoted on their own pages. Mixed-product and unselected-option checks remain in force.
- **Draft shape and alternatives are checked.** The actual response schema caps drafts at 30 rows. Model/series naming, product types, warranty priority and approved-alternative grouping have clearer instructions. Contradictory duplicate manufacturer/model/series rules for one type trigger the existing validation retry, with every conflicting group named together. Drafting alone opts into reasoning by default; extraction, verification, Investigator and report retain their prior reasoning settings. Saved project requirements remain untouched and drafts remain unreviewed.
- **Research reuses available evidence.** Investigators receive already extracted pages and missing metric quotes. A failed document lookup reserves the third-to-last slot for a fallback search, then extraction and finish, within the existing tool/credit caps. Typed `DOC_Type=SPEC_SHEET` links take priority over marketing PDFs; public-URL validation is unchanged.

## Measured checks

On committed `03d61eb`, live run **`20261028-090749-c1a0ea`**: c01 **approve**, c04 **send_back**; **2/2 right calls, 1/1 planted problem caught, zero unnecessary notes, zero invalid results**. Full results and the scoped panel are beside this file. Fresh charge: **$0.035554 / 6 Tavily credits**. The panel gate still reports missing passing replacements and no demonstrated Investigator rescue; a two-case run cannot establish full-panel accuracy.

- Final local Python suite: **793 passed, 2 skipped**. Provider traffic is intercepted by the test harness.
- Existing browser journeys: **17 passed** against the isolated mock server on port 38427. An earlier attempt selected occupied port 8017; its result is discarded for this branch's verification.
- Unchanged-answer-key mock panel: **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**. It exits 1 intentionally on the two existing disagreements.
- No second full eight-case live panel was run. c05/c06 diagnostic runs and scoped retries retain their real results; no answer key, reviewed checklist or recorded public score was changed.
- Fresh UBC draft with Super reasoning: **12 rules, unreviewed**, including warranty and grade rules, **$0.00443880 / 0 credits**, 1,228 reasoning tokens. [draft.json](draft.json) is a cached confirmation under the final default configuration. The default-off attempts were rejected when contradictory groups remained after the bounded retry; their charges remain in the ledger. The schema cap did produce 30-row drafts earlier, but some omitted numeric rules, so they are not the retained draft.

## Work still requiring review

**c05 remains approve with note versus expected approve.** Run `20261028-084056-309b06` retains the 5-year warranty and stable product identity. The source states L80/60,000, conditional DLC qualification and multiple driver configurations. That is not an exact L70 quote or proof of a selected compliant driver/SKU. Do not relabel L80 as L70, choose EZ1 implicitly, or strip qualification conditions to obtain the expected decision. A separate, justified stronger-threshold rule would need domain review; it is not implemented here.

**c06 automatic discovery remains unresolved.** Final discovery run `20261028-090424-5cce37` still returns approve with note. The manufacturer's current API/CDN PDF returned HTTP 403, and automated searches spent their bounded calls on unreadable or different suffixes. A manually found, accessible manufacturer-authored static LDN6 sheet is available at the URL in [ldn6-source.json](ldn6-source.json), with PDF hash and revision `05/03/22`. It states **70% lumen maintenance at 60,000 hours**, versus the submission's 50,000 hours. Supplying that source to the ordinary reader/gates/comparison produces **currency-outdated**, recorded in [c06-manual-source.json](c06-manual-source.json). This is a source diagnostic, **not an autonomous discovery rescue**. Improve general retrieval to reach such a copy; do not hardcode this case or mix LDN6 SWW/cylinder performance into the static downlight.

A broad scripted metric lookup was tried and removed: it selected an old 2017 mirror and could make unchanged old values look current. The final branch does not contain that lookup. Printed changed-value evidence is available; source selection remains the missing step.

**Passing replacements remain unproved.** Scoped c04 research produced no evidenced passing replacement. No replacement is marked passing without all applicable requirements, source/currentness and availability evidence. The release's 0/5 remains the last full-panel measurement. Finding a genuinely passing candidate is still open.

**Drafts still need human coverage review.** The retained 12-rule draft includes warranty/grade requirements but omits the approved manufacturer/model lists. It is not exhaustive. Check property names, warranty scope, product-type consistency and required categories before using it; add the relevant approved-model rule when needed. The 30-row cap and contradictory-alternative validation are enforced, but a large multi-product section cannot be assumed exhaustively represented by its first generated draft. The source is the public [UBC Door Hardware guideline](https://www.technicalguidelines.ubc.ca/guidelines/087100-Door_Hardware_UBCV.pdf); no reviewed project checklist was replaced.

## Handoff and reproduction

Worktree: `/home/kyle/code/nebiusxnvidiahack26/.cache/customer-feedback-finish`. Original video branch: `/home/kyle/code/nebiusxnvidiahack26`; leave it alone. This worktree's ignored `.env`, `.venv`, raw PDFs and node modules reuse the existing local setup. No credentials are committed.

Offline:

```sh
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/accuracy-mock-panel.json
```

The second command is expected to exit 1 with the raw 6/8 panel. Live checks must use the original shared cache and SQLite ledger; never reset them or switch to an empty ledger to evade caps:

```sh
SPECCHECK_MODE=live \
CACHE_DIR=/home/kyle/code/nebiusxnvidiahack26/.cache \
CAMPAIGN_BUDGET_FILE=/home/kyle/code/nebiusxnvidiahack26/evidence/budget/campaign.sqlite3 \
BUDGET_USD_PER_DAY=4.84392002 BUDGET_USD_PER_RUN=3 \
BUDGET_TAVILY_CREDITS_PER_DAY=310 BUDGET_TAVILY_CREDITS_PER_ITEM=60 \
FIX_MAX_CANDIDATES=1 MAX_CONCURRENCY=2 MAX_OUTPUT_TOKENS=65536 \
.venv/bin/python scripts/eval.py --case c01 --case c04 --out /tmp/accuracy-targeted.json
```

Those day ceilings bound this continuation to an incremental **$3 / 180 credits**, starting from local day totals **$1.84392002 / 130**. Actual incremental charge for all diagnostics, including failed attempts: **$0.36584730 / 29 credits**. Final local day total: **$2.20976732 / 159 credits**, zero open holds. [accounting.json](accounting.json) records the snapshot. Public judging and the GitHub fallback use separate ledgers; neither is reset here. Actual cloud/CI billing is not measured.

Review the extraction identity change and the draft's coverage before promotion. Merge/deployment is left for the morning review; this PR does not replace the frozen image or alter the daily fallback.

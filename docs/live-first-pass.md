# First live pass — 2026-10-21–22

Follow-up state on October 23: [readiness and ownership](judge-readiness/ownership.md). Additional targeted
retrieval/reliability work brings actual cumulative spend to **$1.9702294 / 391 credits**. No later dashboard
readout with scope/time was supplied; the historical three-credit discrepancy below remains unresolved.
The dated first-pass figures and recording in this document remain historical evidence.

Status: Gates 1–3 accepted and pushed. On 2026-10-22 Kyle directed “finish all unfinished things”, authorizing continuation past Gate 4 with the recorded limitations disclosed.
All **four** permitted full live evals are complete: final cases **6/8**, samples **1/4**. No cap/provider
warnings occurred in either final run. No more full eight-case runs are allowed in this pass.

**[Completion audit](live-first-pass/completion.md)** · **[case roots](live-first-pass/gate4-review.md)** · **[judge screenshots](live-first-pass/judge-walk/README.md)**.
Final local ledger: **$1.058605 / 298 Tavily credits**. Owner dashboard checkpoint: **$1.05 / 288 credits**,
versus local **$1.048778 / 291** at that time; cent agreement, unresolved three-credit difference.
Final mock checks: **247 passed, 2 skipped**, eval **8/8**, presentation checks/build clean.
Recorded run **20261022-181611-a9d0b5**, full-tray capped replay, public unseen PDF and local smoke verified.
Reviewed checklists/answer-key expectations unchanged. **Do not deploy on Oct 22:** remaining accuracy and fix limitations are below. No cloud resources were touched.
Earlier sections are dated checkpoints; the completion audit supersedes their pending-work statements.

## Setup and baseline

- Started from `master` at `9568d1c`; working branch `live/first-pass`.
- Kyle approved leaving the four existing untracked planning/patch files untouched.
- Actual environment: Linux/bash, Python 3.12.3 in the existing `.venv`, Node 24.11.0, npm 11.6.1.
- Installed `api/requirements.txt`, pytest and respx (already satisfied); `npm install` and `npm run build` passed.
  Restored npm's five incidental lockfile metadata additions; no dependency change is included.
- Preserved the existing ignored `.env`, credentials, `.cache/` and `data/raw/`.
  Set live mode, model caps $3/run and $20/day, Tavily caps 60/item and 2,000/day, concurrency 2, thinking off.
  All inspected quality settings match their code defaults. Key presence reports true for both providers and admin;
  Kyle confirmed the provider keys are ready. No credential value was printed.
- The initial sandboxed pytest attempt stalled in Starlette TestClient/AnyIO thread dispatch. The same first test
  passed outside the restricted sandbox in 0.70 s; provider HTTP is intercepted by the test fixture.
- The first completed suite found one test assuming 999 credits exceeds any configured daily cap. With this pass's
  2,000-credit cap, the assertion was invalid. Changed only that test to use configured caps plus one.
  No production budget checks, prompts, quote gates or answer-key data were changed.
- After that correction: **153 passed, 2 skipped in 10.91 s**.

Mock baseline run: `20261021-065904-1e2dc4`, saved outside `runs/` at
`/tmp/speccheck-first-pass-mock-baseline.json`. The post-test-fix eval
`20261021-070234-ee2555` has the same panel and gate counts, saved at
`/tmp/speccheck-first-pass-mock-after-test-fix.json`.

| Panel | Mock baseline | Live |
| --- | --- | --- |
| Right calls | 8/8 | Not run |
| Planted problems caught | 6/6 | Not run |
| Clean packages wrongly flagged | 0/2 | Not run |
| Passing fixes | 2/5 | Not run |
| Claims retained | 48/48 (0% dropped) | Not run |
| Web values retained | 19/20 (5% dropped) | Not run |

Mock cost and latency are fixture measurements, not evidence of paid provider performance.

## Gate 1: documents

`fetch_docs.py` kept all 13 already-downloaded target files; no URL was fetched and there were no FAIL lines.
`check_pdfs.py` completed. A separate manifest-target check opened every required PDF with PyMuPDF:
none is encrypted and none has a page with fewer than 200 native text characters.

| Path under `data/raw/` | Pages | Native text characters |
| --- | ---: | ---: |
| `specs/cps_07_84_00.pdf` | 5 | 12,412 |
| `specs/cps_26_51_00.pdf` | 23 | 61,750 |
| `c01/sti_specseal_lci_tds_2025.pdf` | 3 | 9,407 |
| `c02/3m_c-aj-2738.pdf` | 1 | 3,839 |
| `c03/3m_ic15wb_2005.pdf` | 4 | 7,563 |
| `c04/hilti_w-l-2078.pdf` | 2 | 2,738 |
| `c05/lithonia_blt_2x4_2024-07.pdf` | 11 | 41,218 |
| `c06/lithonia_ldn6_2017-10.pdf` | 4 | 12,693 |
| `c07/lithonia_2tl4_2022-11.pdf` | 3 | 8,984 |
| `c08/lithonia_lqm_2019-09.pdf` | 2 | 4,436 |
| `samples/s1/3m_ic15wb_rev_b.pdf` | 2 | 10,700 |
| `samples/s3/lithonia_2blt4_adp_2019-07.pdf` | 7 | 29,926 |
| `samples/s4/hilti_fs-one_max_tds.pdf` | 1 | 2,328 |

The broad PDF checker also saw pre-existing uploads: three synthetic OCR PDFs without text, two synthetic
smoke PDFs with 127 text characters each, and their `case.json` metadata (reported as NOT A PDF).
These are outside the required manifest and do not indicate missing or scanned target documents.
Table detection has low fill rates on the old 3M sheet (9/389 cells, 2%) and the firestopping spec
(22/201 cells, 11%); native text is readable, but table detection is not evidence of accurate model extraction.

## Spend ledger

| Checkpoint | Token Factory USD | Tavily credits |
| --- | ---: | ---: |
| Before setup | 0 | 0 |
| After mock baseline and document checks | 0 | 0 |
| After test correction and mock re-eval | 0 | 0 |
| Model spike baseline | 0.000087 | 0 |
| Native tool spike | 0.000226 | 0 |
| Tavily baseline (three fresh searches; Extract/Map cached) | 0.000226 | 3 |
| Fresh host extraction and bounded Map | 0.000226 | 6 |
| Both checklist drafts | 0.013187 | 6 |
| First c03 live pass | 0.018874 | 11 |

Before the first provider call `.cache/budget/2026-10-21.json` did not exist.
At the first c03 checkpoint it recorded `{"usd": 0.018874, "credits": 11.0}`.
This is the local ledger, not console billing verification.
Pass ceilings remain $20 and 2,000 credits across the entire pass.

## Reproduce phases 0–1

```bash
.venv/bin/python -m pip install -r api/requirements.txt pytest respx
(cd web && npm install && npm run build)
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/speccheck-first-pass-mock-baseline.json
.venv/bin/python scripts/fetch_docs.py
.venv/bin/python scripts/check_pdfs.py
```

Use an unrestricted local shell for pytest in this environment. Tesseract is not installed here.
Deployment and cloud resources remain untouched.

## Phase 2: provider spikes

The first real model spike ran on 2026-10-21. The account listed both configured model IDs exactly as configured.
Its five visible Nemotron IDs, verbatim:

```text
nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
nvidia/Nemotron-3-Ultra-550b-a55b
nvidia/Nemotron-3.5-Super-VL
nvidia/Nemotron-3_5-Lightning
nvidia/nemotron-3-super-120b-a12b
```

Both reads returned schema-valid `{"product":"Firestop sealant","f_rating_hours":2.0,"standard":"ASTM E814"}`.
Both accepted `reasoning_effort="none"` and `chat_template_kwargs={"enable_thinking":false}` together,
without a rejected-field retry, and reported zero reasoning tokens. Acceptance does not isolate which field
caused the behavior. `json_schema` worked directly; `json_object` has not been tested live.

| Model | Input/output tokens | Format | Latency | Computed USD |
| --- | --- | --- | ---: | ---: |
| Nano | 136 / 37 | `json_schema` | 779 ms | 0.000017 |
| Super | 136 / 32 | `json_schema` | 1,053 ms | 0.000070 |

The complete console output and credential-free request/response records are in
[model-baseline.txt](live-first-pass/model-baseline.txt) and
[model-baseline-http.jsonl](live-first-pass/model-baseline-http.jsonl).
No 429 was observed in this spike. Model defaults and quality settings remain unchanged.

Added `spike_models.py --tools`: one native `chat_tools("investigate", ...)` call with a synthetic
`lookup(model_number: string)` tool, reporting presence/count, actual finish reason, JSON parsing,
multiple calls, reasoning tokens, latency and cost. Usage now retains the provider's tool-call finish reason,
including on cache hits; it is not added to assistant messages. Existing cache entries without the new field
remain readable and report no finish reason rather than an invented one.

Validation: 158 passed, 2 skipped in 15.91 s; mock run `20261021-071239-431799` remains 8/8 with
48/48 claims and 19/20 web values retained. Its comparison output is `/tmp/speccheck-first-pass-mock-tools.json`.

### Native tool result

The live `--yes --tools` run reused the two structured reads and made one fresh Super tool call:

```text
tool_calls=True  count=1  finish_reason=tool_calls  arguments_json=True  multiple_calls=False  reasoning_tokens=0  thinking=off  latency=1116 ms  cost=$0.000139  cached=False
```

The function was `lookup` and its arguments parsed as `{"model_number":"SPK-100"}`.
The request contained native tools and no `response_format`. Both no-think fields were accepted without retries.
Actual input/output usage was 372/30 tokens. See [model-tools.txt](live-first-pass/model-tools.txt) and
[model-tools-http.jsonl](live-first-pass/model-tools-http.jsonl).

### Tavily and direct HTTP

The first `spike_tavily.py` execution made three fresh basic Search requests, all HTTP 200, costing three
locally counted credits. Its original three-target Extract and Map responses were already cached before
this session, so they are not presented as fresh provider proof. Console: [tavily-baseline.txt](live-first-pass/tavily-baseline.txt).

A fresh five-URL basic extraction then returned four readable sources in 1,751 ms end to end (including the
failed URL's direct fallback). The HTTP API response reported `usage.credits=1`, matching the wrapper's count.
A fresh Map of `https://insights.acuitybrands.com/product-updates-blog`, limit 20/depth 1, returned 20 links;
`usage.credits=2` also matched the code. `include_usage=true` was requested for these two session probes;
the production provider and its quality settings were not changed.

| URL / host target | Fresh Tavily text | Direct httpx |
| --- | ---: | --- |
| `hilti.ca/media-canonical/ASSET_DOC_LOC_4226707_APC_RAW` | Failed: 404 | Redirect then 404 HTML |
| `files-ask.hilti.com/original/vm/vm8lukxnls.pdf` | 2,315 chars; FS-ONE, ASTM | 200 PDF |
| `insights.acuitybrands.com/.../discontinuation-notice-lithonia-lighting-tl-recessed-luminaire-2` | 19,301 chars; TL notice | 200 HTML |
| `hdsupplysolutions.com/.../324751_Specification-PDF.pdf` | 4,389 chars; LQM, 0.62 | 200 PDF |
| `img.acuitybrands.com/public-assets/catalog/999297/contractor-select-lqm.pdf` | 4,836 chars; LQM, 0.62 | 403 Cloudflare challenge |

The old Hilti asset is a dead URL; the actual sample's Hilti PDF works through both retrieval paths.
The fresh TL notice still states: “As of **June 30th, 2024**, the TL family will be discontinued.”
No observed evidence here contradicts that answer-key status. The literal keyword `June 30, 2024` did not
match because the source includes `30th` and Markdown emphasis; its date has not changed.

Exact URLs, response lengths/hashes, HTTP outcomes and that status quote are in
[host-report.json](live-first-pass/host-report.json). Redacted requests, provider response summaries,
credit usage and request IDs are in [tavily-http-summary.json](live-first-pass/tavily-http-summary.json).
Full third-party pages are kept in the ignored cache/session files, not copied into these notes.

### Billing limits of this evidence

Tavily `/usage` reported five pre-existing credits used before this pass's Tavily requests. It still reported
five immediately afterwards and on a later no-cache read at 07:19:32 UTC, despite fresh responses reporting
credits. Its account fields report Researcher / 1,000-credit plan, unlike the owner-provided 9,000-credit
balance. The cause of the unchanged counter is unknown; do not call this a zero-credit live run.
See the three `tavily-usage-*.json` records in this evidence folder. Use the conservative six-credit local
ledger for the pass ceiling while reconciliation is pending. No account plan or billing setting was changed.

Token Factory spend is computed from returned token usage, not yet compared with Kyle's console.
Configured Nano/Super rates match the [current Nebius model page](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference).
Neither provider produced a 429 in these spikes; no load or concurrency stress test is claimed.

### Reproduce Gate 2

```bash
.venv/bin/python scripts/spike_models.py --yes
.venv/bin/python scripts/spike_models.py --yes --tools
printf 'y\n' | .venv/bin/python scripts/spike_tavily.py
```

The session recorder captured the wire requests without authorization headers and redacted any known key
before saving or printing output. Re-runs can hit cache; inspect per-call `cached` fields and fresh HTTP
records before calling them new provider evidence. To repeat the additional host probe, pass the five exact
URLs in `host-report.json` to `api.providers.tavily.extract`, and call `tavily.map` on the blog URL above.
Both wrappers enforce the configured spend caps. The direct comparison used `BROWSER_HEADERS`, redirects
enabled, and a 30-second httpx timeout.

Gate 2: Super schema-valid JSON, native tools and fresh manufacturer extraction all work. Kyle accepted it
and authorized Phase 3. Billing counter reconciliation and the stated account allowance remain open.

## Phase 3: checklist review, not approved

At Kyle's request, `git push -u origin live/first-pass` succeeded before drafting, publishing commits through
`00fcab4` and configuring the upstream. Push this branch after every subsequent gate. Existing untracked
planning files remain untouched and outside every commit.

`scripts/draft_requirements.py` made two fresh Super calls, both schema-valid with thinking off and zero
reasoning tokens. It wrote only `data/requirements/07_84_00.draft.json` and
`data/requirements/26_51_00.draft.json`. Both have `reviewed_at: null`; neither reviewed filename exists.
The source PDF hashes match the provenance in both drafts.

| Section | Draft rows | Added vs fixture | Changed | Missing | Rows needing external/paperwork/site evidence |
| --- | ---: | ---: | ---: | ---: | ---: |
| 07 84 00 | 6 | 4 | 2 | 1 | 1 |
| 26 51 00 | 50 | 47 | 3 | 1 | 12 |

“Changed” includes filled paragraph references, role restrictions and literal unit changes; it does not mean
every original threshold changed. Matching uses property names, assigning the first luminaire warranty to
the fixture warranty and leaving the additional scoped warranty rows as additions. Renamed dimming appears
as added L25 plus missing L51 so the naming change is visible.

The [review tables](live-first-pass/checklist-review.md) contain every draft row plus missing fixture rows,
with paragraph, property, operator, value, unit, severity, applicability, source checks and a blank decision
column. F01–F06 and L01–L50 preserve draft order; F07/L51 are the missing fixture rows. Kyle will mark
keep/edit/delete. No row has been silently corrected or removed to match the answer key.

Observed draft errors include a firestopping warranty not required by its cited paragraph, null numeric
comparison targets, loss of the T=F relationship, a numeric VOC limit not stated in the PDF, an L70 life
misnamed `t_rating_hr`, incorrect lighting paragraph references, subtype requirements assigned to all
product-data sheets, installation requirements and separate test/warranty paperwork. The comparison also
flags string `eq` values that the current numeric comparator cannot evaluate and found `exists` rows whose
missing-claim failures conflicted with the unconfirmed-evidence rule. The latter is fixed below; the other
draft issues still require Kyle's row decisions before use.

| Draft | Input/output tokens | Latency | Computed USD |
| --- | --- | ---: | ---: |
| Firestopping | 4,955 / 688 | 13,765 ms | 0.002106 |
| Lighting | 17,996 / 6,062 | 30,504 ms | 0.010855 |

Lighting supplied 61,820 text characters; the existing 60,000-character prompt bound applied. Defaults were
not changed. Source control dates still match the project metadata, so these draft problems do not establish
a changed specification. No fixture or expected result has been edited.

Console evidence: [checklist-drafts.txt](live-first-pass/checklist-drafts.txt). Credential-free request and
response summaries: [checklist-drafts-http.json](live-first-pass/checklist-drafts-http.json); prompt text is
represented by length/hash so the full source PDFs are not copied into Git.

Kyle specifically requested reconciliation of the local Tavily ledger against the **Tavily dashboard after
c03 and c07** in Phase 4. Record each run's local checkpoint, obtain the dashboard's observed total and
timestamp, subtract the prior account usage, and document any remaining difference here. The API `/usage`
observations above do not substitute for that dashboard check. Neither case has run live yet.

Post-draft mock check `20261021-073404-ea001f` remains 8/8, with 6/6 problems, 0/2 false alarms,
2/5 passing fixes, 48/48 claims and 19/20 web values retained. Output is saved outside `runs/` at
`/tmp/speccheck-first-pass-mock-drafts.json`. Draft generation itself changed no production code; the suite
at that checkpoint was 158 passed / 2 skipped. Draft schema/provenance and absence of reviewed filenames
were checked.

### Missing presence claims stay unconfirmed

While Gate 3 awaits Kyle's decisions, fixed the general `exists` branch in `spec_check.check`, shared by
normal submittals and fix candidates. Previously it treated the absence of an extracted claim as proof
the package was missing that information. It now reuses the existing missing-claim path; no quote gate,
prompt, fixture, expected result or draft row was changed.

Reproduction: one synthetic `input_watts` requirement, `operator=exists`, no claims:

| Behavior | Before | After |
| --- | --- | --- |
| Finding | `fail`, major | `unverified`, minor |
| Decision | `send_back` | `approve_with_note` |

A present claim still passes the presence check. The new regression also checks that even a critical
requirement cannot trigger a send-back from absent evidence. Full suite: **159 passed, 2 skipped in
12.87 s**. Mock eval `20261021-073852-503024` remains 8/8 with the same panel and quote-gate counts;
saved at `/tmp/speccheck-first-pass-mock-exists.json`. Ledger remains $0.013187 and 6 credits.
Neither reviewed checklist exists, and c03/c07 have not run live.

### Gate 3 signed off by Kyle

On 2026-10-21 Kyle supplied explicit keep/edit/delete decisions checked against the CPS text. Saved
`data/requirements/07_84_00.json` and `data/requirements/26_51_00.json` with `reviewed_at=2026-10-21`.
Only these approved properties are used live:

| Section | Approved rows | Properties |
| --- | --- | --- |
| 07 84 00 | F01, F02, F04, F07 | VOC ≤250 g/L; ASTM G21 rating 0; T=F; ASTM E814/E119 or UL 1479 |
| 26 51 00 | L01, L03, L14, L18, L51 | L70 ≥50,000 h; warranty ≥5 yr; DLC Standard/Premium; MacAdam ≤3 steps; dimming ≤5% |

All other proposed rows are excluded from the reviewed checklists. The original `.draft.json` files remain
unchanged as drafting evidence; the review table's Decision column records Kyle's choices. VOC text explicitly
attributes 250 g/L to the Rule 1168 architectural-sealant limit supplied by Kyle, rather than claiming that
the CPS PDF prints the number. CRI is excluded because the cited requirement is scoped to screw-in lamps.
Source title/name metadata was completed without changing source URLs, hashes or draft timestamps.

Before Phase 4, at Kyle's request, `any_of` and `contains` now normalize case, Unicode forms, whitespace,
hyphens and punctuation on both operands. Empty punctuation-only strings cannot pass. This comparison
normalization does not change the quote gate or the approved rows.

| Synthetic comparison | Previous lowercase-only check | Normalized check |
| --- | --- | --- |
| `ASTM E 814` vs `astm e814` | false | true |
| `UL-1479` vs `ul 1479` | false | true |

Tests include formatting variants in both operands, different standard numbers that must still fail,
punctuation-only values, and missing G21/L70/MacAdam properties remaining unverified notes. Full suite:
**173 passed, 2 skipped in 11.48 s**. Mock eval `20261021-074851-a10d76` remains 8/8 with 48/48 claims
and 19/20 web values kept; saved at `/tmp/speccheck-first-pass-mock-reviewed.json`. Ledger is unchanged
at $0.013187 and 6 credits. README now lists product-type scoping under “What's next.”

Kyle's additional answer-key instruction: if c01, c05 or c08 receives `approve_with_note` solely because
G21, L70 or MacAdam is not stated, report it as an **answer-key question** and retain the approved row.
Do not change expectations or drop a requirement to improve the panel. Dashboard reconciliation after
c03/c07 remains required; the available browser profile has no Tavily sign-in, so dashboard figures will
need Kyle's reading or his explicit browser sign-in choice.

## Phase 4: live cases, smallest first

### c03 baseline — 20261021-075141-f8c59e

The first actual case ran after Gate 3 and its push. No reviewed criterion or answer-key expectation was
changed afterwards.

| Expected | Actual | Problems caught | Passing fixes | Time | Model USD | Tavily credits | Model + web equivalent |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| send_back / currency | approve_with_note / currency_note | 0/1 | 0/1 | 23.838 s | 0.005687 | 5 | 0.045687 |

Quote counters: **0/4 claims kept; 13/13 web values kept**. No warnings, cap hits, provider errors or 429s
were observed in the item's result, event trace or recorded wire calls. Investigation did not run. The
result therefore exposes an extraction miss rather than a swallowed provider/budget failure.

Of the four extracted claims, G21 and T rating were null without quotes and were correctly dropped.
The standard-list quote changed the source's words and was correctly dropped. The valid VOC quote was
returned as the literal characters `VOC:\\n0`; the PDF contains `VOC:` followed by a real newline and `0`.
Dropping that last claim removed the submitted side of the currency comparison. The later verify call
returned quoted values using its own property labels against an empty submitted-claims list; no submitted
value could be compared. Because no send-back was produced, fix discovery did not run.

The retrieved manufacturer document is
[3M's current IC 15WB+ sheet](https://multimedia.3m.com/mws/media/207329O/3m-fire-barrier-sealant-ic-15wb-technical-data-sheet.pdf).
Its footer says “© 3M 2018” and its VOC value is “<2 g/L.” That date predates the October 2026 answer key;
the expected old/current value difference is supported. This does not establish a revision since the key
was written. No expected value or manufacturer URL was added to a prompt.

Baseline console and panel: [c03-baseline.txt](live-first-pass/c03-baseline.txt) and
[c03-baseline-scores.json](live-first-pass/c03-baseline-scores.json). Full item/trace remain in the ignored
`runs/20261021-075141-f8c59e/`.

### General extraction corrections

The claims prompt now explicitly requires one short contiguous, verbatim quote, omits unstated/null claims,
and asks for one array entry per distinct standard/certification identifier. Previously it requested only
“a short supporting quote.” No checklist, expected result or task quality setting changed.

The shared quote normalizer now treats literal escaped newline/tab/carriage-return sequences as whitespace
on both operands. It removes ™/® before Unicode normalization, so ™ cannot expand into an unintended
`TM` token. Quotes that normalize to empty are rejected. Words and numbers must still occur contiguously
on the cited page: a paraphrased opening and changed numeric values remain rejected.

The tests cover both directions of escaped whitespace, trademarks/ligatures, changed values, paraphrased
words and empty normalized quotes. Full suite: **174 passed, 2 skipped in 11.41 s**; mock eval
`20261021-075757-cd9964` remains 8/8, claims 48/48, web values 19/20. Its comparison score is saved at
`/tmp/speccheck-first-pass-mock-quote-final.json`. Only c03 is being rerun live to measure the correction.

### Tavily dashboard checkpoint supplied by Kyle

Kyle reported **15 / 9,000** used/available-plan credits during the c03 diagnosis. This is recorded in
[tavily-dashboard-c03.json](live-first-pass/tavily-dashboard-c03.json); exact dashboard observation time
and account/per-key scope were not supplied. At that checkpoint the local pass ledger was **11 credits**.
The earlier API `/usage` baseline was 5 on a different reported plan, so it is not a confirmed dashboard
baseline. If compared arithmetically, 15 minus 5 is 10, one below the local 11, but that is not yet a
reconciled billing result. Request the updated dashboard reading after c03/c07 and preserve this discrepancy
rather than treating the stale API counter as authoritative.


### c03 correction measurements (before → after)

| Run | Change measured | Call / problem | Passing fix | Time | Fresh pass ledger after run |
| --- | --- | --- | --- | ---: | --- |
| `20261021-075808-b7f23e` | Verbatim/omit-null/list prompt + escaped-whitespace quote matcher | send_back / currency **plus false spec failure** | invalid: second fix group hit step credit cap | 68.086 s | $0.036807 / 23 credits |
| `20261021-080506-f3e537` | Recognize parenthesized categorical identifiers; explicit value/quote prompt | send_back / currency only, but wrong numeric quote still accepted | 0/1 | 22.679 s | $0.049276 / 23 credits |
| `20261021-080829-94b9d6` | Numeric quote gate + source-first prompt | approve_with_note / currency_note: **miss**, bad value correctly dropped | 0/1 | 4.044 s | $0.052735 / 23 credits |
| `20261021-081115-f416b6` | One validation-feedback retry | send_back / currency only, exact numeric quote accepted | 0/1 | 11.835 s | $0.067518 / 23 credits |

The first quote-corrected run's extra major finding was caused by `ASTM E 814 (UL 1479)` remaining one
array item despite the prompt requesting separate identifiers. `any_of` now recognizes the outside and
inside of parentheses as identifiers while retaining the full item. It matches either identifier and
still rejects different standard numbers; no case ID or expected result controls this logic. The extra
spec group consumed the shared fix allowance and produced a recorded warning: `Tavily credit cap for
this step reached`. That run is **invalid for fix assessment**. Later runs have no warnings, provider
errors, cap hits or 429s; all web calls were cached, so they charged zero additional Tavily credits.

The verify prompt originally said “Use the same property names. Only use values stated in the sources.”
The first revision required the quote to contain the same value/bound; Super nevertheless paired value
`<2` with quote `contains <250 g/L VOC contents ...`. The next source-first wording also returned that
pair. The numeric gate now rejects numeric values unless the quote includes the same number and bound
(with comma/decimal/fraction formatting supported). It supplements the unchanged requirement that the
quote occur on a fetched page. It does not prove units or the semantic meaning of every property.
The source-first run honestly lost the currency call when the bad pair was dropped.

The final general correction makes **at most one** additional read when numeric quote validation fails.
Its feedback identifies rejected property names, includes the model's previous output and the same fetched
sources, and requests a corrected quote or omission. It contains no answer-key values. Every retry is
charged and recorded separately; the same quote and numeric gates validate its output. The final main
comparison quotes `VOC Less H2O and Exempt Solvents: <2 g/L` from the manufacturer PDF. A fix-candidate
read also corrected its mismatched quote on retry. Tests cover both correction and a retry that remains
unsupported and is still dropped.

Final c03 quote counters (including fix candidates): **8/16 claims kept, 7/8 web values kept**. The main
submission kept 2/4 claims. Neither scripted verification nor its candidates invoked the Investigator.
No candidate passes: all three lack quoted ASTM G21 evidence, and the manufacturer candidate also lost
its standards claim at the quote gate. No requirement was removed. One candidate reader also interpreted
a generic three-hour firestop statement as T rating; this does not establish a T rating and remains an
extraction-semantic limitation, not a reason to approve that candidate.

Final verification: **188 passed, 2 skipped in 11.21 s**, mock eval `20261021-081053-cc0784` remains **8/8**,
6/6 planted problems, 0/2 clean false alarms, 2/5 passing fixes, claims 48/48 and web values 19/20. No web
files changed. Full eight-case live runs used so far: **0**. Per-item model costs include cached token-cost
estimates; only the daily ledger is the actual fresh spend for the pass. Prompt/matcher before/after
measurements above must not be presented as a fresh, independent all-eight baseline.


### c07 baseline and source-selection correction

Baseline `20261021-081226-6aa7c0`: **0/1 right call, 0/1 status problem, 0/1 passing fix**, 39.699 s,
claims 1/5, web values 0/0. The result had no provider/budget warning, but the Investigator outcome was
`capped` after six tool calls. Treat it as invalid for an uncapped status assessment. The extracted
identity was `Acuity Brands Lighting, Inc. / 2TL-2X4`; the four dropped claims were unstated/empty,
not real claims lost to typography. Triage's second/third-page labels were inaccurate, but all pages
were included because only `other` pages are excluded. Triage did not cause the status miss.

The status search actually returned the correct manufacturer discontinuation notice. Manufacturer-first
ranking then took the first three sources, all from the earlier document search, leaving the notice out.
The Investigator received no useful fetched status evidence and spent its six calls repeating searches
and Cloudflare-blocked extracts. No key, case-specific URL or expected status was injected into a prompt.
Source selection now reserves one of the three slots for a manufacturer status notice when search found
one. It retains the normal source-tier order and deduplicates URLs; a third-party notice cannot claim
that manufacturer slot. Test covers duplicates, empty input and a notice beyond the first three results.

Retry `20261021-081707-7f718a`: **1/1 right call, 1/1 status problem, 0/1 passing fix**, 54.134 s,
claims 1/5, web values 0/0. Scripted verify quoted “As of **June 30th, 2024**, the TL family will be
discontinued.” from the manufacturer notice. This predates the key; no changed-world exception applies.
The main check needed no Investigator. However, this run is **invalid for fix assessment**: Tavily's
replacement search returned CP2102N, LM35, RP2040, BME280 and UniFi data sheets for the actual query
`Acuity Brands Lighting, Inc. current LED troffer data sheet`. Verifying unrelated candidates exhausted
the shared fix credit scope; the candidate Investigator trace records the cap. The source-selection
correction fixed status retrieval, not replacement relevance.

Current-product replacement searches now pass the known manufacturer domains to Tavily. Spec/listing
replacement searches retain their broader scope. Candidates with no quoted product properties stop
before web verification or investigation, since they cannot establish a passing replacement. An attempted
host-only filter was rejected by the mock checks because valid manufacturer sheets are also hosted by
distributors; it is absent from the final implementation. It made the mock fix panel 0/5 temporarily.
The retained implementation restores the mock panel to 8/8 calls, 6/6 problems, 0/2 false alarms and 2/5
passing fixes. Verification: **191 passed, 2 skipped in 12.16 s**, mock eval `20261021-082105-0b7d62`.

### Tavily usage reconciliation: captured responses vs ledger

Captured `include_usage` responses disagree with result-count credit estimates:

| Run | Original local debit | API-reported credits | Difference |
| --- | ---: | ---: | ---: |
| c03 baseline | 5 | 4 | -1 |
| c03 quote correction | 12 | 11 | -1 |
| c07 baseline | 9 | 10 | +1 |
| Total adjustment | 26 | 25 | -1 |

An extract with usable text reported zero; two failed extracts each reported one. Therefore “failed
extract URLs are free” was not a safe accounting assumption in these observed responses. Provider wrappers
now request `include_usage=true` and charge a nonnegative integer `usage.credits` when present, including
zero. Missing/invalid usage falls back to the existing documented credit estimates. Cache keys stay the
same and cached calls stay free. Tests cover reported zero, charged failure, reported search cost, cache
hits and fallback estimates.

[Historical correction audit](live-first-pass/tavily-credit-correction.json) preserves the per-request
reported charges and the original ledger. The correction was applied once: 32 → **31 credits** at unchanged
$0.076209 model spend. Original run results and score files were not rewritten. The subsequent c07 source
retry charged 13 credits under returned usage, bringing the ledger to **$0.091991 / 44 credits**. Kyle's
updated dashboard reading has been requested; **dashboard reconciliation remains pending**. The earlier
15/9,000 reading and the API's stale 5/1,000 counter are not sufficient to assert an account reconciliation.


### Scoped-fix reruns

* c03 `20261021-082125-1f89d8`: 1/1 call and currency problem, 0/1 passing fix, 44.742 s, 10 fresh web
  credits; claims 7/12, web 7/7. No warnings or Investigator run. Two candidates had some quoted data;
  both still lacked G21, and other candidate values/currency could not all be confirmed. Ledger after:
  **$0.101116 / 54 credits**.
* c07 `20261021-082231-46f08f`: 1/1 call and status problem, 0/1 passing fix, 60.070 s, 6 fresh web
  credits; claims 1/5, web 0/0. The replacement search returned lighting products. Two candidate
  investigators each used six tool calls and the combined outcome was capped, making fix assessment
  invalid. Captured extracts include mangled binary content for `wrtl.pdf` and raw PDF syntax for
  `vtl-1x4.pdf`; other Acuity URLs returned no text and direct 403s. No quoted properties were extracted
  from the remaining CPX product page, so it correctly stopped before verification. Ledger after:
  **$0.121112 / 60 credits**.

Following the invalid-run rule, a c07-only retry uses `INVESTIGATE_MAX_STEPS=12` in the process environment.
The `.env` defaults remain unchanged; this override must not be described as the default-quality baseline.
Full eight-case live runs used so far remain **0**.


c07 allowance retry `20261021-082700-29a000` used 12 steps per investigation for that command only.
It finished **uncapped**, combined outcome `not_found`, 17 steps across two candidate investigations.
Both called `finish(found=true)`, but code rejected one fabricated revision explanation and one finish
that cited a product URL never successfully extracted. This is a valid no-fix result, not a swallowed
provider/cap failure: 1/1 call and status problem, 0/1 passing fix, 69.404 s, claims 1/5, web 0/0.
Ledger: **$0.161701 / 67 credits**. The first full eight-case baseline then started with
`investigate_max_steps=6`, `search_depth=basic`, `thinking=off`, concurrency 2 and the unchanged reviewed
checklists. No full-run result is claimed until that run finishes.


### First full live baseline — 20261021-082858-431567

All quality defaults were unchanged. This is full eight-case live run **1 of at most 4**.

| Panel | Mock baseline | First full live baseline |
| --- | ---: | ---: |
| Right calls | 8/8 | **3/8** |
| Planted problems caught | 6/6 | **3/6** |
| Clean items falsely flagged | 0/2 | **1/2** |
| Passing fixes | 2/5 | **0/5** |
| Mean time per item | 0.1 s (mock) | **36.770 s**, mixed cache |
| Reported model + web equivalent per item | $0.085867 (mock estimate) | **$0.063096** |
| Claims kept | 48/48 | **24/36** (33.3% dropped) |
| Web values kept | 19/20 | **15/24** (37.5% dropped) |

Use [full-baseline-scores.json](live-first-pass/full-baseline-scores.json) for the exact panel/row values;
[full-baseline-diagnosis.json](live-first-pass/full-baseline-diagnosis.json) preserves claims, comparisons,
investigations and warnings. The baseline used cached c03/c07 calls; c07 took only 113 ms. Its latency is
not a fresh-service benchmark. Fresh ledger delta for this run: **$0.087380 and 47 credits**, bringing the
pass to **$0.249081 and 114 credits**. Item model costs include cached token estimates. No captured provider
request raised an error; no 429 or monetary/day/item-cap warning appeared. Investigators for c05, c06 and
c07 were capped; their affected web/fix assessments are invalid until an uncapped retry.

| Case | Baseline outcome | Stage and evidence for each miss |
| --- | --- | --- |
| c01 | approve_with_note, expected approve | Verify/report: all spec rows passed; revision codes `ZSFOD5062 25171` and `ZSFOD5062 22326` differed. Code treated any difference as “newer” without establishing chronology. No G21 answer-key exception is involved. |
| c02 | approve_with_note, expected spec send_back | Extract: only T=0 was requested/read; the extraction property set omitted the F reference after the reviewed checklist removed the standalone F requirement. The local drawing explicitly states `F Rating — 2 Hr` and `T Rating — 0 Hr`. Search identity also omitted the listed system number and found a generic product certificate. Claims 1/1, web 0/2. |
| c03 | correct currency send_back, no passing fix | Fix: candidates lack complete quoted checklist evidence, including G21. Claims 9/15 and web 9/9 include candidates. No cap or provider error. |
| c04 | approve_with_note, expected validity send_back | Extract: the model omitted the penetrating-item list despite receiving its notes page. The PDF's heading says `PLASTIC PIPE THROUGH GYPSUM WALL ASSEMBLY`; page 2 enumerates PVC, CPVC, ABS, FRPP, PVDF and PEX. With no kept coverage claim, code correctly returned unverified rather than a failure. Claims 1/2, web 1/1. |
| c05 | false spec send_back | Spec check: full phrase `DesignLights Consortium® (DLC) Premium qualified product` failed exact categorical comparison. Extract also selected 10% non-configurable dimming while the same sheet has 1% driver options. It mislabeled L80/60,000 as L70. Warranty is at character 6,748 on an 8,650-character page and was cut by the 6,000-character excerpt. Verify investigator capped; its no-web-confirmation assessment is invalid. Claims 4/4, web 0/4. |
| c06 | approve_with_note, expected currency send_back | Extract/verify: only L70 and warranty survived; narrowing extraction to checklist properties left out performance values needed for revision comparison. Both attempted web values were dropped. The Investigator then capped. Claims 2/3, web 0/2. |
| c07 | correct status send_back, no passing fix | Main status has the exact manufacturer notice. The default six-step candidate loops replayed capped results; use the separately recorded 12-step uncapped retry for fix diagnosis, not an unsupported passing-fix claim. Claims 1/5, web 0/0. |
| c08 | correct approve_with_note | Warranty matched and document revisions differ. L70/MacAdam are additionally unverified, but they are not the sole cause of this note, so Kyle's special answer-key question is not triggered. Claims 1/1, web 1/1. |

The baseline's main scripted checks failed to confirm quoted current evidence on c02, c04, c05 and c06
and invoked the Investigator: **4 items**. It resolved a quoted document/revision on **2** (c02, c04),
while c05/c06 capped. Across main and candidate investigations, **3 items** had a capped combined outcome
(c05, c06, c07). A found document is not a correct substantive call: c02 still missed T versus F, and
c04 still missed pipe compatibility. No passing replacement was produced on any of the five send-backs.

### General baseline corrections under verification

Extraction now includes referenced properties (not merely the requirement's left operand), and the
existing vocabulary of performance properties used for currency comparisons. Both the runner and fix
candidate path use the same property set. Property labels explain meanings without supplying expected
values. Prompt changes require reading notes/tables, preserving system identity and distinguishing test
metrics, and retaining separate configuration alternatives. Triage now explicitly recognizes continuation
pages. No case IDs, answer-key values or manufacturer-specific branches were added.

Categorical checks now match a complete identifier/category phrase inside descriptive text, normalizing
case and separators while enforcing boundaries. `DLC Premium` can match the longer qualified-product
phrase; `UL 1479` cannot match `UL 14790` or `UL 1479.1`. Conflicting numeric alternatives are unverified,
not arbitrarily selected as pass/fail; all-pass and all-fail alternatives retain those outcomes. Range/
“or” strings are not reduced to their first number. F/T equality cannot compare unpaired alternatives.

The claim gate additionally requires the requested lumen-maintenance label/percentage to occur in its
quote and requires an explicit F/T rating label for those claims. This prevents an L80 claim becoming
L70, or a generic fire-resistance duration becoming T. Metric numbers are read from property names;
there are no case-specific values. Quote matching itself is unchanged. The mock claim gate consequently
keeps 47/48 rather than 48/48; calls and passing fixes stay 8/8 and 2/5.

Revision-only wording now states that labels differ and their age order is unconfirmed. The report
receives each coded verdict/severity and is instructed to distinguish missing evidence from a failed
requirement and documentation differences from proven safety/code violations. It still cannot change
the decision. Verification: **206 passed, 2 skipped in 11.42 s**, mock eval `20261021-084624-89afb8`.

Kyle has been asked whether the first-page excerpt may increase from 6,000 to 12,000 characters after
the saved default-quality baseline. Pending his answer, quality settings remain unchanged. Targeted
c02/c04 retries run first. Approved checklists and all answer-key expectations remain untouched.


### Listing and retrieval corrections: measured outcomes

`20261021-084706-627716` reran c02/c04: **2/2 calls and 2/2 planted problems**, no passing fixes.
c02 now quotes F=2 hr and T=0 hr and correctly fails their equality. c04 quotes the permitted plastic-pipe
list and correctly fails steel-pipe coverage. c04's web investigation still capped, so its web assessment
was invalid pending a longer retry. Claims 20/20 and web values 14/14 include candidate checks.
Ledger after this run: **$0.283279 / 138 credits**.

Raw PDF syntax from Tavily is now rejected as text. The free direct-PDF fallback is attempted; cached
corrupt responses are repaired individually without paid refetches or clearing `.cache/`. A single bounded
backfill batch tries other search results when the first sources are unreadable. Direct probes returned
403/text-html for the current LDN6 and WRTL PDFs: see
[acuity-direct-pdf-probe.json](live-first-pass/acuity-direct-pdf-probe.json). The Investigator's redundant
pre-cache credit reservation was removed: provider/WebClient caps still guard paid calls, while cached
reads work at zero remaining credit allowance. A test proves an extract+finish can succeed entirely from
cache under a zero-credit investigation scope.

The 12-step c04/c05/c06 retry `20261021-090608-c1f902` completed c04/c06 but c05 hit the 8,192-output-token
limit. Its error event and charged usage are preserved. The printed c04/c06 calls matched the key, but
manual review found **unreliable currency evidence**: c04 compared different partial standards claims under
the same property, and c06 compared the last of several submitted efficacy values with a 75–80 LPW launch
article. The same LPW quote was even labeled CRI=80. These are not valid grounds for declaring those
currency problems caught. Ledger after: **$0.355057 / 148 credits**.

Currency comparison now groups values by property and only compares an unambiguous value/unit on both
sides; it does not overwrite earlier claims or select one of conflicting alternatives. Conditional options
are excluded from general comparisons. CRI requires a CRI/color-rendering label, including compact `82CRI`
typography; an LPW quote cannot prove CRI. Only comparable submitted properties are sent to the web reader,
and having quoted but uncomparable values no longer suppresses the Investigator.

### Linked documents and c01

The legacy STI PDF is genuinely still available and prints `ZSFOD5062 22326` (direct HTTP 200), while
the manufacturer's live product page links a different CDN data sheet. This is a coexistence/discovery
issue, not evidence of a post-key revision. See the
[direct PDF probe](live-first-pass/sti-direct-pdf-probe.json) and
[HTML link probe](live-first-pass/sti-document-discovery-probe.json).

The shared free downloader now follows one data-sheet/PDF link, including extensionless PDS asset URLs,
from a public product page. Relative links resolve against that page and private/literal-local targets are
rejected using the existing public-URL validator. Successful resolution preserves the actual document URL
and the requested page URL; the fix path follows the resolved URL instead of attributing PDF quotes to the
HTML page. Resolved results are cached. No manufacturer/case-specific URL or filename was added to code.
The web reader receives this provenance and prefers the sheet linked by the current product page over a
standalone search hit.

Retry `20261021-093028-7e0c4b` correctly approved c01 after following that live link. c05 again exceeded
8,192 output tokens. Ledger: **$0.381328 / 151 credits**. The retry uses the normal 6,000-character input
excerpt; no pending input-quality decision was assumed.

### c05 output limits, evidence and remaining miss

| Run | Limits for this command | Result | Ledger after |
| --- | --- | --- | --- |
| `20261021-093410-e942f4` | 16,384 output tokens; 12 investigation steps | Complete but false spec send-back; partial DLC category and a driver option were treated as general facts | $0.423434 / 160 credits |
| `20261021-094619-39bd46` | 16,384 output tokens; 12 steps; option field added | Reply reached 16,384 tokens and was cut off; **invalid item**, not a quality miss | $0.443879 / 160 credits |
| `20261021-095653-618929` | 32,768 output tokens; 12 steps | Complete reply used 3,220 tokens; still false spec send-back; a candidate investigation capped | $0.490957 / 172 credits |
| `20261021-101307-dd95fb` | 32,768 output tokens; 12 steps; stronger claim gates | approve_with_note; **no spec failure, no cap/provider warning**, still a wrong call versus approve | $0.494373 / 172 credits |

The output-cap changes are disclosed retry settings, not the saved default-quality baseline. `max_output_tokens`
is now included in score tuning metadata. Error-only scoreboards show zero item cost/time because no complete
Result exists; **those zeros are not actual spend or latency**. The ledger includes the charged truncated replies,
and their wire usage/latency and error events remain in the redacted evidence.

A category value such as `Premium` can now be grounded by a full allowed identifier in its exact supporting
quote; unrelated “Premium” language cannot match another classification. The new optional `variant` field
preserves exact quoted model/driver qualifiers. Its phrase must itself occur in the supporting quote. Explicit
leading labels such as “Optional …:” or “Non-Configurable …:” are preserved even if the model omits the
field. Requirements with only option-specific values remain unverified until the configuration is confirmed.
This prevents a non-configurable 10% dimming option from becoming a failure for the entire family.

The numeric value/bound gate now also validates submitted claims, including numeric list entries. In one
actual c05 reply, the model attached a five-year warranty value to a copyright quote; that claim is now dropped.
The quote still has to appear on its own page, and the metric label checks remain in place. No source word,
number or requirement is fuzzed to get a pass.

The final c05 targeted run keeps 20/25 claims and 0/3 web values; the Investigator returns found, with no cap.
Its remaining notes are: no kept L70, warranty or DLC claim; dimming only confirmed for Non-Configurable BLT;
and a catalog asset date differing from the submitted revision. The catalog row says `Updated` 9/21/2026 for
BLT.pdf. This proves a catalog asset date, **not the printed PDF revision**; the linked PDF is blocked. It is
not evidence of a post-October-7 world change, and the key remains untouched. The missing L70 row is retained;
it is not the sole cause of this note, so Kyle's special G21/L70/MacAdam-only question is not automatically met.

### F04 applicability conflict — decision pending

An attempted change made missing F/T references unverified instead of skipping the conditional comparison.
It changed the mock eval to **7/8** and passing fixes to **1/5**, with **8 failed, 218 passed, 2 skipped** in
12.03 s. That conflicts with the instruction to keep the mock baseline green. The change was reverted;
the existing conditional behavior is retained pending Kyle's explicit decision. Both reviewed checklists and
all answer-key expectations remain unchanged. The open question is whether F04's “all” means all document
roles when both ratings are stated, or a missing-pair note for every applicable document. This is an unresolved
policy issue, not permission to silently remove the approved row or alter the key.

Current verification: **226 passed, 2 skipped in 12.01 s**; mock eval `20261021-101232-2b4a80` remains **8/8**,
6/6 problems, 0/2 false alarms, 2/5 passing fixes, claims 46/48 and web 19/20. The stricter numeric/metric gates
explain the changed mock retention count. No web files were changed. The second full run uses the disclosed
32,768-output/12-step retry settings; input excerpts, search depths, thinking and approved rows are unchanged.


### Full live run 2 — 2026-10-21

Run `20261021-101810-01e6fb`; scoreboard and per-item diagnosis are in
`docs/live-first-pass/full-after-fixes-{scores,diagnosis}.json` and `.txt`.
Reproduce: `MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=12 .venv/bin/python scripts/eval.py --out /tmp/speccheck-live-full-after-fixes.json`.

| Panel | Full run 1 (defaults) | Full run 2 (disclosed output/step limits) |
| --- | ---: | ---: |
| Right calls | 3/8 | 5/8 |
| Problems caught | 3/6 | 4/6 |
| Major false alarms on clean items | 1/2 | 0/2 |
| Passing fixes | 0/5 | 0/5 |
| Average time/item | 36.770 s | 126.255 s |
| Equivalent model + web cost/item | $0.063096 | $0.065856 |
| Claims retained | 24/36 | 144/173 (16.8% dropped) |
| Web values retained | 15/24 | 17/34 (50.0% dropped) |

The clean-item false-alarm metric counts major failures; c05's unnecessary note remains a wrong call.
Ledger after the full run: **$0.658762 / 213 credits**, a fresh charge of **$0.164389 / 41 credits**.
Per-item displayed costs include cached usage equivalents and are not fresh charges.

| Item | Call and diagnosis |
| --- | --- |
| c01 | Correct approve; following the product page's linked current data sheet removed the legacy-PDF revision note. |
| c02 | Correct send-back: quoted F=2 and T=0. The Investigator did not establish a current exact-system document; a generic certificate's revision is not exact-system evidence. |
| c03 | Correct currency send-back, no passing fix. The current read compared old 120°F continuous temperature with a current 180°F service range. Category code 90G9 was incorrectly read as a revision; metadata remains unreliable. Long latency came mainly from repeated direct HTTP timeouts, not paid model time. |
| c04 | Correct penetrant validity failure; plastic-pipe values were now kept. No passing fix. |
| c05 | Wrong approve_with_note instead of approve; L70/warranty/DLC extraction and driver selection remain unresolved. No major false failure. Missing L70 is not the sole note. |
| c06 | Wrong approve_with_note: current manufacturer PDF unreadable through basic Tavily (raw PDF syntax) and direct fetch (403). Multiple old wattage/efficacy options cannot be compared as one selected value. Investigator not_found. |
| c07 | Wrong approve_with_note: extracted dimensions/SKU made exact queries too narrow; the family discontinuation notice was missed. Investigator capped at 12 calls. This item is invalid for quality assessment until retried without that cap failure. |
| c08 | Correct approve_with_note; missing performance evidence and revision differences remain notes. |

No 429 or captured provider error occurred in this run. Existing swallowed-error paths did not all produce
warning events; they are being fixed with stage/reason-only warnings before the next live retry.
Follow-up changes under validation: a 15-second total direct-lookup timeout; cache failed linked-PDF probes;
use the supplied inbox label for a separate family-status query; constrain the web reader's property-name
schema to the submitted properties without forcing a single variant; give the Investigator a valid JSON
excerpt containing document body and tail, and explicit separate status-search instructions.

The advanced extraction probe (`advanced-pdf-probe.json`) cost **1 reported credit**, versus the old estimate
of 2. LDN6 remained unreadable; BLT-2x4.pdf returned readable text with L80, MacAdam and warranty statements.
That static file has not been established as the current linked BLT.pdf revision. Ledger after probe:
**$0.658762 / 214 credits**. Default extraction depth was not changed.

Tavily dashboard reconciliation is still pending. Kyle's **15/9000** reading is retained as the dashboard
observation; its timestamp and account/key scope are unknown. The local ledger is now 214, after subsequent
runs, so subtracting 15 would not establish a reconciled delta. No dashboard confirmation is claimed.


### Status/fetch retry — 2026-10-21

Run `20261021-110250-710e60`, `status-fetch-retry-{scores,diagnosis}.json`:
**2/3 calls**, 2/3 problems, 0/3 passing fixes. c03 retained the currency send-back in **79.454 s**;
c02 retained the F/T failure in **64.009 s**. These are mixed-cache retries, not a controlled cold latency comparison.
c07 remained approve_with_note in **57.428 s**, with an explicit 12-call-cap warning in both the result and events.
Claims 81/90; web values 8/17. Ledger after: **$0.721930 / 230 credits**; fresh charge **$0.063168 / 16 credits**.

The supplied inbox-label search found the correct TL manufacturer notice. An initial diagnosis blamed
source selection. Inspecting the complete captured model request disproved that: the notice was included,
with the discontinuation sentence at character 5,912 of its 12,000-character excerpt. The reader ignored
the family-wide notice and returned an unrelated CPX product’s values, which were dropped by the gates.
A selector-priority experiment produced an identical cached result (`20261021-110621-4740c2`), charged
zero dollars/credits, and was reverted. The next general prompt change supplies the inbox label to the
reader and asks it to establish family membership when applying a family-wide notice, while excluding
unrelated products. No source URL, case ID or expected status is embedded in code or prompts.
Candidate-verification cap skips also now emit stage/reason warnings. This retry's c02 fix discovery wandered into irrelevant scientific results; quote gating
prevented them from becoming a passing fix, but retrieval quality remains an open problem.


### Prompt and matcher changes: before / after

| General change | Before (live evidence) | After (live evidence) |
| --- | --- | --- |
| Normalize escaped whitespace and typography on both quote sides | c03 baseline kept 0/4 claims; a literal escaped newline lost a real VOC quote | c03 `20261021-081115-f416b6` kept 8/16 claims and caught currency; unsupported claims still dropped |
| Ground complete standard identifiers in supporting quotes | Parenthetical test aliases caused a false spec failure in `20261021-075808-b7f23e` | `20261021-080506-f3e537` caught currency without that false standards failure |
| Require the same numeric value and bound in quote; one feedback retry | `<2` paired with `<250` was wrongly accepted; enforcing the gate initially lost currency | `20261021-081115-f416b6` used the exact `<2` quote; no relaxation of the gate |
| Read all product/system pages and request equality dependencies plus known performance fields | Full baseline c02 omitted F, c04 omitted the plastic-pipe list, c06 omitted performance options | c02/c04 targeted `20261021-084706-627716` caught both failures with 20/20 claims; c06 variants remain unresolved |
| Prevent metric relabelling and arbitrary variant selection | L80 became L70, LPW became CRI, a non-configurable driver value became product-wide; duplicate values overwrote one another | c05 `20261021-101307-dd95fb` became a note rather than a false major failure; ambiguous measurements remain unverified |
| Read the product page's linked document, retain actual PDF URL, reject raw PDF syntax | c01 legacy standalone PDF produced a wrong revision note; raw PDF bytes entered the reader | Full run 2 c01 approved; raw syntax is dropped, unresolved LDN6 is still unknown |
| Bound direct HTTP time and cache failed document probes | Full run 2 c03 took 467.503 s, largely repeated free HTTP waits | Targeted c03 took 79.454 s with mixed warm caches; no controlled cold speedup claim |
| Limit web-reader property names in its schema | Replies wandered into unrelated properties, large responses, and cutoffs | Targeted reader replies fit the named properties; multiple variant values remain allowed |
| Supply input label and ask about family-wide status separately | c07 notice reached the reader but was ignored; unrelated CPX values were dropped | Family-reader retry is pending; not claimed fixed yet |
| Preserve coded uncertainty in report instructions | A document difference could be described as a safety/code violation | Reports receive verdict/severity and explicit uncertainty guidance; no separate report-quality score is claimed |

Latest mock suite: **237 passed, 2 skipped in 12.60 s**; mock eval `20261021-110847-af1c53`:
8/8 calls, 6/6 problems, 0/2 major false alarms, 2/5 passing fixes; claims 46/48 and web 19/20.


### Family status and cap retries — 2026-10-21

`20261021-110848-b21afe` correctly caught c07's discontinued status. The original scripted check now read
`As of **June 30th, 2024**, the TL family will be discontinued.` from the manufacturer notice. The fix search
still hit shared investigation and candidate-verification credit caps: its no-fix result was invalid until retried.
Ledger after: **$0.759579 / 238 credits**.

`20261021-111033-3966a9` repeated c07 with 24 calls/investigation, 30 shared investigation credits and a
40-credit fix allowance, all inside the unchanged 60/item and pass ceilings. It correctly caught status and
finished with **no cap/provider warnings**, 30 combined candidate-investigation steps, outcome not_found,
no passing fix, **112.921 s**. Ledger: **$0.826367 / 250 credits**. These are disclosed cap retries, not
improvements attributed to default settings. Both retries have redacted request/response and repro artifacts.

### Full live run 3 — 2026-10-21

Run `20261021-111241-b49a08`; output 32,768, investigation steps 24, investigation credits 30, fix credits 40.
Other quality settings and checklist rows are unchanged. Raw scorer: **6/8 calls**, **5/6 problems**,
**0/2 major false alarms**, **1/5 coded passing fixes**; **46.159 s/item**, **$0.063565 equivalent/item**.
Claims **153/185** (17.3% dropped), web **31/43** (27.9% dropped). No cap/provider warnings on any item.
Ledger: **$0.981441 / 280 credits**; fresh run charge **$0.155074 / 30 credits**.

The coded passing fix is **not accepted as a valid fix**: c02's proposed FIP 1-Step product data sheet had only
one check, “Current document”, without any evidence that T equalled F. This is a general fix-verification hole:
conditional requirements absent from candidate findings were silently omitted. A replacement must now
include a check for every originally failed requirement; missing evidence is unknown and prevents “Passes”.
The main F04 applicability policy remains unchanged and pending Kyle; this closes the independent fix hole.

Remaining wrong calls: c05 approve_with_note rather than approve (L70, warranty, DLC, driver configuration,
and a different 2025 revision); c06 approve_with_note rather than currency send-back. The c06 Investigator
found a readable **LDN6 SWW** sheet with `Rev. 05/12/22`, not the original exact configuration. Quoted CRI
and warranty match; old/current wattage and efficacy options remain ambiguous. Its “found” is a document
retrieval outcome, **not a resolved currency problem**. It also copied submitted standard identifiers onto
`Certified to US and Canadian safety standards.`; that quote does not state those identifiers.

The shared value gate now requires each categorical identifier to occur in its quote (case/spacing/punctuation
normalization retained), as well as the existing exact page quote, numeric bound and metric-label checks.
Null/empty claims cannot supply a value. The one validation-feedback retry now covers categorical values too.
No unconfirmed value is converted into a failure. Tests cover copied standards, partial numeric identifiers,
missing failed-requirement evidence and a genuinely corrected requirement.

That stricter gate exposed two old mock-fixture defects: c01's standards quote omitted ASTM E814, even though
the full contiguous statement was already in its stored page; c04's pipe-type list included paraphrased size
qualifiers and quoted only the first pipe. Repaired those **fixture responses** using their existing source text:
c01's quote now starts at ASTM E814; c04 uses the six literal pipe identifiers and the complete contiguous
penetrant list for both extracted and web claims. No source text, expected decision/problem, or reviewed row
was changed. Before repair the suite had 10 failures and mock eval 6/8; after repair: **244 passed, 2 skipped
in 12.13 s**, mock `20261021-112113-2b5f8f` **8/8**, 6/6 problems, 0/2 major false alarms, 2/5 passing fixes,
claims 45/48, web 19/20. The fourth (last allowed) full live evaluation is in progress.


### Final full eval and samples — 2026-10-21

Final cases `20261021-112213-cb4555`: **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**;
3.365 s/item with warm caches, $0.033602 equivalent/item. Claims 149/185 (19.5% dropped), web 27/40
(32.5% dropped). No caps/provider warnings/errors. Fresh charge $0.024414 / 0 credits; ledger after
**$1.005855 / 280 credits**. C02’s previously false passing fix is now blocked by missing F/T evidence.

Samples `20261021-112328-21358e`: **1/4 calls, 0/2 problems, 0/3 major false alarms, 0/1 passing fixes**;
62.568 s/item, $0.035761 equivalent/item. Claims 170/185 (8.1% dropped), web 11/11 (0% dropped).
No caps/provider warnings/errors. Fresh charge $0.042923 / 11 credits; ledger **$1.048778 / 291 credits**.
Detailed stage diagnoses, counters and Investigator outcomes are in `live-first-pass/gate4-review.md`;
redacted request/response and repro artifacts are `full-fourth-*` and `samples-first-*` beside it.

The final cases triggered 2 primary investigations; one found a quoted revision for an uncertain SWW
configuration, neither resolved the missing planted problem, and none capped. Four replacement investigations
also ran, none capped and none produced a passing fix. This distinguishes “found a document” from resolving
the review task. No sample required the Investigator.

At the end of October 21, Gate 4 awaited review of the written misses. On October 22 Kyle directed
“finish all unfinished things”; work continued with these limitations disclosed. Four full evals have been used.
The later owner dashboard reading and its scope/precision limitations are recorded below.


## Phase 5 — recording and replay, 2026-10-22

Recording `20261022-181611-a9d0b5` contains c01–c08 and public samples s3/s4, with a cases-only scoreboard.
The script now runs the union of scoring, tray and watched IDs and refuses to publish an incomplete result set.
Mock regression checks: **247 passed, 2 skipped in 12.62 s**, eval **8/8**. Web build passed in 5.82 s.
The live recording preserves the panel **6/8, 5/6, 0/2 major false alarms, 0/5 passing fixes** and quote-gate
counts 149/185 claims, 27/40 web values. All provider responses were cached: **$0 / 0 fresh credits**.
The recording is a capture of previously paid live responses, not a new uncached provider benchmark.

`phase5-api.json` proves GET /api/scores serves this run and POST /api/runs/replay returns ten live results.
`phase5-low-cap.json` proves a zero-day-cap full-tray + watched scan replays all eight public IDs, including
s3/s4. `phase5-cap-restored.json` proves restoration to the requested Phase 6 caps: $3/run, $8/day, 60/item,
600 credits/day, concurrency 2. Credentials were neither printed nor changed. Per-file boolean scans for
both provider keys and the admin token are in `phase5-secret-scan.json`; all were false.

Port 8000 was already occupied by an unrelated ShuttleWorks fixture API (health mode fixture; scores 404).
That process was left untouched. All local checks use **http://127.0.0.1:8001**. No deployment was made.

Owner dashboard reading received 2026-10-22 during this session: **288 Tavily credits, $1.05 Token Factory**.
The local pass total at that observation was 291 credits / $1.048778. Token Factory agrees to the dashboard’s
cent precision. Tavily is three credits lower than the ledger; this equals the three early one-credit estimates
without reported usage, but causality and account/key scope remain unproven. The ledger was not adjusted.
The earlier 15/9000 observation lacks a timestamp/scope, so it is not used as a synchronized delta baseline.


## Phase 6 — local judge walk, 2026-10-22

The private `.env` now has the requested production spending caps: $3/run, $8/day, 60 Tavily credits/item,
600/day, concurrency 2; live mode and thinking off. Measured retry quality limits were supplied only to the
app/recording commands: `MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40`.
No code or `.env` quality defaults were changed. Port 8001 is the documented local substitute for occupied 8000.

A real Chromium walk completed Inbox → Scan → Review → Outcome, saved c01/c03 decisions, pressed
“Check approved now”, and opened Specs and Scoreboard. Scan `20261022-182245-2b796d` and approved check
`20261022-182432-6bd04e` were live and fully cached; each left today's ledger at $0 / 0.
The approved check showed c01 unchanged and the watched TL troffer discontinued, backed by its manufacturer quote.
No nightly job was run; the page correctly says no nightly re-check has reported.

An official STI SSS Intumescent Sealant PDF, absent from all case/sample inputs, was dropped through the public
Inbox without an admin header. Upload `u-ccb0ffe5` produced a live approve_with_note with three kept claims,
no cap/provider warnings and no mock fixture. Source URL, SHA-256, public request/result and screenshots are
in [the judge walk](live-first-pass/judge-walk/README.md). After the first smoke plus this upload,
today's ledger was $0.009703 / 7 credits.

The first smoke failed its fresh-provider assertion because c01 was fully cached. One exact Nano triage cache
entry was preserved outside `.cache/` so the repeat exercised a fresh provider call; no cache directory was
cleared. Final smoke `20261022-182735-a950f9` passed health/project, bounded live scan, PDF, specs, scores and
watch checks. The provider repopulated that entry. See `phase6-smoke-initial.txt`,
`phase6-smoke-cache-preparation.json`, `phase6-smoke.txt` and `phase6-smoke-ledger.json`.

The screenshot audit found and fixed a source-date renderer showing “Invalid Date”, a replacement summary
calling unknown evidence a failure, and unqualified cached costs/major-only false alarms. Regression checks
cover source dates and unknown/failed replacement distinction. Before/after screenshots and every remaining
observed misleading line are listed in the judge walk. No verdict or evidence gate was weakened.

## Final spend and validation — 2026-10-22

| UTC ledger day | Token Factory USD | Tavily credits |
| --- | ---: | ---: |
| 2026-10-21 | 1.048778 | 291 |
| 2026-10-22 | 0.009827 | 7 |
| **Pass total** | **1.058605** | **298** |

The total remains below $20 / 2,000. Owner console reading was before the final upload/smoke charges, not a
final invoice check. No ledger adjustment was made for the unexplained three-credit dashboard difference.
The three earliest search credits remain estimates; subsequent returned provider usage is used when present.

Final regression suite: **247 passed, 2 skipped in 12.42 s**. Final mock eval
`20261022-183901-964db3`: **8/8 calls, 6/6 problems, 0/2 major false alarms, 2/5 passing fixes**,
45/48 claims and 19/20 web values kept. `npm run test:presentation` passed; final `npm run build` passed
in 5.76 s. No fifth Phase 4 eight-case evaluation was run. Phase 5 recording was the separate requested capture.

## Phase 7 — handoff

FEEDBACK contains dated, redacted requests/responses and reproduction steps for observed provider behavior,
including model casing, JSON mode, no-think fields, tools, latency, host access, credit math and console reading.
README/SUBMISSION now show the live panel and its limits; no deployment/nightly success is claimed.
The [completion audit](live-first-pass/completion.md) ranks the open issues and records the final PR.

PR: [#12 — first live pass](https://github.com/wongywrongy/nebiusxnvidiahack26/pull/12), `live/first-pass` → `master`; pushed and open for review.
No merge or deployment was performed.

## Readiness follow-up billing checkpoint — 2026-10-22

The original first pass above remains historical. Kyle subsequently authorized the readiness refinement plan and targeted live validation. [Readiness evidence](judge-readiness/g2/live-validation.md) records c03/c07 before and after general fixes. The two-item guarded confirmation at this dated checkpoint is **2/2 calls, 2/2 problems, 0/2 passing fixes**, not a new full evaluation or release pass. No follow-up full eight-case eval had run.

After these targeted runs, the actual local day report is **$0.4379588 / 67 credits** for October 22; adding October 21 **$1.048778 / 291** gives cumulative **$1.4867368 / 358**. The follow-up added **$0.4281318 / 60** beyond the prior cumulative baseline. The local durable wallet has no outstanding holds. Kyle replied “that is correct” to the reported cumulative $1.4867368 / 358 totals on 2026-10-22. This is owner confirmation of the reported totals; a separate dashboard readout, its timestamp and account/key scope were not supplied. The earlier three-credit gap is still unexplained, and no ledger was adjusted.

## Post-targeted billing note — 2026-10-23

After final affected c03/c07 run `20261023-023154-e725f0`, the actual local campaign ledger reports
**$1.9702294 / 391 Tavily credits**, with no outstanding holds. The UTC day ledger reports
**$0.4834926 / 33 credits**; one of those day credits preceded this checkpoint. The checkpoint itself
adds **$0.4834926 / 32 credits**. The final two-item run adds **$0.1244169 / 7 credits**.

Kyle's last response confirmed the previously reported $1.4867368 / 358, without a separate dashboard
readout, timestamp or account/key scope. No new dashboard reading covers the additional usage here.
Reconciliation is therefore pending, not a claimed match. The historical three-credit discrepancy remains
unexplained; no ledger or invoice was adjusted. [Per-run requests, responses, traces and wallet](judge-readiness/replacement-discovery-20261023/README.md).

## Claim-repair billing checkpoint — 2026-10-23

The [five targeted claim/citation runs](judge-readiness/claim-repair-20261023/README.md) add **$0.5553024 /
28 Tavily credits**. The actual cumulative local ledger is **$2.5255318 / 419**, no outstanding holds or
persistent block; UTC-day usage is **$1.038795 / 61**. Final two-item run `20261023-055339-e48fd0` adds
**$0.0562113 / 0**, makes 2/2 correct calls and has no passing fix. This is not a full-set result or release.
The intermediate live reservation settled normally without resetting accounting or starting a duplicate run.

Kyle has supplied no new timestamped dashboard reading for this usage. His earlier confirmation and the
unexplained historical three-credit discrepancy remain as recorded. No invoice match is inferred and no
ledger is altered. The previous model/credit caps and final-validation reserves remain in force.

## Scope and account-wide billing checkpoint — 2026-10-23

Targeted run `20261023-064841-187b83` retains 2/2 correct calls/problems, 0/2 passing fixes, no invalid
items or provider/cap warnings. It adds **$0.0424338 / 7 credits**, cumulative local **$2.5679656 / 426**,
UTC-day **$1.0812288 / 68**, no holds. The general matcher accepts unconditional L70/MacAdam statements
beside a separate optional lifetime clause; it still rejects unselected driver and conditional DLC proof.
[Exact before/after, traces and 615-test verification](judge-readiness/scope-binding-20261023/README.md).
No follow-up full set or final recording was used; G2 remains open.

Kyle's new reading, received **07:04:28 UTC**, is **$2.13 / 421 Tavily credits**. He explicitly confirms
**account-wide** scope. The dashboard's own cutoff/time and inclusion of today's usage remain unspecified.
Local minus owner is **$0.4379656 / 5 credits**. A separate authenticated read-only Tavily `GET /usage` at
**07:10:32 UTC** reports **415** for both account and key, not a match to the dashboard or local ledger.
The current public Token Factory catalog lists Super cached input at $0.06/million versus ordinary
$0.30/million; the ledger used ordinary prices and historical cached-token quantities were not retained.
This could explain part of the dollar difference, but no amount or cause is established. A local audit
checks 776 settled records, zero holds and exact seed-plus-settlement conservation. Reconciliation is
**unresolved**, not an invoice match; no seed, ledger, invoice or cap was changed. The higher local total
continues to enforce the ceiling. Redacted requests/responses and reproduction are in the linked checkpoint.

## Required replacement research checkpoint — 2026-10-23

[Targeted run `20261023-071700-8a9e33`](judge-readiness/replacement-research-20261023/README.md)
passes two-item evidence consistency and keeps **2/2 calls/problems, 0/2 passing replacements**, no invalid
items or provider/cap warnings. Four replacement investigations run, none capped; no primary investigation
is needed. Applicable missing requirements, candidate URL and explicit availability context now reach the
Investigator, and newly discovered status/supplementary sources survive the final bounded read. Unsupported
availability and unselected configurations still fail to establish proof. No key or checklist is changed.

Full mock regression: **621 passed, 2 skipped in 31.67 seconds**; raw mock remains **6/8, 5/6, 0/2, 0/5**,
48/65 claims and 8/20 web values. Fresh targeted charges **$0.0671367 / 12 credits**, cumulative actual local
**$2.6351023 / 438**, UTC-day **$1.1483655 / 80**, no holds or persistent block. The prior owner account-wide
$2.13 / 421 and separate Tavily API 415 observations predate this run; no current invoice match is claimed.
The higher local accounting remains in force. G2 is open; no broader evaluation, blind evaluation, final
recording, cloud action or owner approval is inferred.

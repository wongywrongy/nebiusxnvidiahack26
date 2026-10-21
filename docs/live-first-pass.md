# First live pass — 2026-10-21

Status: Gate 3 was approved, saved and pushed as `d8eb713`. Phase 4 is diagnosing the first c03 live run.
No full eight-case live evaluation or demo recording has been made yet.

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
After the first c03 live pass it records `{"usd": 0.018874, "credits": 11.0}`.
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

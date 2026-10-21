# First live pass — 2026-10-21

Status: Gate 2 provider checks passed; stopped for Kyle's review. No case has been run live.

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

Before the first provider call `.cache/budget/2026-10-21.json` did not exist.
After the provider spikes it records `{"usd": 0.000226, "credits": 6.0}`.
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

Gate 2: Super schema-valid JSON, native tools and fresh manufacturer extraction all work. Billing counter
reconciliation and the stated account allowance remain open. Phase 3 requires Kyle's go-ahead, followed by
his explicit checklist review at Gate 3; no checklist has been self-approved.

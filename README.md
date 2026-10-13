# SpecCheck

**A rejected submittal costs a construction project two weeks.** SpecCheck reads a subcontractor's product
submittal, checks it against the project spec, checks the product against the manufacturer's *current* documents on
the live web, finds a replacement that passes when it doesn't, and keeps watching approved items for the day the
manufacturer discontinues one. Every finding carries the quote it rests on.

Built solo for the **Nebius x NVIDIA Global AI Hackathon** (Best Apps and Agents track) by someone who builds
document pipelines for a general contractor and has watched this problem cost real weeks.

- **Live demo:** _URL on the Devpost page_ · **Video:** _YouTube link_ · **License:** MIT
- **Models:** NVIDIA **Nemotron 3 Nano** and **Nemotron 3 Super**, served by **Nebius Token Factory**
- **Web:** **Tavily** Search, Extract and bounded Map for the manufacturer's current documents
- **Cloud:** deployment configuration for a **Nebius Serverless Endpoint** and a nightly **Nebius Serverless Job**;
  deployment and live provider results have not been verified in this checkout

## Where Nemotron and Token Factory do the work

| Step | Who | What it does | Why this tier |
| --- | --- | --- | --- |
| Sort the pages of a package | **Nemotron 3 Nano** on Token Factory | labels each page: product data, listing, system drawing, installation, warranty, other | runs on every page; the cheap, fast call |
| Read the spec | **Nemotron 3 Super** | turns a CSI spec section into a checklist of properties, operators and values (`t_rating_hr eq_ref f_rating_hr`) | long context, structured output; done once per spec, then reviewed by a person |
| Read the data sheet | **Nemotron 3 Super** | extracts the product's stated values, each with the page and the quote it comes from | the same structured extraction, against the reviewed checklist |
| Check the spec | plain code | compares each claim to its requirement, converts units, decides pass/fail/not stated | deterministic; a model never decides a verdict |
| Check reality | **Tavily** + **Nemotron 3 Super** | Tavily finds and fetches the manufacturer's current sheet and any discontinuation notice; Super reads the current values, each with a quote; code diffs them | the web is where the current truth lives |
| Find a fix | **Tavily** + the same pipeline | for a send-back, searches for the current sheet or a listed system that fits, then runs each candidate through the *same* extract → spec check → web check | nothing is suggested that was not checked |
| Write the result | **Nemotron 3 Super** | the plain-language summary, the note to the sub, a title and "why it matters" per issue | words only; the findings already stand |
| Watch approved items | the same pipeline as a **Nebius Serverless Job**, nightly | re-checks approved submittals against the manufacturer's live documents; raises a discontinuation with the maker's own quote and a replacement that passes | the part a human never gets around to |

Structured reads ask for JSON against a Pydantic schema (`response_format: json_schema`, with the `json_object`
fallback); Investigator turns use native tools without `response_format`. Both use temperature 0 and thinking off (Nemotron 3 reasons by default; these are extraction calls,
so thinking would only spend output tokens). Replies are cached on disk so a document is paid for once. Spend is
capped per run and per day before each call is made. Each result carries its trace: every model call with tokens,
latency and cost, and the Tavily credits, shown in the app under "Checked by".

**Models read and quote; code decides.** A claim whose quote is not found on the page it cites is dropped. A web
value, revision or status without a quote on a fetched page is dropped. What nothing confirms is reported as
"couldn't confirm", never as a failure.

When the scripted check has no quoted answer, the **Investigator** lets Nemotron 3 Super choose Tavily search,
map and extract calls, then finish with exact quotes. It stops after six tool calls, including finish, and shares
an eight-credit investigation allowance across each item's checks and fix candidates. Extracted pages stay whole
for quote verification; the model sees at most 6,000 characters per tool result. Accepted documents go through the
same value comparison as the scripted check. The Review trace lists each step; the Scan row says "Investigating".
The s4 Hilti sample demonstrates this offline with an explicitly labelled, hand-written mock fixture.

The scripted status search uses Tavily news results, publication dates and an exact quoted model number;
the manufacturer search prefers its domains. With no manufacturer-tier hit, one Map call (20 pages, depth 1)
and one Extract call (up to three links, PDFs first) share a five-credit cap before the Investigator is considered.
All recovered text passes the same quote checks. These request options follow the Tavily docs and have mocked
400-response coverage; their live behavior has not been checked.

Owner-only live validation (not run for this change; these commands spend tokens and credits):

```bash
python scripts/fetch_docs.py
SPECCHECK_MODE=live python scripts/eval.py --samples
SPECCHECK_MODE=live python scripts/eval.py --case s4
SPECCHECK_MODE=live uvicorn api.main:app
```

Add Hilti FS-ONE MAX from the tray and Scan. An investigation is expected only if the scripted sources do not
confirm a revision or values; a successful scripted check skips it. Look for at most six steps per investigation,
quoted evidence behind any accepted revision/status, `task="investigate"` usage, and an honest capped/unconfirmed
result if no source can be verified. Live recovery rate and provider compatibility remain unverified.

## What the reviewer sees

1. **Inbox.** Drag sample submittals in (real public documents from STI, 3M, Hilti and Lithonia, as two
   subcontractors would send them) or drop your own PDF. Nothing runs until you press Scan.
2. **Scan.** Each row streams its stages: reading pages, checking the spec, checking the manufacturer online,
   looking for a replacement, writing the summary.
3. **Review.** One submittal at a time: the PDF with the quoted lines highlighted, the check table (required vs
   submitted, and current vs submitted), the suggested replacement if one passed, and an editable message
   addressed to the sub or forwarded to the architect.
4. **Outcome.** What went back to whom with what request; what was approved and forwarded. "Check approved now"
   re-runs the approved items; the troffer approved in March 2024 comes back discontinued, with Acuity's notice
   quoted and a replacement that passes every check.

The browser saves the inbox, completed results, edited messages and decisions in localStorage when available.
An interrupted scan needs Retry after reload; it never starts another paid run automatically. **Start over**
clears this browser's session, including message drafts. It does not delete server uploads or cancel work already
running on the server.

## Scoreboard

Eight submittals against two Chicago Public Schools spec sections (07 84 00 Firestopping, 26 51 00 Interior
Lighting), each with a hand-built answer key from the real documents: two clean packages, one spec failure
(T rating below F), one listing that does not cover the penetrant, two out-of-date sheets, one discontinued
product, and one newer sheet with unchanged values (a note, not a send-back).

| | |
| --- | --- |
| right call | 8 of 8 |
| planted problems caught | 6 of 6 |
| clean packages wrongly flagged | 0 of 2 |
| replacements found that pass the spec | 2 of 5 |

_Mock replay, 2026-10-13. `python scripts/record_live.py` runs all eight live and saves them under
`runs/recorded/`._ `scripts/eval.py` writes `runs/scores.json`; `GET /api/scores` serves it. The table above is
maintained manually and is not a live result.

## Run it

```bash
# Mock mode: recorded answers, no keys, no API calls.
pip install -r api/requirements.txt
sudo apt-get update && sudo apt-get install -y tesseract-ocr  # local OCR on Debian/Ubuntu; included in Docker
SPECCHECK_MODE=mock python scripts/eval.py       # the scoreboard from fixtures
SPECCHECK_MODE=mock uvicorn api.main:app --reload # http://localhost:8000 (after: cd web && npm install && npm run build)

# Live mode: Nemotron on Token Factory and Tavily, cached in .cache/ after the first run.
cp .env.example .env                # SPECCHECK_MODE=live, NEBIUS_API_KEY, TAVILY_API_KEY, ADMIN_TOKEN
python scripts/fetch_docs.py        # the public PDFs into data/raw/ (not committed)
python scripts/spike_models.py      # one tiny call per model: ids, json_schema, thinking off
python scripts/draft_requirements.py   # Super drafts each spec's checklist; review, save as data/requirements/<section>.json
SPECCHECK_MODE=live python scripts/eval.py --case c03
python scripts/record_live.py       # all eight live, recorded to runs/recorded/ (commit it)
python scripts/recheck.py           # the nightly re-check, by hand
```

Pages with fewer than 40 text characters are rendered at 200 dpi for local Tesseract OCR. Nemotron reads that
text through the existing router; no vision model is claimed. Work is bounded to 20 OCR attempts per PDF,
40 megapixels per rendered page and 15 seconds per Tesseract call. If OCR is missing or fails, native text is
retained and absent evidence stays unconfirmed. OCR pages have no invented highlight boxes. The Review trace
shows the OCR page count and explicitly labels mock model reads.

Deploying the demo as a Nebius Serverless Endpoint and the nightly job as a Nebius Serverless Job:
[deploy/nebius/README.md](deploy/nebius/README.md). One container (`Dockerfile`) serves both.

Live, tray items, watched items and uploaded PDFs run without an admin token, under the per-IP rate limit,
upload size limit and spend caps. Set `PUBLIC_UPLOADS_LIVE=false` to force public uploads to mock mode;
`X-Admin-Token` still permits live uploads and bypasses the rate limit. At either daily cap, a scan can replay
only its requested tray/watched items from the newest recording, provided it contains every requested item;
uploads receive a clear 429.
The Scan note and result trace label a replay and retain the original usage/time. `/api/health` reports key
presence (true/false only), models, today's spend and `budget: {usd_left, credits_left}`.
An early model failure shows its reason and a Retry action for that item. Later web, fix or summary failures
keep the checked findings and explain what couldn't be confirmed. These paths are tested with fixtures/respx;
live provider behavior remains for the owner to verify.

Owner check (uses paid APIs; not run during development):

```bash
SPECCHECK_MODE=live PUBLIC_UPLOADS_LIVE=true uvicorn api.main:app
# In the browser: upload one PDF, Scan without an admin header, then inspect its trace.
# Replay check after creating a real recording with scripts/record_live.py:
SPECCHECK_MODE=live BUDGET_USD_PER_DAY=0 uvicorn api.main:app
# Add a recorded tray item and Scan: the dated replay note must appear. An upload must return 429.
```

Secret scan: `pip install pre-commit && pre-commit install` (gitleaks on every commit).

The header's **Specs** page shows each project source, control version and checklist. Bundled fixture checklists
are labelled mock stand-ins; missing draft/review dates are never invented. In live mode, dropping a spec PDF
drafts a checklist with Nemotron 3 Super, under the same public rate/size and model-budget limits. The response
includes its model, source name/hash and draft date. It is not saved as a project checklist or used by scans;
normal model response caching still applies. Only an admin can save it after reviewing the requirements and
setting `reviewed_at`. `scripts/draft_requirements.py` writes the same provenance fields.

**Scoreboard**, linked from the header and Scan totals, displays `/api/scores`: four computed panel values,
per-case expected/actual calls, problems, fixes, time and cost. Its label comes from the score file's mode/date.
On a clean install with no saved scores or recording, the API computes and saves the mock set without any
provider calls, even on a live server. It stays labelled mock until the owner records a live evaluation.
The answer key is a small hand-authored demonstration set, not an unseen validation set.

Owner checklist workflow (the draft call below spends real model tokens):

```bash
SPECCHECK_MODE=live uvicorn api.main:app
# In another shell, with ADMIN_TOKEN available only in your environment:
curl --fail-with-body -X POST 'http://localhost:8000/api/specs/draft?section=07%2084%2000&name=project-spec.pdf' \
  -H 'Content-Type: application/pdf' --data-binary @data/raw/specs/cps_07_84_00.pdf > /tmp/checklist-response.json
jq '.draft' /tmp/checklist-response.json > /tmp/reviewed-checklist.json
# Review/edit every requirement in that file, then set reviewed_at to the date you reviewed it (YYYY-MM-DD).
curl --fail-with-body -X POST 'http://localhost:8000/api/specs/07%2084%2000' \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H 'Content-Type: application/json' --data-binary @/tmp/reviewed-checklist.json
```

## Layout

```
api/
  config.py        settings (.env), mode, model per task, prices, thinking, budget caps, log redaction
  schemas.py       Pydantic models: Requirement, Claim, Evidence, Finding, Result, Usage, Event
  llm.py           model router: fixtures in mock mode, providers/tokenfactory live
  web.py           web lookups: fixtures in mock mode, providers/tavily live
  providers/       tokenfactory.py (Nemotron chat: json_schema, no-think flags, retries, cache, cost)
                   tavily.py (search / extract / map, credits, fetch_pdf), budget.py (run/item/day caps)
  pipeline/        ingest, extract (triage, requirements, claims), spec_check, verify, fix, decide, render, runner, scores
  main.py          FastAPI: project, inbox, scan, SSE events, results, scores, watch report, static web app
data/
  cases/           cases.json (8 test submittals + answer key), samples.json (the tray), specs.json, documents.json
  fixtures/        recorded answers per case for mock mode; fixtures/fix/ for the fix step
  requirements/    reviewed checklist per spec section (scripts/draft_requirements.py, then a person)
  raw/             downloaded PDFs (gitignored; baked into the image when present)
scripts/
  fetch_docs.py    download the public documents and record their sha256
  spike_models.py  list models, one tiny live call each
  eval.py          the scoreboard against the answer key
  record_live.py   a live run of all cases, recorded for the public demo
  recheck.py       the nightly re-check (runs as a Nebius Serverless Job)
deploy/nebius/     endpoint + job commands
.github/workflows/ image.yml (build + push to GHCR), nightly-recheck.yml (schedule → Serverless Job)
web/               React + Vite + Tailwind app
tests/             pytest (providers mocked with respx; no network)
```

## Test documents

The eight cases and four samples use public documents: Chicago Public Schools spec sections and STI, Hilti, 3M and
Acuity/Lithonia data sheets, listings and notices. The PDFs are not committed; `scripts/fetch_docs.py` downloads
them from the URLs in `data/cases/documents.json` (first URL that returns a real PDF wins) and records their
sha256, so an uploaded copy of a known document is recognised.

## Feedback on the tools

[FEEDBACK.md](FEEDBACK.md): dated, reproducible notes on Token Factory, Nemotron 3 and Tavily as they came up.

## License

MIT

# SpecCheck

**A rejected submittal costs a construction project two weeks.** SpecCheck reads a subcontractor's product
submittal, checks it against the project spec, checks the product against the manufacturer's *current* documents on
the live web, finds a replacement that passes when it doesn't, and keeps watching approved items for the day the
manufacturer discontinues one. Every finding carries the quote it rests on.

Built solo for the **Nebius x NVIDIA Global AI Hackathon** (Best Apps and Agents track) by someone who builds
document pipelines for a general contractor and has watched this problem cost real weeks.

- **Live demo:** _URL on the Devpost page_ · **Video:** _YouTube link_ · **License:** MIT
- **Models:** NVIDIA **Nemotron 3 Nano** and **Nemotron 3 Super**, served by **Nebius Token Factory**
- **Web:** **Tavily** (Search, Extract, Map) for the manufacturer's current documents
- **Cloud:** the demo runs as a **Nebius Serverless Endpoint**; the nightly re-check runs as a **Nebius Serverless Job**

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

Every call asks for JSON against a Pydantic schema (`response_format: json_schema`, with the `json_object`
fallback), at temperature 0, with thinking turned off (Nemotron 3 reasons by default; these are extraction calls,
so thinking would only spend output tokens). Replies are cached on disk so a document is paid for once. Spend is
capped per run and per day before each call is made. Each result carries its trace: every model call with tokens,
latency and cost, and the Tavily credits, shown in the app under "Checked by".

**Models read and quote; code decides.** A claim whose quote is not found on the page it cites is dropped. A web
value, revision or status without a quote on a fetched page is dropped. What nothing confirms is reported as
"couldn't confirm", never as a failure.

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

_Mock replay, 2026-10-13. `python scripts/record_live.py` runs all eight live and rewrites this table and
`runs/recorded/`._ `scripts/eval.py` prints it; `GET /api/scores` serves it.

## Run it

```bash
# Mock mode: recorded answers, no keys, no API calls.
pip install -r api/requirements.txt
python scripts/eval.py              # the scoreboard from fixtures
uvicorn api.main:app --reload       # http://localhost:8000 (after: cd web && npm install && npm run build)

# Live mode: Nemotron on Token Factory and Tavily, cached in .cache/ after the first run.
cp .env.example .env                # SPECCHECK_MODE=live, NEBIUS_API_KEY, TAVILY_API_KEY, ADMIN_TOKEN
python scripts/fetch_docs.py        # the public PDFs into data/raw/ (not committed)
python scripts/spike_models.py      # one tiny call per model: ids, json_schema, thinking off
python scripts/draft_requirements.py   # Super drafts each spec's checklist; review, save as data/requirements/<section>.json
SPECCHECK_MODE=live python scripts/eval.py --case c03
python scripts/record_live.py       # all eight live, recorded to runs/recorded/ (commit it)
python scripts/recheck.py           # the nightly re-check, by hand
```

Deploying the demo as a Nebius Serverless Endpoint and the nightly job as a Nebius Serverless Job:
[deploy/nebius/README.md](deploy/nebius/README.md). One container (`Dockerfile`) serves both.

Live, the sample tray and the watched item run without a token: they are fixed public documents, cached after
their first run, and the caps hold. Your own uploaded PDF runs live with `ADMIN_TOKEN` (header `X-Admin-Token`),
else in mock mode with a note. `GET /api/health` reports the mode, which keys are set (true/false only), the model
ids and today's spend. Secret scan: `pip install pre-commit && pre-commit install` (gitleaks on every commit).

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

# SpecCheck

Checks construction submittals against the project spec **and** against the manufacturer's current documents on the live web, with a source for every finding.

Built for the Nebius x NVIDIA Global AI Hackathon (Best Apps and Agents track).

- **Models:** NVIDIA Nemotron 3 (Nano, Super, Ultra) on Nebius Token Factory
- **Web verification:** Tavily (Search, Map, Extract)
- **Stack:** Python + FastAPI, React + Vite, one container

## Quick start (mock mode, no API calls)

```bash
cd api
pip install -r requirements.txt
cd ..
python scripts/eval.py            # runs all 8 cases from fixtures, scores against the answer key, writes runs/scores.json
uvicorn api.main:app --reload     # API at http://localhost:8000
```

Mock mode replays recorded model and web responses from `data/fixtures/`, so the whole pipeline runs offline and costs nothing.

## Live mode

```bash
cp .env.example .env              # add NEBIUS_API_KEY and TAVILY_API_KEY
python scripts/fetch_docs.py      # download the public test documents into data/raw/
SPECCHECK_MODE=live python scripts/eval.py --case c03
```

Every live response is cached in `.cache/`, so re-running a case does not spend credits.
Spend is capped per run (USD), per item and per day (Tavily credits); a cap marks that step "Couldn't confirm".
A live deployment needs `ADMIN_TOKEN` (sent as `X-Admin-Token`) for live runs; without it the public demo
plays recorded runs and uploads run in mock mode. `GET /api/health` shows mode, which keys are set, models and today's spend.

Secret scan: `pip install pre-commit && pre-commit install` (gitleaks runs on every commit).

## Layout

```
api/
  config.py        settings (pydantic-settings, .env), mode, model per task, prices, log redaction
  schemas.py       Pydantic models: Requirement, Claim, Evidence, Finding, Result, Event
  llm.py           model router: mock fixtures, or providers/tokenfactory in live mode
  web.py           web lookups: mock fixtures, or providers/tavily in live mode
  providers/       tokenfactory.py (Nemotron chat, JSON, retries, cost), tavily.py (search/extract/map,
                   credits, fetch_pdf), budget.py (run/item/day caps, BudgetExceeded)
  cache.py         disk cache for live calls
  pipeline/        ingest, triage, extract, spec_check, verify, reconcile, fix, report, runner
  main.py          FastAPI: runs, uploads, SSE events, results, scores, replay, static web app
data/
  cases/           cases.json (8 test submittals + answer key), specs.json
  fixtures/        recorded responses per case for mock mode; fixtures/fix/ for the fix step
  raw/             downloaded PDFs (gitignored)
scripts/
  fetch_docs.py    download test documents and record sha256
  eval.py          scoreboard: right call, problems caught, false alarms, fixes that pass, time, cost
web/               React + Vite app
tests/             pytest
```

## Fixes for send-backs

When the call is send back, SpecCheck looks for what the sub should send instead:

- **Out of date or discontinued:** Tavily search for the maker's current sheet, or a current product in the same category.
- **Spec or listing problem:** Tavily search for listed systems for the same penetrant and assembly.

Each candidate (at most 3, under a Tavily credit cap per item: `FIX_MAX_CANDIDATES`, `FIX_CREDIT_CAP`) goes through the
same extract, spec check and web check as a new submittal. A candidate passes only if every check passed on quoted
evidence; otherwise the fix says "No passing replacement found" and lists what was tried. In mock mode 2 of 5 fixes
pass (c03, c07): c02's recorded search found nothing, c04's one candidate fails T = F, and c06's 2025 sheet doesn't
state CRI, dimming, warranty or DLC.

## Uploads and scores

- `POST /api/uploads?name=x.pdf` with the PDF as the body adds it as one more item, checked against the project specs
  on its own run. In mock mode, a PDF that matches a test case (by sha256) replays that case's fixture; any other PDF
  runs with no recorded answers, so every requirement shows as not stated.
- `GET /api/scores` serves `runs/scores.json` from `scripts/eval.py`; the Results page shows it, and its
  "Run the scoring set" button (`POST /api/scores/run`) reruns all 8 cases and rewrites it.
- Watchlist: cases with `watch` in `cases.json` are already approved. "Run nightly watch" re-checks them; c07 (the
  approved troffer, since discontinued) opens the Alert screen with its replacement.

## Model routing

| Task | Tier | Why |
| --- | --- | --- |
| Page triage | Nemotron 3 Nano | cheap, runs on every page |
| Requirement and claim extraction, sheet comparison, report | Nemotron 3 Super | long context, structured output |
| Spec comparison, unit conversion, the decision | plain code | deterministic, no model |

Models read; code decides. Every claim needs a quote found on its page, and every web value, revision or status needs a
quote found on a fetched page, or it is dropped. A value nothing confirms is "couldn't confirm": a note, never a send-back.
Ultra is not called: it's reserved for when sources disagree, which isn't built yet.

## Test documents

The 8 test cases use public documents (Chicago Public Schools spec sections, STI, Hilti, 3M and Acuity/Lithonia data sheets). The PDFs are not committed; `scripts/fetch_docs.py` downloads them from the URLs in `data/cases/documents.json` (first URL that returns a real PDF wins).

## License

MIT

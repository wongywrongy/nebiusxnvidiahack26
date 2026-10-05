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
python scripts/eval.py            # runs all 8 cases from fixtures, scores against the answer key
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

## Layout

```
api/
  config.py        settings, mode (mock | live), model IDs, prices
  schemas.py       Pydantic models: Requirement, Claim, Evidence, Finding, Result, Event
  llm.py           model router: task -> Nemotron tier, JSON schema, retries, token + cost log
  web.py           Tavily wrapper with the same mock/live switch
  cache.py         disk cache for live calls
  pipeline/        ingest, triage, extract, spec_check, verify, reconcile, report, runner
  main.py          FastAPI: runs, SSE events, results, replay, static web app
data/
  cases/           cases.json (8 test submittals + answer key), specs.json
  fixtures/        recorded responses per case for mock mode
  raw/             downloaded PDFs (gitignored)
scripts/
  fetch_docs.py    download test documents and record sha256
  eval.py          scoreboard: problems caught, false flags, time, cost
web/               React + Vite app
tests/             pytest
```

## Model routing

| Task | Tier | Why |
| --- | --- | --- |
| Page triage | Nemotron 3 Nano | cheap, runs on every page |
| Requirement and claim extraction, sheet comparison, report | Nemotron 3 Super | long context, structured output |
| Final calls on flagged items | Nemotron 3 Ultra | strongest reasoning, called only when something is flagged |
| Spec comparison of numbers and units | plain code | deterministic, no model |

## Test documents

The 8 test cases use public documents (Chicago Public Schools spec sections, Hilti, 3M and Acuity/Lithonia data sheets). The PDFs are not committed; `scripts/fetch_docs.py` downloads them from the URLs in `data/cases/cases.json`.

## License

MIT

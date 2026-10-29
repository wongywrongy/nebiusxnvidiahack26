# SpecCheck

Stop losing weeks to rejected submittals. SpecCheck checks each product data sheet against the project spec and the manufacturer's live website, then tells you exactly what to send instead.

**[Live demo](https://speccheck-wongywrongys-projects.vercel.app)** (no login) · [MIT license](LICENSE) · Nebius x NVIDIA Global AI Hackathon, Best Apps and Agents

## Try it

1. In the Inbox, click **Add all samples**, then **Scan**.
2. Read the package table, open a row, and read **What to send**.
3. Save decisions, open **Outcome**, and click **Check approved now**.
4. Open **Package review memo** to print the whole review.
5. Bring your own spec: open **Specs**, upload a spec section PDF, edit the drafted rules, then upload a product sheet against it. The **Try one** links under the drop zone give you sample PDFs.

## How it works

1. **Read.** Nemotron reads each data sheet and returns every value with its exact quote and page.
2. **Check the web.** Tavily finds the manufacturer's current documents. Nemotron reads those the same way to spot a newer sheet or a discontinued product.
3. **Decide.** Code, not the model, compares each value to the spec. A value counts only if its quote is on the cited page with the same number and unit. Anything unproven goes to a person.
4. **Report.** Each item gets a decision and **What to send**: the fix, an ordering option to specify, or ranked alternates. The package gets one table and a printable memo.

## NVIDIA Nemotron on Nebius Token Factory

| Model | What it does in SpecCheck |
| --- | --- |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Sorts PDF pages by type (product data, system drawing, listing, test report, warranty and others) |
| `nvidia/nemotron-3-super-120b-a12b` | Extracts quoted values, reads manufacturer sources, drafts checklists from an uploaded spec, writes reviewer notes |

How Token Factory sped up the work:

- **One OpenAI-compatible API for both models.** Each step picks its model with one setting (`MODEL_TRIAGE`, `MODEL_EXTRACT`, `MODEL_VERIFY`, `MODEL_WRITE`, `MODEL_DRAFT`). That let me compare Nemotron 3 Super, Super with reasoning, and Nemotron 3 Ultra on the same test set in one afternoon. Super with reasoning off ships.
- **Structured output.** Every extraction requests a JSON schema and is validated with Pydantic, so the pipeline gets typed data, not free text.
- **Reasoning per task.** It's off for fast extraction and on only for checklist drafting (`THINKING_TASKS`).
- **Usage on every response.** Token counts feed the per-call trace in the app and a spend ledger that reserves budget before each call. A full check averages about $0.13 per submittal.

## Other Nebius services

- **Nebius Serverless Endpoint** (AI Cloud, eu-west1, cpu-d3, 2 vCPU / 8 GB) runs the app's Docker container.
- **Nebius shared filesystem**, mounted at `/state`, keeps the spend ledger, uploads, cache and runs across redeploys.
- **Nebius MysteryBox** holds the API keys as secrets, outside the image.

Vercel provides the stable public URL. A GitHub Actions job re-checks approved products daily.

## Run locally

Requires Python 3.12 and Node 22.

```bash
python -m venv .venv
.venv/bin/pip install -r api/requirements.txt -c api/constraints.txt
cp .env.example .env
cd web && npm ci && npm run build && cd ..
SPECCHECK_MODE=mock .venv/bin/python scripts/serve.py
```

Open http://localhost:8000. **Mock mode** needs no keys and replays recorded results.

For **live mode**, put `NEBIUS_API_KEY` and `TAVILY_API_KEY` in `.env`, set `SPECCHECK_MODE=live`, and fetch the sample PDFs once:

```bash
.venv/bin/python scripts/fetch_docs.py
```

Tests: `SPECCHECK_MODE=mock .venv/bin/python -m pytest -q`

## Repository

| Path | Contents |
| --- | --- |
| `api/` | FastAPI app and the pipeline (`api/pipeline/`: read, check, decide, alternates, package) |
| `web/` | React + TypeScript front end |
| `data/` | Sample cases, spec sections and reviewed checklists |
| `scripts/` | Local server, evaluation and data fetch |
| `deploy/` | Nebius endpoint, Vercel and daily re-check setup |

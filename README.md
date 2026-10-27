# SpecCheck

SpecCheck reads construction product submittals and checks their quoted claims against a project spec and current manufacturer documents. NVIDIA Nemotron models read and quote; code decides whether each check passes, fails or cannot be confirmed. A reviewer follows **Inbox → Scan → Review → Outcome**, with the source PDF beside every finding.

**[Open the live demo](https://port8000-ddh028qg63p3bzj.tunnel.applications.eu-west1.nebius.cloud)** · [MIT license](LICENSE) · Solo entry, Nebius x NVIDIA Global AI Hackathon

## Try it

- Add the sample submittals in the Inbox, scan, review and save your decisions.
- No PDFs handy? Download a **Try one** product sheet beneath the drop zone, upload it and select its spec.
- Bring your own spec: open **Specs**, draft a checklist from the example UBC Door Hardware PDF, edit/delete rows and use it for an uploaded Schlage ND sheet. Drafts are **unreviewed**, saved for this browser, and available for 14 days. Rules for other product types are disclosed separately.

An upload with no quoted values matching its selected spec says **“Doesn't match this spec”**, uses no web credits, and appears as **Not checked**. Change its spec in the Inbox before scanning.

## Measured live panel

Recorded **October 22, 2026**, run **`20261022-181611-a9d0b5`**:

| Right calls | Problems caught | Clean cases wrongly flagged | Passing replacements |
| --- | --- | --- | --- |
| **6 / 8** | **5 / 6** | **0 / 2** | **0 / 5** |

This is a small known demonstration set, partly cached, rather than an unseen accuracy benchmark. **No passing replacement was found live; no Investigator rescue is claimed.** [Run evidence](docs/live-first-pass.md) · [Playground evidence](docs/playground/README.md) · [Deployment evidence](docs/deployment/README.md)

## Models and evidence

| Component | Work |
| --- | --- |
| **Nemotron 3 Nano**, Nebius Token Factory | Sorts PDF pages |
| **Nemotron 3 Super**, Nebius Token Factory | Drafts checklists, identifies draft product types, extracts quoted claims, reads manufacturer sources, investigates missing evidence and writes summaries |
| **Tavily Search, Extract and bounded Map** | Finds and retrieves current manufacturer documents |
| **Code** | Validates quotations, compares values, applies product-type scope and owns every verdict |

Unquoted claims and web values are dropped. “Couldn't confirm” is never a failure. A replacement is suggested only after its checks pass; messages remain editable drafts and are never sent. Mock results say mock, cached live calls remain labelled, and recorded fallback says replay. Checklist drafts are unreviewed. **No Nebius Serverless Job execution or nightly schedule is claimed.**

## Hosting and limits

The public app is one Nebius Serverless Endpoint in **eu-west1**, `cpu-d3` / 2 vCPUs / 8 GB RAM, with a 32 GiB container disk and a separate persistent filesystem for the campaign ledger, uploads, cache and runs. Its judging allowance is **$75 / 6,000 Tavily credits**, with **$8 / 600 daily caps**, **$3 per run** and concurrency **2**. Spend is reserved before each call; unknown usage settles at the reserved worst case. Missing or corrupt accounting blocks paid calls.

If deployed without persistent storage, replacing the container starts a fresh judging allowance, still bounded by the **$8 / 600 daily caps**; the campaign ceiling then does not survive replacement. The current endpoint uses persistent storage. Planned availability runs through **December 15, 2026, 20:00 UTC**. [Plain-container deployment](deploy/nebius/README.md)

## Run locally

```bash
python -m venv .venv
.venv/bin/pip install -r api/requirements.txt -c api/constraints.txt
cp .env.example .env  # Type keys here for live mode; never commit them.
cd web && npm ci && npm run build && cd ..
SPECCHECK_MODE=mock .venv/bin/python scripts/serve.py
```

Open `http://localhost:8000`. Mock mode makes no provider calls; spec drafting is live-only. For live mode set `SPECCHECK_MODE=live` and fetch the locked public PDFs with `.venv/bin/python scripts/fetch_docs.py` first. The public image includes those PDFs and the recorded fallback.

Validation: `SPECCHECK_MODE=mock python -m pytest -q` and `cd web && npm run build`. [Feedback from observed calls](FEEDBACK.md) · [Submission and video plan](SUBMISSION.md) · [Historical technical README](docs/history-readme-20261027.md)

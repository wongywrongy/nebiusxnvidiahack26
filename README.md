# SpecCheck

SpecCheck checks construction submittals against the project spec and the manufacturer's current documents on the live web. Review leads with **what to send**, ordering options to specify, and ranked alternates with anything still unconfirmed. A package view grouped by spec section, manual-review bucket and printable memo help the reviewer make and file the decision; NVIDIA Nemotron reads and quotes, and code decides.

**[Open the live demo](https://speccheck-wongywrongys-projects.vercel.app)** · [MIT license](LICENSE) · Solo entry, Nebius x NVIDIA Global AI Hackathon

## Try it

- Add the sample submittals in the Inbox, scan, review and save your decisions.
- Read the package matrix, open a row to review **What to send**, and flag an item for manual review when it needs a person. Open **Package review memo** to print the matrix, evidence and alternate comparisons.
- No PDFs handy? Download a **Try one** product sheet beneath the drop zone, upload it and select its spec.
- Bring your own spec: open **Specs**, draft a checklist from the example UBC Door Hardware PDF, edit/delete rows and use it for an uploaded Schlage ND sheet. Drafts are **unreviewed**, saved for this browser, and available for 14 days. Rules for other product types are disclosed separately.

An upload with no quoted values matching its selected spec says **“Doesn't match this spec”**, uses no web credits, and appears as **Not checked**. Change its spec in the Inbox before scanning.

## Measured live panel

Live run **`20261028-173729-554074`**, recorded **October 28, 2026** on the pipeline code the public endpoint serves (the later UI update changed only `web/`; see the [deploy record](docs/deployment/final-deployment.json)) (eight known cases plus the tray and watched items). The Scoreboard shows this run.

| Right calls | Problems caught | Clean cases wrongly flagged | Unnecessary notes | Passing replacements |
| --- | --- | --- | --- | --- |
| **6 / 8** | **5 / 6** | **1 / 2** | **0** | **0 / 5** |

Wrong-spec check on the same code: **0 of 14** approved (13 not applicable, 1 sent back). Average **$0.126** and **114 s** per item. This is a small known set, partly cached, not an unseen benchmark. c05 and c06 are the wrong calls.

**Run-to-run variance:** a same-day run on the earlier PR #20 code (`20261028-171142-5ca0fc`) differed only on clean case c05, which it approved with a note instead of sending back (0/2 false alarms, 1 unnecessary note). c05 flips between runs.

A same-day A/B tested Nemotron 3 Ultra (5/8, about 5× the cost per item) and reasoning on every Super step (4/8); neither ships. **The strict case evidence gate does not pass. No passing replacement was found live; no Investigator rescue is claimed.** [A/B evidence](docs/customer-feedback/accuracy-arms-20261028/README.md) · [Recorded scores](runs/recorded/20261028-173729-554074/scores.json) · [Deployment and public checks](docs/deployment/README.md)

## Models and evidence

| Component | Work |
| --- | --- |
| **Nemotron 3 Nano**, Nebius Token Factory | Sorts PDF pages |
| **Nemotron 3 Super**, Nebius Token Factory | Drafts checklists (with reasoning on), identifies draft product types, extracts quoted claims, reads manufacturer sources and writes summaries. Nemotron 3 Ultra was tested for these steps on October 28 and not adopted |
| **Tavily Search, Extract and bounded Map** | Finds and retrieves current manufacturer documents |
| **Code** | Validates quotations, compares values, applies product-type scope and owns every verdict |

In short: Nemotron 3 Nano sorts pages; Nemotron 3 Super reads data sheets, checks the manufacturer's site and writes the notes, on Nebius Token Factory; Tavily finds current manufacturer documents; code makes every decision.

Unquoted claims and web values are dropped. “Couldn't confirm” is never a failure. SpecCheck suggests alternates and shows what's still unconfirmed; only a fully checked alternate is labelled acceptable. Messages remain editable drafts and are never sent. Mock results say mock, cached live calls remain labelled, and recorded fallback says replay. Checklist drafts are unreviewed. A memo covers one run; items retried into another run are separate. The daily GitHub Actions fallback has a real October 28 report: one watched item, one discontinued product, $0.0667 / 13 credits. **No Nebius Serverless Job execution is claimed.** [Schedule, caps and measured status](deploy/nebius/recheck-job.md).

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

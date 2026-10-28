# SpecCheck — submission draft, October 28, 2026

**Track:** Best Apps and Agents. **City:** San Francisco. **Demo:** https://speccheck-wongywrongys-projects.vercel.app

## What I built

Construction submittal review is more than comparing two PDFs. A product sheet can meet yesterday's spec and still be out of date or discontinued today. SpecCheck reads the submitted pages, checks the manufacturer's live documents, and puts the quotes beside the decision.

The reviewer gets a package matrix and a short **What to send** list for each item. If the sheet only meets a requirement with a particular ordering option, the review says what to specify. Alternates are ranked with point-by-point comparisons and anything still unconfirmed. Items can go to manual review, and the package memo prints the evidence, draft notes and reviewer sign-off line.

The flow is **Inbox → Scan → Review → Outcome**. People can upload their own spec, draft checkable rules, edit or delete them, and use that unreviewed checklist for their own submittals. The PDF stays beside the findings. Nothing sends a message or approves construction work without the reviewer saving a decision.

Approved samples can be checked again against current manufacturer sources. The scheduled GitHub Actions fallback is bounded at $0.50 and 40 Tavily credits per execution; only a real stored report may supply the Outcome timestamp. No Nebius Serverless Job execution is claimed. See [setup and actual execution status](deploy/nebius/recheck-job.md).

## Why this matters

[Construction Review's industry article](https://constructionreviewonline.com/knowhow/the-hidden-cost-of-submittal-rejections-a-data-driven-analysis/) estimates 30–40% first-submission rejection, about $805 in direct cost per rejection, and two to four weeks added to procurement. These are published industry estimates, not my own research or a measured saving from SpecCheck. The [Illustrarch article supplied for context](https://illustrarch.com/articles/77575-why-submittals-get-rejected-more-often-than-pms-expect.html) could not be independently retrieved during this release, so it is not used to substantiate those numbers.

**Manual-versus-SpecCheck timing:** [Kyle to supply timed manual checks for c02, c03 and c07. No measured time saving claimed.]

**Practitioner quote:** [Kyle to supply a quote, title and permission to publish. No attributed endorsement claimed.]

## How it works

- **NVIDIA Nemotron 3 Nano on Nebius Token Factory:** page sorting.
- **NVIDIA Nemotron 3 Super on Nebius Token Factory:** quoted extraction, checklist drafting, product-type scope and manufacturer-document reading. Ultra is not used in the scan path and has not been adopted for drafting.
- **Tavily Search, Extract and bounded Map:** live source discovery and retrieval.
- **Python code:** quote gates, value comparisons, decisions, ordering-option instructions, alternate ranking and package summaries.
- **FastAPI, React, TypeScript, Vite, PyMuPDF and Tesseract:** the app, native PDF view and OCR.
- **Nebius Serverless Endpoint:** the public app, with persistent ledger, cache, uploads and runs. **Vercel:** the stable URL's rewrite to that endpoint. **GitHub Actions:** the bounded daily fallback workflow.

Models read and quote; code owns the verdict. Unconfirmed evidence stays unconfirmed. Alternates say **possible** until all checks pass. Mock, cached, replayed and unreviewed-checklist labels remain visible.

## What I measured

October 28 live recording `20261028-065522-3dd974`: **4/8 right calls, 4/6 planted problems caught, 0/2 major false alarms, 0/5 passing replacements**. All ten case/tray/watched results are valid. A separate fixed wrong-spec run approved **0/14**, with all 14 not applicable. Both use some cached calls and are small known demonstration sets, not unseen benchmarks.

The earlier October 22 panel was 6/8 calls and 5/6 problems. This release adds an unnecessary c01 note and misses c04's pipe-coverage failure. c05/c06 remain wrong calls. The strict case evidence gate fails; no passing replacement or planted-problem Investigator rescue is claimed. [Full comparison and costs](docs/customer-feedback/release-20261028/README.md).

Verification: **771 Python tests passed, 2 skipped; 17 mock browser journeys passed; presentation checks and web build passed**. The final recording charged $0.59806296 and 46 Tavily credits. Wrong-spec checks added no fresh charge. Public smoke and browser evidence must be read from the deployment record, not inferred from these local checks.

## Submission checklist for Kyle

- Supply the timing results and permissioned quote above, or remove those placeholders.
- Re-capture the existing video using [video/DELTA.md](video/DELTA.md), publish it and add its URL here and on Devpost. The previous video shows the old UI and numbers.
- Complete Devpost, select Best Apps and Agents / San Francisco, and verify the entry is submitted. Kyle's target is Thursday October 29; the recorded official deadline is October 30 at 17:00 UTC.
- Keep the public demo available through December 15, 2026, 20:00 UTC.

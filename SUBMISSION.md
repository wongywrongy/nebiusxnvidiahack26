# SpecCheck — Devpost submission (paste-ready)

**Track:** Best Apps and Agents · **City:** San Francisco · **Demo:** https://speccheck-wongywrongys-projects.vercel.app · **Code:** https://github.com/wongywrongy/nebiusxnvidiahack26 · **Video:** [KYLE: YouTube URL]

Each section below is one Devpost field. Every number comes from a file in this repo, named beside it. Text in [KYLE: …] is for Kyle to fill in or delete.

---

## Tagline

Checks submittals and says what to send instead

## Inspiration

On a construction job, the subcontractor sends a product data sheet (a "submittal") and someone on the general contractor's side checks it against the project spec before anything is ordered. It's slow, line-by-line work. The sheet can also be out of date, or the product discontinued, and nothing on the page tells you.

When I showed an early version to a GC practitioner, the feedback was simple: don't just tell me it fails, tell me what to send instead. That changed the product. Every review now ends on a short **What to send** list.

[KYLE: optional — the practitioner's exact words, their title and permission to publish. Leave this out if you don't have permission.]

## What it does

You drop in submittal PDFs and pick the spec section. SpecCheck reads the pages, pulls quoted values for each spec requirement, then checks the manufacturer's live website for a newer data sheet or a discontinued notice. You get:

- a package matrix: one row per submittal, showing whether it meets the spec, whether the sheet is current and whether the product is still made;
- a review for each item, with the PDF beside the findings, the quotes and links behind each one, and **What to send**: the exact fix, the ordering option to specify when one exists, and ranked possible alternates with what's still unconfirmed;
- an Outcome page where you save decisions or flag items for manual review, plus a printable package review memo;
- a "Check approved now" button that re-checks already-approved products against the manufacturer's current site.

You can also upload your own spec: SpecCheck drafts a checklist of checkable rules, you edit or delete rows, and you use it on your own uploads. Drafts are labelled unreviewed.

Models read and quote. Code makes every decision. A value with no matching quote is dropped. "Couldn't confirm" is never treated as a failure. Nothing is sent or approved unless the reviewer saves a decision.

## How we built it

- **Nemotron 3 Nano sorts pages; Nemotron 3 Super reads data sheets, checks the manufacturer's site and writes the notes, on Nebius Token Factory; Tavily finds current manufacturer documents; code makes every decision.** Super, with reasoning on, also drafts checklists from an uploaded spec.
- **Nebius Token Factory** through its OpenAI-compatible API. Every request is priced and reserved against a ledger before it is sent, and settled afterwards.
- **Tavily Search, Extract and a bounded Map** (20 URLs, depth 1) find and read current manufacturer documents.
- **Quote gates in code.** A claim survives only if its quote is on the cited page and the value, unit and metric are in that quote. Web values have to be quoted from the source they cite. Comparisons, verdicts, ordering options, alternate ranking and the memo are plain Python.
- **Nebius Serverless Endpoint** in eu-west1 (cpu-d3, 2 vCPU, 8 GB) runs one container: FastAPI plus the React app. A Nebius persistent filesystem mounted at `/state` holds the spend ledger, uploads, cache and runs, so they survive endpoint replacements. A Vercel rewrite gives it a stable URL.
- **GitHub Actions daily re-check** of approved items, capped at $0.50 and 40 Tavily credits per run. Its first manual run (Oct 28, 07:22 UTC) flagged the watched Lithonia troffer as discontinued with the manufacturer's quote, for $0.0667 and 13 credits. The scheduled cron fired at 15:37 UTC ([run 40717808721](https://github.com/wongywrongy/nebiusxnvidiahack26/actions/runs/40717808721)) and correctly skipped because that day's report already existed. Source: `docs/deployment/final-deployment.json`.
- Python, FastAPI, PyMuPDF and Tesseract OCR on the back end; React, TypeScript, Vite and Tailwind on the front end; Playwright for the browser checks.

## Challenges we ran into

- **The quote gates throw away a lot.** In the official run, 91 of 235 claims (39 %) and 39 of 320 web values (12 %) survived. The top reason is a web value whose quote isn't actually on the source. I kept the gates strict because a wrong quote is worse than a missing one. Source: `docs/customer-feedback/accuracy-arms-20261028/README.md`.
- **Retrieval.** Manufacturer sites often block direct downloads: Acuity returned 403 with a Cloudflare page while Tavily Extract read the same PDF. On the discontinued Lithonia notice, the replacement models are printed only inside an image. I added OCR for that image; it read the table, but no row matched the submitted configuration, so SpecCheck names no replacement rather than guessing. Sources: `FEEDBACK.md`, `docs/customer-feedback/w3-live.md`.
- **Run-to-run variance.** Two same-day live runs differ on one clean case: c05 was approved with a note in one and sent back in the other (a freshly read "10 %" minimum dimming against a ≤ 5 % rule). One-item differences between runs are noise.
- **Ultra A/B.** I tested Nemotron 3 Ultra for reading data sheets and web sources. It kept 50 % of web values versus 12 % for Super, but got 5/8 right calls against 6/8 and left 3 items invalid. One item made 471 paid requests over 24 minutes ($3.65) before the run cap stopped it. Overall cost was about 5× per item ($0.64 vs $0.126). Turning on reasoning for every Super step was worse too: 4/8, and it kept only 4 of 92 web values. The default config ships. Source: `docs/customer-feedback/accuracy-arms-20261028/README.md`.

## Accomplishments that we're proud of

- A public app that runs the full check on real manufacturer documents, with a hard spend ceiling (judging allowance $75 / 6,000 Tavily credits, $8 / 600 per day, $3 per run).
- It catches real problems a quick read misses: a fire-rating mismatch (c02), an outdated data sheet (c03) and a discontinued product (c07, from "Check approved now"), each ending on what to send instead.
- Honest output. Mock, cached, replayed and unreviewed results are labelled as such. Unconfirmed stays unconfirmed. Alternates say "possible" until every check passes.
- A wrong-spec guard: 14 documents uploaded under the wrong spec section, 0 approved.

## What we learned

- Letting code decide and making models quote is what makes the output checkable. It also shows exactly where accuracy is lost (drop reasons per gate).
- A bigger model is not automatically better. Ultra read more of the web but extracted claims less precisely and cost far more. More reasoning made the extractor terser.
- Measure everything twice. A one-item swing between runs looks like a change in accuracy when it's variance.
- Fetching current manufacturer documents is the hard part. Search, extract, blocked hosts and image-only tables matter more than model choice.

## What's next

- A larger, unseen test set from real projects, instead of my 8 known cases.
- Finding replacements: today SpecCheck suggests possible alternates but has not found a fully passing replacement (0 of 5).
- Reviewing drafted checklists with a practitioner, and more spec sections beyond firestopping and lighting.
- Exporting the memo into the tools GCs already use.

## Try it

1. Open https://speccheck-wongywrongys-projects.vercel.app (no login).
2. In the Inbox, add the sample submittals and click **Scan**. A live scan takes a minute or two per item.
3. Read the package matrix, open a row, and read **What to send**.
4. Save decisions, open **Outcome**, and try **Check approved now** on the approved Lithonia troffer.
5. Click **Package review memo** and print it.
6. No PDFs handy? Download a **Try one** product sheet under the drop zone, upload it and pick its spec.
7. Bring your own spec: open **Specs**, draft a checklist from the example UBC Door Hardware PDF, edit it, and use it on a Schlage ND sheet.
8. **Scoreboard** shows the recorded live panel.

## Built With

nvidia-nemotron · nebius-token-factory · nebius-serverless-endpoints · tavily · python · fastapi · pymupdf · tesseract · react · typescript · vite · tailwindcss · docker · github-actions · vercel · playwright

---

## Positioning (for the description or a judge's question)

Procore, Nomic, Trunk Tools and BuildSync do compliance tables and deviation reports. SpecCheck's difference: it checks the manufacturer's live web for newer sheets and discontinued products, says what to send instead (ordering options and ranked alternates), and gives a package view with a printable memo.

## Problem size (industry estimates, not my measurements)

- [Construction Review: the hidden cost of submittal rejections](https://constructionreviewonline.com/knowhow/the-hidden-cost-of-submittal-rejections-a-data-driven-analysis/) estimates 30–40 % of first submissions are rejected, at about $805 direct cost per rejection, adding two to four weeks to procurement.
- [Illustrarch: why submittals get rejected more often than PMs expect](https://illustrarch.com/articles/77575-why-submittals-get-rejected-more-often-than-pms-expect.html), cited for context only. I could not retrieve it independently, so none of its numbers are used.
- [KYLE: your own timing — e.g. minutes to check c02, c03 and c07 by hand versus with SpecCheck. Leave it out if not measured. No time saving is claimed without it.]

## Official numbers

Live run `20261028-173729-554074`, recorded October 28 on the deployed code (8 known cases):

| Right calls | Problems caught | Clean cases wrongly flagged | Unnecessary notes | Passing replacements |
| --- | --- | --- | --- | --- |
| 6 / 8 | 5 / 6 | 1 / 2 | 0 | 0 / 5 |

Wrong-spec check on the same code: 0 of 14 approved (13 not applicable, 1 sent back), run `20261028-183608-dfa1b9`. Average cost per item is $0.126 (model + web, priced uncached), with p50 / p90 item time of 75 s / 230 s. Sources: `runs/recorded/20261028-173729-554074/scores.json`, `docs/customer-feedback/accuracy-arms-20261028/README.md`.

Variance: a same-day run on the earlier code (`20261028-171142-5ca0fc`) differed only on c05: approved with a note instead of sent back, giving 0/2 false alarms and 1 unnecessary note. c05 flips between runs.

Not claimed: a passing replacement, an Investigator rescue, a Nebius Serverless Job run, a human study or time saving, or Ultra in production. This is a small known set, not an unseen benchmark, and the strict case-evidence gate does not pass.

---

## Sponsor feedback fields

Measured rows only. Sources are `FEEDBACK.md` and `docs/customer-feedback/accuracy-arms-20261028/README.md`.

### Nebius (Token Factory, Serverless Endpoint, filesystem)

- **Used for:** all model calls (Nemotron 3 Nano and Super) through Token Factory's OpenAI-compatible API; hosting the public app on a Serverless Endpoint in eu-west1 with a persistent filesystem at `/state`.
- **What worked:** the persistent filesystem kept the ledger, uploads and re-check report across every endpoint replacement; today's swap read exactly $1.82596578 / 388 credits before and after today's swap. Endpoint creation from a GHCR digest with MysteryBox secret references worked from the CLI. In captured live calls we saw no 429s.
- **Needs work:** eu-north1 rejected a 2-vCPU endpoint with `ResourceExhausted: compute.instance.non-gpu.vcpu (limit 0)`; eu-west1 had 200 vCPUs free. Browser SSO for the CLI expired mid-release, and there is no `iam login` command (auth happens on the first request). Two Nano calls hit our 180 s client timeout during a seven-item scan on Oct 27, and their reserved cost stayed held until settled.
- **Onboarding:** the OpenAI-compatible API needed no new SDK for model calls. Finding a region with CPU quota took an authenticated quota listing.
- **Would use again?** Yes.

### NVIDIA (Nemotron 3 Nano, Super, Ultra)

- **Used for:** Nano sorts PDF pages; Super extracts quoted values, reads manufacturer sources, writes notes and (with reasoning) drafts checklists. Ultra was tested in an A/B only.
- **What worked:** the default config (Nano + Super) got 6/8 right calls and 5/6 problems caught at $0.126 per item. Super with reasoning drafts usable checklists from a real spec PDF.
- **Needs work:** with reasoning on for every step, Super got 4/8 and kept 4 of 92 web values, using 328,819 reasoning tokens. Ultra kept 50 % of web values versus 12 %, but got 5/8 with 3 invalid items. One Ultra reply hit the 65,536 max output tokens, and one item made 471 paid requests ($3.65) before the run cap stopped it, about 5× Super's cost per item.
- **Onboarding:** used through Token Factory by model ID (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/Nemotron-3-Ultra-550b-a55b`); no separate NVIDIA account.
- **Would use again?** Yes, Nano and Super. Ultra only after fixing the runaway request loop.

### Tavily (Search, Extract, Map)

- **Used for:** finding and reading current manufacturer data sheets and discontinued notices.
- **What worked:** Extract read an Acuity PDF (4,836 chars) where a direct download got 403 from Cloudflare. The daily re-check found the Lithonia discontinued notice for 13 credits.
- **Needs work:** one Extract of a linked spec PDF returned no readable document but was still charged 1 credit. A product-page fallback returned a general guide without the product identifier. Usage for one request was not itemized, so we settled it at the reserved amount.
- **Onboarding:** one API key. Per the Search docs, domain preference needs a non-empty `include_domains`.
- **Would use again?** Yes.

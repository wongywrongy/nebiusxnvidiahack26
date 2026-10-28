# Video brief for Kyle — SpecCheck, October 28 release

**Length:** aim for 2:00–2:30; 2:55 is the hard limit. Upload to YouTube as **Public**, then paste the URL into SUBMISSION.md and Devpost.

**Record from:** https://speccheck-wongywrongys-projects.vercel.app in a fresh private browser window at 1440×1000, browser zoom 100 %, no admin token. Live scans take minutes; record them in full and speed them up in the edit, with a small "sped up" label.

**Say these names aloud at least once:** Nemotron 3 Nano, Nemotron 3 Super, Nebius Token Factory, Tavily.

**Before narrating a catch, check the screen.** Your scan is a new live run. If an item's decision differs from what's written below, narrate what the screen shows, or skip that item. Never speak a number or finding that isn't visible. Today's public tray scan is listed in `docs/release-final/public/d-trace.json`.

## Frames to avoid

- Long candidate URLs, e.g. the alternate source link on c03/c07. Crop them, or zoom on the text above them.
- PDFs while they're still loading (grey page, spinner). Cut to after the page renders.
- Matrix cells reading **Unknown** (c02 "current sheet" and "still made" were Unknown in the official run). They read as broken. Frame the row's decision and spec columns, or zoom past them.
- Anything mentioning Nemotron 3 Ultra, the Investigator, "passing replacement" or a Nebius job run. None of these are claimed.
- Admin or developer pages, terminal windows, `/api/...` JSON.

## Beats

| # | Time | Screen and URL | Action | Zoom on | Overlay (≤ 8 words) | Voiceover |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0:00–0:07 | Inbox, `/` | Hold on the page title | App name | Checks submittals against the spec and web | "SpecCheck checks construction submittals against the spec and the manufacturer's live website, then tells you what to send instead." |
| 2 | 0:07–0:20 | Specs (`/#specs` from the header) → open the **07 84 00 Firestopping** spec PDF; then a tray data sheet | Show the spec page, then the product sheet | One spec rule, then the matching value on the sheet | Spec says this. Data sheet says that. | "Before anything's installed, the subcontractor sends a submittal — the product's data sheet — and someone on the GC side checks it against the project spec, line by line." |
| 3 | 0:20–0:42 | Inbox `/` → **Add … to the inbox** for each tray item → **Scan 7 submittals** → **Scan complete** matrix | Add, scan (sped up), land on the matrix | The matrix rows and decision column | Live scan on Nebius Token Factory | "I add a sample package and scan. Nemotron 3 Nano on Nebius Token Factory sorts the pages. Nemotron 3 Super reads each data sheet and quotes every value, and Tavily finds the manufacturer's current documents." |
| 4 | 0:42–0:58 | Matrix → click the **c02** row (Firestop system, floor penetration) → Review | Open the row | The failing finding, then **What to send** | Doesn't meet spec | "This firestop system lists a 2-hour F rating but a 0-hour T rating, and the spec needs both. What to send: a listed system rated T and F at 2 hours." |
| 5 | 0:58–1:14 | Matrix → **c03** (Firestop sealant, cable penetrations) → Review | Open the row | "Data sheet is out of date", then **What to send** | Outdated data sheet | "This sheet still describes the product, but the manufacturer's current sheet, dated January 2026, changed the service temperature. What to send: the current data sheet, plus a possible alternate with what's still unconfirmed." |
| 6 | 1:14–1:34 | Save decisions → **Outcome** → **Check approved now** on the approved **Lithonia 2TL4** (c07) | Click and wait (sped up) | The discontinued alert and its quote, "As of June 30th, 2024, the TL family will be discontinued", then **What to send** | Approved last year. Discontinued now. | "This troffer was approved in 2024. Check approved now finds the manufacturer's discontinued notice and quotes it. What to send: a current product that meets the spec." |
| 7 | 1:34–1:56 | **Specs** → Section `08 71 00`, title `UBC Door Hardware` → **Draft a checklist from a spec PDF** (download "UBC Door Hardware 08 71 00" from **Try one** first) → delete a row → **Use this checklist for my uploads** → Inbox → upload "Schlage ND Series Grade 1 locks" (also under **Try one**) → scan → Review | Draft (sped up), edit, scan | The **unreviewed** label, the ND series rule passing, and the collapsed "rules for other product types" line | Bring your own spec | "You can bring your own spec. Super drafts a checklist of checkable rules, I edit it, and run it on a Schlage lock sheet. Only the lockset rules apply. The rest are set aside, not failed." |
| 8 | 1:56–2:08 | Scan page → **Package review memo** (opens `/memo/<your run id>`) → **Print or save as PDF** | Open, scroll, open print preview | One point-by-point alternate table and the sign-off line | One memo for the whole package | "The package memo puts the matrix, the evidence and the draft notes in one printable page for the file." |
| 9 | 2:08–2:22 | **Scoreboard** (`/#scoreboard`) | Hold | The four numbers | 6/8 right · 5/6 caught · 1/2 false alarms | "On eight known test cases, the recorded live run made 6 of 8 right calls and caught 5 of 6 planted problems. It wrongly flagged 1 of 2 clean cases, and it hasn't found a fully passing replacement yet." |
| 10 | 2:22–2:30 | Back to the Inbox, URL bar visible | Hold | URL | Models read and quote. Code decides. | "Models read and quote. Code decides. Try it at speccheck-wongywrongys-projects.vercel.app." |

## About the "Specify option" beat (c05 EZ1)

**Leave it out.** In the official run, c05 is the false alarm: it's sent back for a freshly read 10 % minimum dimming, with no Specify line. The only ordering option in that run is on c07 (EZB, dims to 0.1 %), and the memo drops it because c07 is discontinued. The c05 "Specify EZ1" screen came from a different, older run, so showing it next to these numbers would mix runs. Source: `runs/recorded/20261028-173729-554074/results/c05.json` and `c07.json`; ordering-option logic in `api/pipeline/package.py`.

If you want an extra beat in its place (adds ~10 s): **Flag for manual review** on any item, then show it in the Outcome bucket. Overlay: "Unsure? Flag it for a person."

## Where each number and quote comes from

| On screen or spoken | Source |
| --- | --- |
| 6/8 right calls, 5/6 caught, 1/2 wrongly flagged, 0/5 passing replacements, 0 unnecessary notes | `runs/recorded/20261028-173729-554074/scores.json` (served by `/api/scores` and the Scoreboard) |
| c02: T rating 0 Hr vs F rating 2 Hr; "A listed system with T = F (2 Hr)" | `runs/recorded/20261028-173729-554074/results/c02.json` |
| c03: current source dated January 2026, differs on highest service temperature | `runs/recorded/20261028-173729-554074/results/c03.json` |
| c07: "As of June 30th, 2024, the TL family will be discontinued"; approved 2024-03-12 | `runs/recorded/20261028-173729-554074/results/c07.json`; `/api/project` watched item |
| Model roles (Nano sorts pages, Super reads, checks and writes) | `/api/health` models; `docs/deployment/final-deployment.json` |
| Variance (only if asked): a same-day run differed on c05 alone | `docs/customer-feedback/accuracy-arms-20261028/README.md` |

The scan you record is a new live run, so its per-item time and cost will differ from the recorded run's. Don't quote seconds or dollars from your own scan.

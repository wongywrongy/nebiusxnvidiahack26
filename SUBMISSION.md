# SpecCheck submission — October 27, 2026

Kyle submits **Thursday October 29**. The [official deadline](https://nebiusglobalaihackathon.devpost.com/rules) is **Friday October 30, 10:00 AM PDT / 17:00 UTC**. Keep the public app up through **December 15, 20:00 UTC**.

## Current state

- PR #12 and playground PR #13 are merged into `master`. Historical G2–G5, controller/authority and blind-package work is closed.
- One-container Nebius endpoint in eu-west1 is live with persistent state. The eu-north1 attempt failed only on regional CPU quota (0 versus 2 requested); eu-west1 has capacity. Fly login is stopped.
- [No-admin smoke](docs/deployment/smoke.txt) and [all five public private-browser workflows](docs/playground/public/README.md) passed. The approved UI polish is being redeployed; final URL/evidence will be recorded after that replacement.
- Judging allowance $75 / 6,000 credits; daily $8 / 600, run $3, concurrency 2. [Accounting and evidence](docs/deployment/README.md).
- 767 Python tests passed / 2 skipped; unchanged raw mock panel and clean production build. Presentation and browser checks cover the three polish items.
- Recorded October 22 live panel remains **6/8 right calls, 5/6 problems, 0/2 major false alarms, 0/5 passing replacements**, run `20261022-181611-a9d0b5`. This is a small known set, partly cached. Public workflow runs are not a new eight-case accuracy benchmark.

## Kyle's 2:45 video

Use the actual public app. Show its Live label and source quotes; keep cached calls/replay labels visible when relevant. [Public tray and UBC/Schlage run IDs](docs/playground/public/README.md) are the real run references.

| Time | Footage / narration |
| --- | --- |
| 0:00–0:15 | “Construction submittals stall when product sheets disagree with the spec or today's manufacturer documents. SpecCheck reads the evidence; code decides.” |
| 0:15–0:55 | Inbox → Add all samples → Scan → Review. Cut the wait visibly; full trays take minutes. Open a quoted finding beside the native PDF, then save a decision and show Outcome. |
| 0:55–1:15 | Drop the off-topic PDF: Doesn't match this spec; zero Tavily credits; Not checked. |
| 1:15–2:20 | Specs → UBC PDF → edit/delete draft rows → Use this checklist → upload Schlage → select draft → Scan → Review → Outcome. Show ND passing and other product types collapsed. Drafts are unreviewed; save at most 30 rows. |
| 2:20–2:45 | Show the recorded live panel and the per-call trace: Nano sorts pages; Super reads/drafts/investigates; Tavily retrieves sources; code decides. State that no passing replacement was found live. End on the public URL. |

No cloud job or nightly schedule was run for this submission. Do not show a job execution claim. No message is sent: reviewer messages remain drafts.

## Remaining owner work

1. Record/edit and publish the public video; put its link in the README and Devpost.
2. Complete the Devpost form, repo and demo links, track selection and tool-feedback fields using [observed feedback](FEEDBACK.md).
3. Submit Thursday October 29. Verify the entry is submitted, not merely saved as a draft.

Known product limits: unreviewed drafts may exceed the prompt's row limit or need semantic edits; the UBC example produced 65 rows and was trimmed to 30. Shared untyped rules still apply. Large scans and uncertain manufacturer sources can take minutes and leave honest couldn't-confirm notes. No passing replacement or Investigator rescue is claimed.

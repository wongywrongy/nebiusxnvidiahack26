# Mock walkthrough — October 13, 2026

Captured from the local app with `.env` disabled, empty provider keys and outbound HTTP blocked. All visible
model/web answers are fixtures; token counts, model costs and Tavily credits are estimates. Source PDFs and
local Tesseract/rendering are real. The archive here is **local disk**, not Nebius Object Storage. No cloud job
was created. These are offline verification artifacts, not screenshots of a deployed service.

| Screen | Capture | Observed behavior |
| --- | --- | --- |
| Inbox | [Desktop](inbox-desktop.png) | Six available samples, explicit mock label, one primary Scan button |
| Scan | [Investigating](scan-investigating-desktop.png), [complete](scan-desktop.png) | Streaming stages; fixture usage explicitly estimated; four returns and two approvals |
| Review | [Investigator trace](review-investigation-desktop.png) | Four bounded fixture steps, quoted revision, unconfirmed VOC, archived-copy link; browser-only draft |
| Outcome | [Desktop](outcome-desktop.png), [mobile](outcome-mobile.png) | Saved decisions, in-process approved-item check, sample discontinuation; one primary button; cloud action hidden |
| Specs | [Desktop](specs-desktop.png) | Two fixture checklists explicitly not reviewed; free-text section/title controls, drafting live-only |
| Scoreboard | [Desktop](scoreboard-desktop.png) | Mock 8/8; 48/48 claims and 19/20 web values retained; small known answer-key limitation visible |
| PDF upload | [Review](upload-review-desktop.png) | One-page synthetic PDF yields unconfirmed findings and an honest draft, without an error |

The browser walkthrough reviewed all six items, edited a draft, reloaded and checked that the draft survived
without another scan, saved a substitution request and reloaded, opened both reference pages, uploaded
`tests/data/smoke.pdf`, then used Start over and reloaded to verify an empty inbox. It made exactly three mock
scans and reported zero browser page errors. Layout checks passed at 1440, 768 and 390 pixels: no document
horizontal overflow, header links on the first row from 768 pixels up, and at most one primary action.
Wide reference tables retain their own horizontal scroll area on phones.

Separately, Package C's offline fake-CLI browser exercise showed queued → starting → running → done and a
matching report with a job name and duration. Those state strings were explicitly configured test values;
only `COMPLETED` is assumed from Nebius documentation. A real console screenshot is still an owner TODO in
[the README](../../README.md#ai-cloud-in-the-workflow).

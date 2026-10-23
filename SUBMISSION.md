# SpecCheck submission package

Prepared for Best Apps and Agents, Nebius x NVIDIA Global AI Hackathon. Official requirements checked
on October 23: submission Friday October 30, 2026 at 10:00 AM PDT / 17:00 UTC; judging December 1–15.
[Official-source requirements and outstanding deliverables](docs/judge-readiness/submission-requirements-20261023.md). The original October 22 production
target has passed without a deployment. First live pass completed October 21–22; refinement is ongoing.
Deployment and nightly cloud execution remain unverified. Live evidence is separate from offline results.

## Submission description

SpecCheck helps a construction reviewer catch a submittal that misses the project spec or relies on an outdated
product sheet. NVIDIA Nemotron 3 Nano sorts pages; Nemotron 3 Super reads requirements and quoted values,
investigates missing documents with bounded tools, and drafts the reviewer’s message. Both model tiers use
Nebius Token Factory. Tavily retrieves manufacturer evidence. Code checks the quotes and computes each verdict.
An unsupported claim becomes “couldn’t confirm.” A suggested replacement must pass the same checks.

The app follows Inbox → Scan → Review → Outcome. A Nebius Serverless Endpoint can host it, Serverless Jobs can
re-check the bundled watch list, and an archive can retain source evidence. Job allowances, receipts and
publication belong to a private controller authority. The protocol is implemented and tested with a fake CLI
and isolated local wallets, including pinned transfer/cutover and interrupted-import recovery. Actual remote
authority migration and hosted durability remain unfinished. Deployment
requires owner approval, followed by agent-executed validation. Review messages remain drafts in the browser.

## Demo recording plan

Keep the finished public YouTube video under three minutes and verify its actual encoded duration. Use
final validated footage with the run ID, date and live/cached/replay mode visible. Say **Nebius Token
Factory** and **NVIDIA Nemotron Nano and Super** aloud while showing their actual roles. Do not promise
a passing replacement or primary rescue unless the captured evidence demonstrates one.

1. **Inbox:** point out the mode label. Add the seven available tray PDFs. In mock mode explain that the
   product documents are real but the model/web answers are fixtures; no external checks are taking place.
2. **Scan:** run once. Point out streaming stages and Investigator steps actually present in the captured run. Show
   estimated counts in mock mode; quote paid usage only from an actual live trace.
3. **Review:** show a quoted mismatch and the source PDF. The live run found no passing replacement; show the unknown candidate checks without claiming success. Open the trace to show
   Nemotron’s reading tasks and code’s verdicts. Edit a message and save the decision; no email is sent.
4. **Outcome:** show saved return decisions and approvals. Click **Check approved now** to re-check them plus
   the sample watched troffer. The live local walk found the watched TL discontinuation. No passing live replacement was found.
5. **Cloud proof, only after approved deployment validation:** launch through the authenticated controller, then show its real console state,
   matching job-name report and archived source. Do not substitute a fake CLI capture for cloud execution.
6. Open **Specs** and **Scoreboard** from the header. Explain the two reviewed-section targets, public draft
   behavior, quote-gate counts and the small, known answer key. Reload to show saved drafts; **Start over**
   clears this browser’s session. A new one-page PDF produces honest unconfirmed findings in mock mode.

## Reproducible offline evidence

```bash
SPECCHECK_MODE=mock python -m pytest -q
SPECCHECK_MODE=mock python scripts/eval.py --out /tmp/speccheck-final.json
cd web && npm run build
```

The original fixture baseline yielded 8/8 calls, 6/6 planted problems, 0/2 major false alarms and 2/5 passing
replacements. The current selection/evidence policy yields **6/8, 5/6, 0/2 and 0/5** against the unchanged key,
with 46/65 claims and 8/20 web values retained. Kyle approved the disclosed selection-policy disagreements
for continued engineering; the strict release gate still fails. The current suite passes 657 tests (2 skipped).
Both workflows for tested source `e1a4c2e` pass Python/mock, presentation/build and mock browser journey/failure checks. These are measured demonstration-set results, not live
accuracy or an unseen benchmark. Respx/fake-CLI tests
cover paid-call boundaries, profile redaction, job create/poll, storage retention and the deployment smoke
script. Real local Tesseract is exercised when installed. An eight-week soak has not been performed.

Browser walkthrough captures are in [docs/mock-walkthrough](docs/mock-walkthrough/README.md). They are all
labelled mock and are not a replacement for a real console screenshot.

## Current targeted live checkpoint — 2026-10-23

Run `20261023-095053-630ac4` checks c03/c07 only: **2/2 calls and problems, 0/2 passing replacements**,
zero invalid items or warnings. It adds **$0.0792648 / 2 credits**; cumulative local accounting is
**$3.36648982 / 490**. [Actual trace, before/after, intermediate failures and reproduction](docs/judge-readiness/document-links-20261023/README.md).
The measured profile uses a 65,536-token cap and concurrency 1 after an invalid output-limit item; it is
partly cached evidence, not a current full-set/blind score or release approval. The earlier
[unpublished validated-source image](docs/judge-readiness/document-links-20261023/image/README.md)
freezes `061cf9d` and excludes newer shared status-timing work. Final source/configuration validation,
registry identity, owner approval and hosted proof remain pending.

## Links and judge access to finalize

The project demo/test-build URL and public YouTube URL are pending. The final submission must identify
the released commit/build and the ordinary reviewer path. Judges should not need provider credentials or
an admin token for that path. Prove public access with the final artifact and the approved operating plan
through **December 15, 2026, 20:00 UTC**. The bounded initial cloud trial alone does not establish that access.
No URL, uptime, grant entitlement, deployment or submission is inferred from this draft.

Suggested Built With fields for the verified application: **Nebius Token Factory, NVIDIA Nemotron,
Tavily, Python, FastAPI, Pydantic, PyMuPDF, React, TypeScript and Vite**. Add actual AI Cloud execution only
after commissioning evidence exists. The accepted Endpoint + Jobs work remains in scope.

## Provider feedback draft for owner review

Token Factory runs Nano for page triage and Super for structured reading, source verification, native-tool
investigation and reviewer drafts. The first live spikes listed both configured model IDs, returned
schema-valid JSON and produced a native tool call with JSON arguments. Both thinking-off fields were
accepted together; their independent effect was not established. There is no measured end-to-end
onboarding duration or claim about Kyle's personal console experience.

Useful behavior: structured reads and tool calls work at the documented boundaries. Friction: even with
thinking off, extraction can be verbose, omit evidence or misread scope and bounds. A returned JSON object
is not proof of a correct statement. Exact page quotes, identity, numeric/unit and selection checks remain
necessary. Historical cached-input quantities were not retained, so computed versus billed dollars cannot
be fully reconciled from those logs.

Tavily retrieved a manufacturer PDF that direct HTTP received as a Cloudflare response, but the outcome
is URL-specific. Some responses needed native-PDF or linked-sheet fallback. Usage metadata now drives
accounting; the historical/local/dashboard difference is unresolved and accounting stays conservative.
AI Cloud endpoint/job execution has not been performed: local images, fake CLI tests and synthetic wallets
are not evidence of cloud onboarding, IAM or hosted durability.

Engineering recommendation for Kyle's review: continue Token Factory and Tavily for bounded reading and
retrieval with code-owned decisions and explicit failure reporting. Revisit the cloud assessment after the
approved live deployment proof. [Dated observations, redacted requests/responses and repros](FEEDBACK.md)
support this draft; Kyle reviews the final feedback and submits it through the owner account.

## Owner sign-offs and access

- Review gate evidence, source/answer-key conflicts and independently prepared blind labels. Require submitted
  selected configurations rather than inferring them from catalog examples.
- Read account billing/credit-expiry details unavailable to the agent. Confirm scope and date; do not share keys.
- Approve a concrete immutable-image, storage, IAM, cost and rollback plan before any cloud resources are created.
- Provide private account access/configuration where required. The agent owns deployment execution, restart and
  storage tests, paid smoke checks, manual/scheduled job verification, screenshots and documentation after approval.
- Approve final claims, demo/video and release PR, then submit through the owner account. See
  [the full ownership ledger](docs/judge-readiness/ownership.md). No deployment, nightly-execution or cost-saving
  claim is made. The historical known-set live panel remains 6/8, 5/6, 0/2 and 0/5.

## First live pass — 2026-10-22

Recorded run: `20261022-181611-a9d0b5`, c01–c08 plus all public tray/watched samples, cases-only scoreboard.
Live cases 6/8; samples 1/4; no passing live fixes. The original mock panel remains 8/8, 6/6, 0/2, 2/5.
Local walk, public unseen-PDF upload, capped full-tray replay and final smoke passed on port 8001 (8000 was
occupied by another project). Screenshots and exact commands are in [the judge walk](docs/live-first-pass/judge-walk/README.md).
The recording reuses cached live provider responses; do not present its warm latency as a cold benchmark.
Local spend: $1.058605 / 298 Tavily credits. Billing precision/scope limitations and the three-credit dashboard
difference are documented in [the first-pass notes](docs/live-first-pass.md). Deployment recommendation: **no**
until the documented currency/configuration misses and replacement limitations are addressed.

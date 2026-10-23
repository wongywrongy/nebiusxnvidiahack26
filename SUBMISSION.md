# SpecCheck submission package

Prepared for Best Apps and Agents, Nebius x NVIDIA Global AI Hackathon. Owner-provided dates:
submission Friday October 30, 2026 at 10:00 AM PT; judging December 1–15. The original October 22 production
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

## Three-minute demonstration

1. **Inbox:** point out the mode label. Add the seven available tray PDFs. In mock mode explain that the
   product documents are real but the model/web answers are fixtures; no external checks are taking place.
2. **Scan:** run once. Point out streaming stages and the bounded Investigator on the Hilti sample. Show
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
with 48/65 claims and 8/20 web values retained. Kyle approved the disclosed selection-policy disagreements
for continued engineering; the strict release gate still fails. The current suite passes 560 tests (2 skipped).
Eight mock browser journey/failure tests passed at the preceding frontend checkpoint. These are measured demonstration-set results, not live
accuracy or an unseen benchmark. Respx/fake-CLI tests
cover paid-call boundaries, profile redaction, job create/poll, storage retention and the deployment smoke
script. Real local Tesseract is exercised when installed. An eight-week soak has not been performed.

Browser walkthrough captures are in [docs/mock-walkthrough](docs/mock-walkthrough/README.md). They are all
labelled mock and are not a replacement for a real console screenshot.

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

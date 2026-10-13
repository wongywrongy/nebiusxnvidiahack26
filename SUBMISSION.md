# SpecCheck submission package

Prepared for Best Apps and Agents, Nebius x NVIDIA Global AI Hackathon. Owner-provided dates:
test deployment October 16–17, production October 22, submission Friday October 30, 2026 at 10:00 AM PT;
judging December 1–15. All implementation validation below is offline. No live provider keys or credits were used.

## Submission description

SpecCheck helps a construction reviewer catch a submittal that misses the project spec or relies on an outdated
product sheet. NVIDIA Nemotron 3 Nano sorts pages; Nemotron 3 Super reads requirements and quoted values,
investigates missing documents with bounded tools, and drafts the reviewer’s message. Both model tiers use
Nebius Token Factory. Tavily retrieves manufacturer evidence. Code checks the quotes and computes each verdict.
An unsupported claim becomes “couldn’t confirm.” A suggested replacement must pass the same checks.

The app follows Inbox → Scan → Review → Outcome. A Nebius Serverless Endpoint can host it, Serverless Jobs can
re-check the bundled watch list and run evaluations, and a mounted Object Storage bucket can retain evidence,
watch reports and scores. These integrations are implemented and tested with a fake CLI and local disk;
their live deployment is still the owner’s verification step. Review messages remain drafts in the browser.

## Three-minute demonstration

1. **Inbox:** point out the mode label. Add the six available sample PDFs. In mock mode explain that the
   product documents are real but the model/web answers are fixtures; no external checks are taking place.
2. **Scan:** run once. Point out streaming stages and the bounded Investigator on the Hilti sample. Show
   estimated counts in mock mode; quote paid usage only from an actual live trace.
3. **Review:** show a quoted mismatch, the source PDF and a replacement that passed. Open the trace to show
   Nemotron’s reading tasks and code’s verdicts. Edit a message and save the decision; no email is sent.
4. **Outcome:** show saved return decisions and approvals. Click **Check approved now** to re-check them plus
   the sample watched troffer. The fixture demonstrates discontinuation evidence and a checked replacement.
5. **Cloud proof, only after owner validation:** use the secondary job link, then show its real console state,
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

The fixture evaluation yields 8/8 correct calls, 6/6 planted problems caught, 0/2 clean packages falsely flagged
and 2/5 passing replacements. Quote gates retain 48/48 extracted claims and 19/20 web values: 0% and 5% dropped.
These are measured demonstration-set results, not live results or an unseen benchmark. Respx/fake-CLI tests
cover paid-call boundaries, profile redaction, job create/poll, storage retention and the deployment smoke
script. Real local Tesseract is exercised when installed. An eight-week soak has not been performed.

Browser walkthrough captures are in [docs/mock-walkthrough](docs/mock-walkthrough/README.md). They are all
labelled mock and are not a replacement for a real console screenshot.

## Owner completion checklist

- Follow [the Nebius deployment guide](deploy/nebius/README.md): check credit expiry, configure the service
  account, MysteryBox selectors and bucket, test for one day, delete that endpoint, then deploy production.
- Run `python scripts/smoke.py "$SPECCHECK_URL"` once against the live test deployment. It shares one run’s USD
  cap and one item’s Tavily allowance across c01 and the tiny PDF; the command spends real tokens/credits.
- Submit one real re-check, observe its actual state strings, and fill the state-map TODOs. Confirm the
  report/job-name link, bucket archive retrieval, callback-secret refresh and report persistence after restart.
- Add a real console screenshot to the README and commit the first real `runs/watch/latest.json` fallback.
  Record live runs only from actual execution; keep credentials, cache files and downloaded PDFs out of Git.
- Enable the nightly workflow only after the test job succeeds. Avoid overlapping app and scheduled launches;
  per-process budgets are not an account-wide cloud spending limit.
- Replace the README’s live URL and video placeholders. Check the demo without an admin token, then submit
  the video, repository link, deployment URL and only observed feedback. [FEEDBACK.md](FEEDBACK.md) separates
  docs review from offline tests. No live accuracy, latency or cost-saving claim is available yet.

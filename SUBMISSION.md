# SpecCheck: judge playground, public demo, video

Current plan: October 27, 2026. This replaces the October 13 handoffs and the G2–G5 readiness process.
The repository’s default branch is `master` (called “main” in conversation). PR #12 was merged at
`4105e55`; `feat/playground` starts there and includes `3176ec9` and the owner-run hold-resolution command.
No controller, authority-transfer, blind-package, lease or private-wallet development remains in scope.
Existing implementation and historical evidence stay in the repository.

Kyle submits **Thursday October 29**. The [official deadline](https://nebiusglobalaihackathon.devpost.com/rules)
is Friday October 30 at **10:00 AM PDT / 17:00 UTC**. Keep the public demo available through
**December 15 at 20:00 UTC**. The [official FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs)
permits hosting the app elsewhere while calling NVIDIA models on Nebius Token Factory; promotional
Token Factory credits do not establish a separate AI Cloud grant.

## What is established

- Runtime: NVIDIA Nemotron 3 Nano for page triage; Nemotron 3 Super for checklist drafting, quoted
  extraction, manufacturer-source reading, bounded native-tool investigation and report prose.
  All model calls go through Nebius Token Factory. Code owns every verdict.
- Tavily Search, Extract and bounded Map retrieve manufacturer evidence. Missing or unquoted evidence
  stays unconfirmed. Models never turn that uncertainty into a failure.
- Recorded live run `20261022-181611-a9d0b5`, October 22: **6/8 right calls, 5/6 problems caught,
  0/2 major false alarms, 0/5 passing fixes**. This is a small known set, partly cached, not an unseen
  accuracy benchmark. No passing live replacement or Investigator rescue is claimed.
- At `574299b`: **723 Python tests passed, 2 skipped**; web production build clean; current raw mock
  panel **6/8, 5/6, 0/2, 0/5**. Mock results are fixture answers and incur no provider spend.
- Playground checks on October 27: **741 Python tests passed, 2 skipped; 12 Chromium journeys passed; presentation checks and production build passed**. The raw mock panel remains unchanged. Draft generation in the browser regression is synthetic, and all provider-adapter tests use intercepted HTTP.
- PR #12 is merged. Playground implementation is on `feat/playground`; its live walkthrough, public deployment and final video are still pending.
- Local cumulative accounting: **$3.36648982 model spend, 490 settled Tavily credits, one held credit**.
  Kyle reported dashboard totals of 485 credits and approximately $3; those totals do not identify the
  held request’s charge. The hold stays intact. Kyle asked to continue with unpaid work; paid work remains blocked until actual usage is resolved.

## Finish in this order

| Work | Completion evidence | State |
| --- | --- | --- |
| Phase 0: owner-run `resolve-hold`, merge live branch | Tested CLI, PR #12 merged; ledger has no holds and permits paid calls | CLI and merge done; ledger still has one hold and blocks paid calls |
| 1. Off-topic guard | Zero matching requirements yields `not_applicable`; neutral “Doesn’t match this spec”; no web/fix calls; Outcome “Not checked” | Implemented; mock/respx checked |
| 2. Upload spec choice | Inbox select; upload-only `PATCH /api/inbox/{id}` validates and persists spec before scan | Implemented; persistence and refusal tests pass |
| 3. Bring your own spec | Draft → edit/delete rows → save unreviewed checklist → assign to upload → full pipeline → Review/Outcome | Implemented; synthetic browser loop checked, live proof pending |
| 4. Try-one PDFs | 3–4 new manufacturer products plus another-division spec/product pair; HTTPS downloads and readable page counts shown to Kyle | Links verified from this machine; UI checked |
| GATE 1: local live walkthrough | Screenshots, run IDs, trace and actual cost for a–e below; Kyle approves before merge | Pending |
| Phase 2: one-container public demo | Approved host cost/expiry, judging allowance initialized, live health, smoke and private-window a–e | Pending |
| GATE 2: public evidence and freeze | Public URL, smoke output, screenshots, spend; hotfixes only afterward | Pending |
| Phase 3: recording and submission | One deployed tray + BYO run; README first screen; observed feedback; public YouTube video and Devpost | Pending |

### Playground acceptance

Keep Inbox → Scan → Review → Outcome, one orange action per main screen, header links for Specs and
Scoreboard, and the existing CSS tokens. No fifth step or redesign.

1. Detect off-topic documents **after quoted extraction and the code spec check**: no requirement has a
   matched value. Return `not_applicable`, skip web and replacements, and state “None of the N rules in
   <section title> found a value in this document. Pick a different spec for it in the Inbox.” The trace
   records the section and 0/N matches. Preserve c01–c08 and s1–s4 mock decisions.
2. Keep keyword classification as the default only. Uploads can select either reviewed section or one of
   this browser’s saved draft IDs. Reject tray changes, unknown specs and changes after scan starts.
3. Public `POST /api/checklists` validates the existing Checklist shape, a `00 00 00` section, title 1–160,
   1–30 requirements, unique IDs and matching requirement sections. Store under uploads/checklists with
   a creation time; expire after 14 days at startup. Use upload rate limits. Never overwrite reviewed rules.
4. Draft editing allows value/operator/severity changes and row deletion. Label throughout:
   **“Drafted by Nemotron 3 Super · edited by you · unreviewed · this browser only.”**
   Save IDs in existing browser session state. Drafting remains live-only; mock must explain why no
   “Use this checklist” button appears. An expired ID returns a clear 404 before a scan is created.
5. A draft-backed upload loads its stored rules without project conditions or exclusions. Downstream
   quote checks, unrestricted manufacturer search, Investigator, replacements and reporting remain shared.
   Review and trace identify the unreviewed draft, rule count and paragraph references.
6. Try-one links appear under the Inbox drop zone when there are no uploads. Specs links its public
   example beside drafting. Links only; PDFs stay outside Git.

### Try-one download evidence

Verified from Kyle’s machine on October 27 using plain HTTPS and PyMuPDF text extraction. No login or
challenge was required. These are input links, not claims that the products pass a checklist. The PDFs
are kept outside Git.

| Public PDF | Readable pages | Suggested spec |
| --- | ---: | --- |
| [RectorSeal Metacaulk 1000](https://rectorseal.bynder.com/asset/57ee3073-e728-44a4-992a-66a819a17d68/Spec-Sheet-English.pdf) | 3 | 07 84 00 |
| [Tremco TREMstop Acrylic](https://www.tremcosealants.com/resource/download/TREMstop_Acrylic_DS.pdf) | 2 | 07 84 00 |
| [Keystone KT-BPLED40 panel](https://keystonetech.widen.net/content/817ljcfqbn/pdf/KT-BPLED40-22-8XX-VDIM.pdf?u=xq6wdp) | 6 | 26 51 00 |
| [UBC Door Hardware](https://www.technicalguidelines.ubc.ca/guidelines/087100-Door_Hardware_UBCV.pdf) | 7 | Draft 08 71 00 |
| [Schlage ND Series](https://allegion.ca/content/dam/allegion-us-2/web-files/schlage/information-documents/Schlage_ND_Series_Cut_Sheet_113158.pdf) | 14 | Pair with UBC’s draft |

UBC paragraph 3.1.1.7 names the Schlage ND series; configuration and other requirements still need
checking. The US Allegion URL returned 403; the linked Canadian manufacturer host downloaded normally.

### Local and public walkthrough (a–e)

| Check | Action and expected evidence |
| --- | --- |
| a | Off-topic PDF → neutral mismatch, 0 Tavily credits, no fix calls |
| b | New try-one product + correct reviewed section → at least one accepted quote |
| c | Draft try-spec, delete a row, save, upload paired sheet, assign draft, scan, review and outcome |
| d | Bundled tray completes the four steps with unchanged decisions |
| e | Upload the same document twice, select different specs, and show the appropriate differing results |

Capture every result’s run ID, mode, trace and ledger delta. Screenshots taken against mock fixtures prove
UI behavior only. GATE 1 must be live, local; GATE 2 repeats a–e at the public URL in a private window.
Show Kyle the verified try-one URLs and page counts before committing them. Do not run a fresh full
8-case live evaluation. The raw 8-case **mock** regression remains required on each commit.

### Spend and host

Engineering/validation ceiling this push: **$5 model spend / 400 Tavily credits** above the local baseline.
GATE 1 ceiling: **$2 / 150 credits**, included in that push allowance. Report actual ledger deltas after
each live run. Never clear an unknown charge by guessing. Provider reservations and existing run/day/
item/step caps still apply. Budget exhaustion degrades supported stages to unconfirmed findings.

Deployment is **one container**. First try Nebius Serverless Endpoint `cpu-d3 2vcpu-8gb`, disk 32 GiB,
public auth, credentials in MysteryBox. Kyle must confirm AI Cloud balance/expiry and approve the concrete
cost before creation. Timebox from the first endpoint attempt to **90 minutes**; if `/api/health` is not
serving `mode: live`, stop and prepare Render or Fly.io with persistent disk for Kyle’s cost approval.
No controller/authority topology. Do not assume Token Factory credits cover hosting.

Add `campaign_budget.py init-judging --usd X --credits N`: create an allowance-only database only when
none exists; refuse replacement. Run at startup when JUDGING_USD/JUDGING_CREDITS are set. Proposed
allowance **$60 / 4,000 credits**, awaiting Kyle’s confirmation. Set daily caps **$8 / 600 credits**, run
cap **$3**, concurrency **2**. Put state on persistent disk. If the host has none, README must explain that
a replacement container resets the allowance, with daily caps still configured; do not claim durable
campaign limits in that configuration.

Build from a checkout containing `data/raw/` and committed replay `20261022-181611-a9d0b5`. Run public
`python scripts/smoke.py <url>` without an admin token, then private-window a–e. Nightly job is optional:
only attempt a real Nebius Serverless Job if the site works and it is before Thursday 10:00 PT. Otherwise
remove its public UI link and all execution claims. Do not reopen controller work to obtain a job screenshot.

## Video: 2 minutes 45 seconds

The [official rules](https://nebiusglobalaihackathon.devpost.com/rules) require a public YouTube video under
three minutes, functioning application footage and at least a minute of the key modules in action.
Use real browser footage from the deployed build, with mode/run/date visible. Narration below is a script,
not evidence that the pending steps work. Replace future-tense assertions only after the captured run proves them.

| Time | Screen / action | Narration |
| --- | --- | --- |
| 0:00–0:15 | Inbox and an actual product sheet | “A construction reviewer has to compare what a subcontractor sent with the project spec—and find out whether the manufacturer’s information has changed. SpecCheck puts that evidence in one review.” |
| 0:15–0:35 | Add tray items; Scan; readable model stages | “NVIDIA Nemotron 3 Nano sorts the pages. Nemotron 3 Super reads the claims and their exact quotes. Both run on Nebius Token Factory. Models read; code decides.” |
| 0:35–1:00 | Review a quoted issue; open PDF and current manufacturer source | “Tavily finds and retrieves the manufacturer’s documents. Each finding links back to evidence. Unsupported values are dropped, and ‘couldn’t confirm’ stays uncertainty. This recorded run found no passing replacement.” |
| 1:00–1:55 | Specs draft; delete/edit row; Use checklist; Inbox paired product; Scan; Review | “A judge can bring a different spec. Super drafts its checklist; I can edit it before assigning it to my product sheet. It stays visibly unreviewed and separate from the project’s reviewed rules. The same pipeline checks the new document.” |
| 1:55–2:10 | Off-topic result, then Outcome “Not checked” | “A document with no matching values doesn’t get approved. SpecCheck asks for a different spec and leaves it out of approvals and returns.” |
| 2:10–2:30 | Outcome saved decisions; Check approved now; real result | “The reviewer saves an editable message draft. No email is sent. Approved items can be checked again for manufacturer changes.” Only mention discontinuation if the shown run catches it; only mention a cloud job with real console proof. |
| 2:30–2:45 | Scoreboard, then public Inbox URL | “The recorded live demonstration got six of eight calls right and caught five of six problems, with no major false alarms and no passing fixes. It’s a small known set. Try the tray, a linked product sheet, or your own spec and submittal.” |

Trim slow waits with visible cuts; do not imply that edited waits are measured latency. Capture at least
60 seconds of real module interaction across these shots. Use no copyrighted music. Keep keys, private
console details and `.env` out of frame. Kyle records the narration and uploads the final video publicly.
Verify the encoded duration is below 180 seconds and open the YouTube link signed out.

Recording evidence to fill after GATE 2: demo URL **pending**; deployed commit/image **pending**;
tray/BYO run ID and date **pending**; a–e screenshots **pending**; public YouTube URL **pending**.

## Devpost copy draft

**Tagline:** Quoted spec checks and current manufacturer evidence for construction submittals.

**Inspiration:** I build document pipelines for a general contractor. A reviewer needs to know both whether
a submitted product meets the project’s requirements and whether the attached sheet is still current.

**What it does:** SpecCheck follows Inbox → Scan → Review → Outcome. It reads submitted PDFs, compares
quoted values with checklist rules, researches current manufacturer documents and drafts the reviewer’s
message. Evidence gaps remain visible. Add the judge playground paragraph only after GATE 1 passes.

**How we built it:** FastAPI and Pydantic own validation and deterministic decisions; React/Vite show the
PDF, findings and saved drafts. NVIDIA Nemotron 3 Nano handles page triage, while Nemotron 3 Super handles
structured reads, bounded native-tool research and report prose on Nebius Token Factory. Tavily Search,
Extract and Map provide current-source discovery and retrieval. Every paid call reserves spend first.
Describe the actual chosen host only after deployment; cloud jobs are optional and need separate proof.

**Challenges / learning:** A plausible model reply is not source evidence. We added quote, identity,
configuration, unit and bound checks so unsupported values remain unconfirmed. Public PDF access varies
by URL; retrieval needs explicit errors and evidence. See [dated provider observations](FEEDBACK.md).

**Accomplishments:** Recorded live run `20261022-181611-a9d0b5`: 6/8 right calls, 5/6 problems caught,
0/2 major false alarms, 0/5 passing fixes. State the build/date and distinguish recorded, cached, live
and mock evidence. No measured time saving, unseen accuracy or successful Investigator rescue is claimed.

**What’s next:** User validation with real reviewers and broader document coverage after the hackathon.
No additional feature work is part of this submission push.

**Built With:** Nebius Token Factory, NVIDIA Nemotron, Tavily, Python, FastAPI, Pydantic, PyMuPDF,
React, TypeScript, Vite. Add the actual host and AI Cloud only if exercised. Track: Best Apps and Agents.
Kyle confirms San Francisco attendance for the City field, reviews feedback in his voice and submits.

## Last actions for Kyle

1. Resolve the held request from individual usage if available; approve the concrete host cost and credit
   expiry, then the proposed judging allowance. Review local/public gate evidence at each stop.
2. Record the deployed browser workflow and narration using the storyboard; upload the public YouTube video.
3. Complete Devpost: description, track, public demo/repo/video URLs, Built With and feedback fields.
4. Open all links signed out, ensure the public repository has its MIT license/setup instructions, and
   submit Thursday October 29. After GATE 2, allow only hotfixes a judge would hit.

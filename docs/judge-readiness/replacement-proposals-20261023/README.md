# Source-backed replacement proposals — 2026-10-23

Kyle approved: **“Allow clearly labelled agent proposals, with every SKU, option and check supported by
fetched quotes.”** This changes replacement research only. A blank catalog field or example still cannot
select the original submitted configuration. No case expectations, reviewed requirements or blind labels change.

The replacement extractor may propose one complete SKU printed beside a catalog/stock/part-number label.
Code assigns `selection.origin=agent_proposal`; the model cannot choose that provenance. The SKU must be
quoted on its actual page. Ordering examples, placeholders and constructed combinations are rejected.
Option claims bind only to complete components of that SKU; identity must belong to the same configuration.
Value, metric, unit, scope, currency and availability gates remain mandatory. A family-only conditional
listing cannot establish a specific SKU's DLC class. Every check must pass and cite its source before a
proposal is suggested. The release checker independently replays this proof, permitting proposals only
inside replacement candidates, never on the original submission.

Review, outcome, watch, saved draft and report wording identify **SpecCheck** as the proposal author and
say **“Confirm configuration before ordering.”** Review evidence includes the printed SKU quote and page.
This is not contractor selection, acceptance or approval of the original package.

## Before and after

The [actual boundary probe](before-after.json) executes the previous selection gate from commit `7419dda`
and the current gate on synthetic text. The previous gate accepted a selected-SKU quote cut inside a
longer SKU; the new token boundary rejects it, including identifiers ending in `+` or `.`. A real submitted selection remains accepted. A catalog SKU
is accepted only in replacement mode; invented SKUs and ordering examples remain rejected in both modes.

[Ordinary extraction prompt](prompt-before.txt), [replacement proposal prompt](prompt-after.txt).
These are actual stubbed request captures with synthetic pages, not provider responses. Only property
names/meanings and source pages are supplied; requirement thresholds and answer-key values are not inputs.
The ordinary extraction prompt/schema is retained, including exclusion of caller-owned provenance from
the model schema. Replacement requests use the existing Super JSON call; no tools/format combination,
new model, discovery query or extra model call is introduced.

## Verification and limits

See [final Python output](pytest-final.txt), [presentation checks](presentation.txt), [production build](build.txt)
and [nine Chromium journeys](browser-final.txt): **722 tests passed / 2 skipped**, presentation/build clean,
**9/9 browser journeys passed**. The [source/accounting snapshot](verification.json) binds these results to
code hash `0cb242eda7b7a8d599741f074c98eaf44aebd24ccc1e48bf99d95426724e8688`. The new scenarios exercise proposal provenance, printed
SKU/option boundaries, invented/truncated codes, original-submission forgery, archived proof, wrong-SKU web
values, conditional DLC evidence, missing availability and the review/draft/outcome UI. Browser input is
explicitly synthetic; the screenshots below are not live case evidence.

[Desktop](proposal-desktop.png) · [390 px mobile](proposal-mobile.png).

The [final raw mock panel](mock-scores-final.json) remains **6/8 calls, 5/6 planted problems, 0/2 major false
alarms and 0/5 passing fixes**. There is one unnecessary note, zero invalid items, 46/65 retained claims
(29.2% dropped) and 8/20 web values (60% dropped). Eval exit 1 is the disclosed selection-policy disagreement,
not a new regression or release acceptance. Fresh mock spend is **$0 / 0 credits**; mock usage-equivalent
costs and warm timings are not live benchmarks.

The first browser attempt could not launch because Playwright expected absent Chromium revision 1248.
Using the already installed revision 1243 through `SPECCHECK_CHROMIUM_PATH` passed. No dependency change
or browser download was needed. An intermediate synthetic browser record reused an approval summary;
the final test now sets consistent send-back text before capturing the proposal screens.

**Not live validated.** The [19:14:04 UTC read-only billing refresh](billing-refresh.json) still returns
630 monthly rows / 485 key and account credits; the latest log remains 09:52:39 UTC. It supplies no receipt
for the failed 10:36–10:38 request. Campaign-date provider logs remain 480 against 490 locally settled.
Absence is not a confirmed zero charge: the one-credit unknown hold remains and the real wallet is unchanged.
Local cumulative calculated spend remains **$3.36648982 / 490 settled credits**, plus that one-credit hold.
No paid request, settlement, cloud resource, final recording or live passing replacement is claimed here.
G2 remains open. Deployment is not recommended until the remaining gates have actual evidence.

## Reproduce

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/proposal-mock-scores.json
# Expected exit 1: the raw key remains unchanged.
.venv/bin/python docs/judge-readiness/replacement-proposals-20261023/reproduce.py
cd web
npm run test:presentation
npm run build
# Start a separate mock API as in .github/workflows/checks.yml, then:
SPECCHECK_CHROMIUM_PATH=/home/kyle/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome npm run test:browser
```

The read-only billing refresh is reproduced with
`docs/judge-readiness/requirement-discovery-followup-20261023/billing-log-audit/reproduce.py`.
It never settles the hold. Keep credentials private; the full [action list](../ownership.md) separates
agent execution from Kyle's domain, billing and release decisions.

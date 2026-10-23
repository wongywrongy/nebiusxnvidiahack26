# Product-page catalog fallback — 2026-10-23

G2 remains open: **no complete replacement**. This checkpoint corrects a source substitution, without
changing prompts, original answer keys, reviewed requirements, quote gates or selection policy.

## Observed cause and general fix

The live requirement-name discovery probe returned a LightMart product page. Its first PDF link was a
full company catalog. The direct fallback replaced the requested product page with that **96,133-character**
catalog, and persisted the substitution. The actual unauthenticated product HTML contains two repeated
catalog links and no product-specific PDF link. [Exact URL, link list, status and source hash](../replacement-research-20261023/product-link-probe.json).

The shared document-link helper now skips explicit full/master/complete company-catalog filenames,
including encoded spaces. Both direct HTTP and Tavily linked-document discovery use it. An existing
page-to-company-catalog substitution is refetched through the usual billed/cache path once; unrelated
cache entries and explicitly requested catalogs remain usable. No cache tree is cleared. Generic catalog
filenames remain a documented limitation; this is not a complete semantic link classifier.

| Actual affected source | Before | After |
| --- | --- | --- |
| LightMart product request | Company catalog, 96,133 characters | Product page retained, 9,303 characters |
| Source URL | Separate full-catalog PDF | Requested product URL |
| Existing bad substitution | Reused from cache | Refetched once under normal credit accounting |
| Explicit catalog request | Supported | Supported; no forced refresh |

[Actual affected-batch request/response](live-source-probe.json), [runtime patch](source.patch),
[clean-parent reconstruction](source-reproduction.json). The live repair charges **$0 / 1 Tavily credit**.
It proves source retention, not that the page satisfies the lighting checklist or that a replacement passes.
Five new respx/pure regressions cover full/master/complete names, product-sheet preference, page retention,
legacy repair, free subsequent hits and an explicit catalog cache hit.

## Discovery experiments: no production query change

Two bounded Tavily diagnostics test PDF filtering and a requirement-name query. The former yields three
readable PDF candidates, but the additional LSI/LED-LLC texts still lack complete accepted evidence; the
latter repeats SLLT/LT and reveals the catalog substitution. Neither supplies a complete package or a
selected configuration. No broad accuracy improvement is inferred and no production query is changed.
[PDF-filter request/response](../replacement-research-20261023/pdf-discovery-probe.json),
[requirement-name request/response](../replacement-research-20261023/metric-discovery-probe.json).
Their fresh charges are **$0 / 1** and **$0 / 2 credits**, respectively.

## Verification and limits

- Full suite: **626 passed, 2 skipped in 32.12 s**, [output](pytest.txt). A sandboxed focused provider run
  stalled and was interrupted; the complete outside-sandbox run passes those tests.
- Mock run `20261023-073415-d6cd79` preserves **6/8 calls, 5/6 problems, 0/2 major false alarms,
  0/5 passing fixes**, no invalid items and one unnecessary note; 48/65 claims and 8/20 web values.
  [Score](mock-score.json); expected eval exit 1 preserves the approved raw-key disagreements.
- No frontend code changed. Previous frontend checks are not a new live-browser proof.

Current-code live confirmation **`20261023-073518-c1e622`**:

| Item | Correct call / problem caught | Passing fix | End-to-end time | Fresh model USD / credits |
| --- | --- | --- | ---: | ---: |
| c03 | 1/1, currency send-back | 0/1 | 0.864 s | 0 / 0 |
| c07 | 1/1, discontinued send-back | 0/1 | 0.846 s | 0 / 0 |

All provider responses in this confirmation are cached: **$0 / 0 fresh charges**. These times are not
fresh upload/provider latency or a measured speed improvement. The earlier paid checkpoint remains the
[fresh-work observation](../replacement-research-20261023/README.md).
Claims retained **56/209** (73.2% dropped), web values **54/110** (50.9% dropped). No clean item is
requested. No typed invalidity, cap/provider warnings or observed 429s occur. Zero primary investigations
run; four replacement investigations run, none capped, with the same unresolved checklist/selection/
availability gaps. One confirms values and one finds only a revision; neither yields a passing replacement.
[Score](score.json), [stage diagnosis](diagnosis.json), [trace](events.jsonl).
The actual claim/source/archive/trace consistency check [passes](consistency.json) for two items only;
the release gate still fails. No full-set follow-up, blind evaluation or final recording is consumed.

This checkpoint's diagnostics add **$0 / 4 credits** after the preceding paid run. Actual cumulative local
accounting is **$2.6351023 / 442**, UTC day **$1.1483655 / 84**, engineering since the original pass
**$1.5764973 / 144**. No holds or persistent block. [Campaign](campaign-status.json), [daily mirror](daily-ledger.json).
The prior dashboard/API observations predate this work and remain unreconciled. No ledger is adjusted.
No deployment, cloud resource, owner approval or real authority transfer occurred.

## Reproduction

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/catalog-fallback-mock.json
# Expected mock exit 1; the raw key is unchanged.
SPECCHECK_MODE=live MAX_OUTPUT_TOKENS=32768 INVESTIGATE_MAX_STEPS=24 INVESTIGATE_CREDIT_CAP=30 FIX_CREDIT_CAP=40 EVIDENCE_DIR=.cache/live-evidence .venv/bin/python scripts/eval.py --case c03 --case c07 --out /tmp/catalog-fallback-live.json
.venv/bin/python scripts/campaign_budget.py status
```

To reproduce the affected source retrieval, bind a `budget.Ledger` and item context, then use
`WebClient(None).extract` with the three URLs saved in `live-source-probe.json`. Reuse the existing
authority/cache; do not copy secrets into the request or reset accounting. Cache misses or expiry can charge.

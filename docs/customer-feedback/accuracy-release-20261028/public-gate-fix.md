# Public draft-checklist regression and fix

The first deployment of `8f91ae9` passed smoke and browser journeys a, b (on retry), d and e. Journey c failed: a newly drafted UBC checklist paired with the Schlage ND sheet yielded no quoted claims and no matched rules. Its numeric-only draft also omitted the printed approved-series alternatives. The initial failed c and transient b connection failure remain in `public-8f91ae9-attempt/`; their provider charges are included in hosted accounting.

Kyle approved fixing the regression and deploying a new image. Source `a81d9d203f2562fdc7486b74f3863f11cf8154aa` adds requirement descriptions and request-specific reasoning to custom-checklist extraction, and asks the draft extractor to retain grouped printed product choices when rows remain. Custom scans request only their checklist properties and referenced dependencies. Claims still need a literal quote and grounded value on their own product page; the specification description cannot provide product evidence. Product-type exclusions and unreviewed-draft disclosures remain enforced.

The stock eight-case extraction requests were compared against `8f91ae9`: all 13 page batches have identical prompts, schemas and contexts, with no provider calls. The source keeps the recording `20261028-171142-5ca0fc`; no new stock-case recording or replacement success is claimed. Full mock suite: **797 passed, 2 skipped**. Tests cover custom property dependencies, reasoning/cache isolation and rejection of values quoted only in the requirement hint. The built image passed the credential-free, network-disabled API/PDF/memo/package proof and a scan of 9,774 regular files for configured secret values.

Public acceptance on the fixed image is recorded separately under `public/`. The capture script and its assertions were not weakened.

## Commissioning a deployment with its existing cache

The original smoke check completed valid live results on the fixed image but refused cached-only c01 usage. A fresh-web retry spent 5 credits, retrieved unchanged source text and correctly reused the same model readings; it also failed freshness. Both attempts remain under `public/smoke-*-attempt*`.

Verification-tool commit `20cca85` stamps a clearly labelled deployment probe onto an in-memory copy of the off-topic PDF. The bounded two-input scan retains c01 and requires a non-cached live Nemotron call from that scan. It still rejects replayed, invalid or failed results and cached-only usage. The real successful run `20261028-183136-799436` includes fresh Nano triage and Super extraction. No persistent cache was deleted, no API response was fabricated, and no runtime image change was needed for this standalone verification tool. All 10 smoke-tool tests pass, including the preserved-cache and cached-only rejection cases.

The memo and Scoreboard helper's first two approved-item attempts could not read an uploaded response from Chromium's inspector cache; neither started a scan or spent provider allowance. The helper now starts reading that real response immediately and uses the same PDF-buffer upload pattern as the five-journey capture. Original failures are retained as `public/check-approved-attempt1.json` and `public/check-approved-attempt2.json`.

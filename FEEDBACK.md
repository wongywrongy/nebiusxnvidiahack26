# Feedback log (for the Devpost feedback section)

Write a dated line whenever something about Token Factory, Nebius AI Cloud, Nemotron or Tavily helps or gets in the way.
Specific, reproducible notes are what win the "Most Valuable Feedback" prize.

| Date | Product | What happened | Suggestion |
| --- | --- | --- | --- |
| 2026-10-05 | Hilti docs (test data) | All 3 Hilti `media-canonical/ASSET_DOC_LOC_*_APC_RAW` URLs in cases.json now return 404 HTML; asset IDs rotate. | Pin documents by sha256 and keep a local copy; don't rely on manufacturer asset URLs staying stable. |
| 2026-10-05 | Acuity / HD Supply (test data) | img.acuitybrands.com, acuitybrands.com and hdsupplysolutions.com return a 403 Cloudflare "Attention Required" captcha to plain HTTP clients. | Worth testing whether Tavily Extract gets past it; if it does, that's a strong point for Tavily over raw fetching. |
| 2026-10-05 | Tavily (python SDK) | `AsyncTavilyClient.map` has no default page limit, and our `WebClient.map` doesn't pass one, so mapping a large manufacturer site could bill many credits (1 per 10 pages). | Docs/SDK could show a cost cap example; we pass `limit=20, max_depth=1` in the spike. |

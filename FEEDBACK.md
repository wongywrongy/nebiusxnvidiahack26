# Feedback log (for the Devpost feedback section)

Write a dated line whenever something about Token Factory, Nebius AI Cloud, Nemotron or Tavily helps or gets in the way.
Specific, reproducible notes are what win the "Most Valuable Feedback" prize.

| Date | Product | What happened | Suggestion |
| --- | --- | --- | --- |
| 2026-10-05 | Hilti docs (test data) | All 3 Hilti `media-canonical/ASSET_DOC_LOC_*_APC_RAW` URLs in cases.json now return 404 HTML; asset IDs rotate. | Pin documents by sha256 and keep a local copy; don't rely on manufacturer asset URLs staying stable. |
| 2026-10-05 | Acuity / HD Supply (test data) | img.acuitybrands.com, acuitybrands.com and hdsupplysolutions.com return a 403 Cloudflare "Attention Required" captcha to plain HTTP clients. | Worth testing whether Tavily Extract gets past it; if it does, that's a strong point for Tavily over raw fetching. |
| 2026-10-05 | Tavily (python SDK) | `AsyncTavilyClient.map` has no default page limit, and our `WebClient.map` doesn't pass one, so mapping a large manufacturer site could bill many credits (1 per 10 pages). | Docs/SDK could show a cost cap example; we pass `limit=20, max_depth=1` in the spike. |
| 2026-10-05 | STI (test data) | stifirestop.com's LCI product page shows "Less than or equal to 185°F (85°C)" in both its VOC Content and STC Rating rows, so a verify step reading the page can't get VOC from it; the linked PDS (26 g/L) is right. | Verify should prefer the manufacturer's PDF over the product page's spec table when both exist. |
| 2026-10-05 | STI (test data) | The widely mirrored LCI sheet (rev ZSFOD5062 3409, 2020) is superseded by rev 25171 (2025) with identical values: real currency drift even for a "clean" product. | Good demo point: currency checks need the revision, not just the values. We now submit the 2025 sheet for the clean case. |
| 2026-10-05 | Test data | The Albuquerque city submittal URL for LDN6 Rev. 04/11/25 returns 404 (IIS "File or directory not found"); Dublin, OH copy (Rev. 05/03/22) works. The Acuity TL discontinuation notice was reachable by plain HTTP (no Cloudflare). | Remove or replace the Albuquerque URL in documents.json. |

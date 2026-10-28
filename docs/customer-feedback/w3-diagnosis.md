# W3 diagnosis: why no live alternate reached "meets spec"

Read-only, from `runs/recorded/20261022-181611-a9d0b5` (live, Oct 22), plus a direct fetch of the c07 notice page. That recording came before two current behaviours: the current document as candidate zero (`origin=current_document`) and the "Still made" check on every candidate. So it shows where candidates came from and which checks stopped them. It doesn't show today's ranking.

| Item | Problem | Query | Candidates tried | What stopped each one |
| --- | --- | --- | --- | --- |
| c02 | T rating fails (spec) | `UL listed firestop system  floor penetration Temperature rating (T) equals Fire rating (F)` | 3M Fire Barrier Rated Foam FIP 1-Step data sheet | Current document passed (RevB). **Temperature rating (T): unconfirmed.** A product data sheet carries no T rating; T ratings live in UL system listings, and the search returned a product sheet. |
| c03 | Submitted sheet outdated | `3M 3M Fire Barrier IC 15WB+ Sealant current data sheet` (maker doubled) | 3M CP 25WB+ product page; 3M 3000 WT product page | Both are HTML product pages, not data sheets. **VOC, ASTM G21 and test standards: "not stated".** The current IC 15WB+ sheet that verify had already found (`multimedia.3m.com/…/207329O`) wasn't a candidate. Today it is candidate zero. In mock it ends "possible" on Temperature rating (T) and Still made. |
| c04 | Listing doesn't cover steel pipe | `UL listed firestop system steel pipe steel pipe through gypsum wall` | 2 search results gave no claims (27 and 41 output tokens), then STI System No. WL-1049 (PDF) | WL-1049: current document passed. **Temperature rating (T) and Pipe types covered: "not stated".** It's a system PDF whose values sit in tables the extract didn't quote. |
| c06 | Expected send-back; live gave approve with note | — | none | Currency came back "newer" (a note), not "outdated", so no fix ran. That's on the decision path, outside W3. |
| c07 | Discontinued | `"LED troffer" manufacturer specification sheet` | 1 search result, no claims (29 output tokens) | Dropped before any check: nothing quoted. **The notice names its replacements only in an image** (below). |

## c07: the discontinuation notice

`insights.acuitybrands.com/product-updates-blog/discontinuation-notice-lithonia-lighting-tl-recessed-luminaire-2`. The text Tavily extracts reads: "As of **June 30th, 2024**, the TL family will be discontinued. Please begin converting this business to the following replacements options." It ends there. The page's HTML puts the cross-reference in an inline `data:image/png;base64` table (TL FW → CPX A12 / CPX SWL, TL RW → SPX MPL / SPX LUGR, bottom access → GTL / ALL). No replacement name appears as text on the page.

Consequence for W3's named-replacement step as briefed (quote-gated on the notice text): on c07 it will find no quotable name and drop it. That is the correct, honest result. Getting CPX/SPX into the candidates would take OCR of inline images on the notice page. Tesseract is already in the container for scanned submittals, so that is a scope decision for Kyle, not a gate change.

## What W3 changes and why

1. **Named replacement** (discontinued items): ask Super, quote-gated on the fetched notice text, whether it names a replacement. If it does, search that name on the maker's domains and put it first. It runs through the same extract → spec check → verify, inside the same caps. It helps notices that name a successor in text (e.g. the Acuity CPRB notice: "replaced by the new CPRB IP65 High Bay"). It doesn't help c07 as published.
2. **Current-document "Still made"** (c03): candidate zero is the same product and URL that verify already checked. If verify quoted the product as active on that URL, the candidate's "Still made" check can use that quote instead of staying unconfirmed.
3. **Not changed**: the c02/c04 gaps are T ratings and listing coverage that only UL system listings carry. The search queries and extraction of listing tables are prompt 10's Package A/B territory, now cut.

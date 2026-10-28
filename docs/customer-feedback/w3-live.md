# W3 live re-run (before OCR)

Run `20261028-053737-0551f7`, local, live (Nemotron 3 Nano and Super on Nebius Token Factory, Tavily), Oct 28 05:37 UTC.
Spend from the shared ledger: **$0.4815 and 32 Tavily credits** (today $0.7214 / 52 → $1.2030 / 84).

| Item | Decision (expected) | Alternates, ranked in code | Still to confirm | Better marks | Item cost |
| --- | --- | --- | --- | --- | --- |
| c02 | send back (send back) | none: no search result gave quoted values | — | — | $0.0648 · 3 cr |
| c03 | send back (send back) | 1. **possible** · current sheet of the same product (3M IC 15WB+ Product Data Sheet) · 2. **possible** · 3M IC 15WB+ product page | ASTM G21 rating, Temperature rating (T), Still made (both) | VOC < 250 g/L = meets | $0.2136 · 10 cr |
| c04 | send back (send back) | none | — | — | $0.0397 · 5 cr |
| c06 | approve with note (send back) | no fix: live currency came back "newer", not "outdated" | — | — | $0.0918 · 9 cr |
| c07 | send back (send back) | none. The named-replacement call ran ($0.0024) and its gate accepted the phrase "following replacements options" as a name (see correction below); that search gave no usable candidate | — | — | $0.0717 · 5 cr |

**No live `meets_spec`.** Per the honesty rule the copy says "suggests alternates and shows what's still unconfirmed". c03's "Still made" stays unconfirmed: the item's own check quoted no active status, so there was nothing to reuse.

## Correction and the OCR step (c07 only)

The first run's text gate accepted "following replacements options" from the sentence "Please begin converting this business to the following replacements options.": the phrase really is in the sentence. The gate now also requires a designation (a token with a capital or a digit), and the prompt says a phrase like "the following options" is not a name. Test added.

Then the OCR step (Kyle's go, after no live meets_spec): when the notice text names no successor, the page's inline images are OCR'd and Super reads that text for the submitted product's row.

| Run | What happened | Spend (ledger) |
| --- | --- | --- |
| `20261028-055030-a9df5e` | Before the designation gate: the bad text name was still accepted, so OCR didn't run | $0.0089 · 0 cr |
| `20261028-055131-e8e2f1` | Text gate: no name. OCR read the table from the notice image (one direct page GET, no Tavily credits): `TL FW A12 ( flat frame) CPX Al12` … `TL RW MWS ( regressed frame) \| SPX LUGR` … `TL GTL` / `TL ALL`. Super, given the submitted product **2TL**, returned no row. Every row is TL plus a frame/lens the submittal doesn't state, so nothing was kept | $0.0037 · 0 cr |

Result: **no live meets_spec, and no named replacement for c07.** The OCR path works live (the table text is cached at `.cache/page_image_ocr`), and its gate held: no row was guessed for a configuration the submittal doesn't give. Ledger after all W3 live work: **$1.2156 / 84 credits today** (W3 total $0.4941 / 32).

## Schlage upload, W1 "after" (live, local)

`screens/before-schlage-1440.png` is the Oct 27 public gate. `screens/after-schlage-1440.png` is run `20261028-055531-bdeddc`. It uses the same Schlage ND PDF and the 30-rule checklist that was edited in that gate (from `docs/playground/public-final/c-trace.json`), saved to the local server. A fresh UBC draft first failed with "The reply was cut off at the token limit" ($0.0094), so the recorded edited checklist was used instead. Result: approve with note, 3 meet, 0 don't, 4 couldn't be confirmed. What to send: "The newer data sheet (optional)". 23 other-product rules are hidden. Spend: $0.0209 / 0 credits (web calls cached); with the failed draft, $0.0303. Ledger: $1.2459 / 84 credits today.

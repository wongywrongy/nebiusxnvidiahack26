# QuickShip source follow-up — 2026-10-23

Manual source research found manufacturer inventory evidence that the latest replacement investigation
did not retrieve. This is additional source evidence, not an application evaluation or a passing fix.
The current selection policy, original cases, reviewed requirements, prompts and caches used by providers
are unchanged. No proposed configuration is selected or recommended here.

[Actual HTTP requests, hashes, page-grounded quotes and latest retrieval comparison](quickship-observation.json).
All three unauthenticated manufacturer GETs returned HTTP 200. The QuickShip PDF has two native-text
pages, the general LT PDF four; both first-page tables were inspected visually. Native files, text and
renders remain ignored under `.cache/research/williams-quickship-20261023/`, outside provider caches.

| Source | New evidence | Limit |
| --- | --- | --- |
| [LT QuickShip PDF](https://hew.com/specifications/LT_quickship.pdf), page 1, revision July 30, 2026 | Manufacturer states stocked QuickShip availability; the ordering table prints complete catalog numbers | Every listed model uses DIM. The control-voltage description does not establish minimum light-output percent. DLC qualification has an explicit version limitation. |
| [General LT PDF](https://hew.com/specifications/LT_led.pdf), pages 1 and 4, revision January 21, 2026 | DIM1 is the separate one-percent driver option | It cannot establish that the QuickShip DIM models have that rating. Changing the order code does not preserve the QuickShip inventory statement. |
| [QuickShip program page](https://hew.com/products/quickship), LT section | Lists six exact offered configurations and a product-specific PDF link | A family/stock-program offering does not select the contractor's configuration or establish a particular DLC class. |

The two revisions describe different document/configuration scopes; their dates are not proof that one
supersedes the other. No original answer-key conflict is established by this new candidate research.

For the actual c07 run `20261023-084824-7ab49b`, replacement investigations extracted the general LT sheet,
not this QuickShip PDF. That is a **fix / investigate-search-and-extract coverage gap**. The newly located
source helps availability research for the printed stock models, but dimming, specific DLC qualification
and a genuine selection still prevent a complete passing replacement. No status gate is weakened or broad
family availability inferred. The pending proposal-selection decision does not supply these missing facts.

Reproduce with unauthenticated GETs of the three URLs, verify their hashes against the observation,
extract native page text with PyMuPDF and inspect the page-one ordering/driver tables. Stop for source
review if a hash or material statement changes. Do not inject manually downloaded sources into the
application's paid caches, infer a selected SKU, or present this manual inspection as a Super/Tavily run.

Research adds **$0 / 0 provider credits**. Settled actual local accounting remains **$2.9516488 / 457**,
with no holds. G2 stays open; no full evaluation, blind run, final recording, image build or cloud operation.

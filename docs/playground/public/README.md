# Public browser checks — October 27, 2026

All five checks passed in fresh private Chromium contexts on the live Nebius URL. No responses were intercepted. Cached calls are identified in the actual traces; no replay or mock result was accepted.

| Check | Run | Model USD | Tavily credits |
| --- | --- | ---: | ---: |
| [a](a-trace.json) | `20261027-213432-156290` | 0.00000000 | 0 |
| [b](b-trace.json) | `20261027-213502-ad3ccb` | 0.02257356 | 6 |
| [c](c-trace.json) | `20261027-213717-37058d` | 0.04664346 | 6 |
| [d](d-trace.json) | `20261027-214516-f3e253` | 0.19372416 | 27 |
| [e](e-trace.json) | `20261027-215052-0bf2ea` | 0.01999200 | 3 |

The earlier [four-item tray attempt](d-attempt1-trace.json) is retained: the capture clicked Scan before the final three add requests returned. All four results were valid, but it failed the seven-item count assertion. Cost: $0.24982812 / 30 credits. The capture now waits for all seven rows before Scan; the successful trace confirms every tray item reached verify, including zero-claim items.

Smoke cost: $0.02498790 / 8 credits. Hosted total including smoke and every attempt: **$0.55774920 / 80 credits**. No holds; blocked false. Local push spend before deployment: $0.64693362 / 38 credits, including conservative timeout settlements. Combined push total at this checkpoint: **$1.20468282 / 118 credits**.

- [Off-topic](a-review.png) · [Try-one](b-review.png)
- [Edited draft](c-draft-edited.png) · [Schlage ND Review](c-review.png) · [Other types](c-other-product-types.png) · [BYO Outcome](c-outcome.png)
- [Full tray Outcome](d-outcome.png) · [Same PDF/firestop](e-firestop-review.png) · [Same PDF/lighting](e-lighting-review.png)

The UBC model draft contained 65 rows despite its prompt limit; 35 were deleted to save 30. Five of seven applicable rules matched, ND passed, and 23 other-product rules were hidden. Drafts remain unreviewed; shared untyped rules still apply. The seven-item tray took several minutes; no passing replacement was found. This is workflow evidence, not a new eight-case accuracy evaluation.

Approved UI polish and redeployment follow this checkpoint. No cloud-job execution is claimed.

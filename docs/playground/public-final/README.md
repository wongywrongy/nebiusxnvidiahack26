# Frozen public demo — October 27, 2026

**[Open SpecCheck](https://port8000-xbq07jkkdkpet9f.tunnel.applications.eu-west1.nebius.cloud)**

All five checks passed in fresh private Chromium contexts on this final URL. Replies were genuine live pipeline results, with cached calls labelled in their traces. No API routes were intercepted and no replay/mock result was accepted.

| Check | Run | Added model USD | Tavily credits |
| --- | --- | ---: | ---: |
| [a](a-trace.json) | `20261027-220512-ad3554` | 0.00000000 | 0 |
| [b](b-trace.json) | `20261027-220518-f52a4f` | 0.01082010 | 0 |
| [c](c-trace.json) | `20261027-220600-7bbc44` | 0.01643520 | 1 |
| [d](d-trace.json) | `20261027-220656-b91ba1` | 0.08850660 | 10 |
| [e](e-trace.json) | `20261027-220937-b8e50e` | 0.00000000 | 0 |

[Initial public fresh smoke and all-attempt accounting](../public/README.md) retain the first deployment, including its failed four-item capture and successful seven-item retry. The final endpoint passed a no-admin read-only smoke preflight and all five browser loops. Final b/c/d include fresh provider calls; cached operations are not represented as new inference.

- [Off-topic Review](a-review.png) · [Try-one Review](b-review.png)
- [Edited draft](c-draft-edited.png) · [Schlage ND Review](c-review.png) · [Other types](c-other-product-types.png) · [BYO Outcome](c-outcome.png)
- [Seven-item tray Outcome](d-outcome.png) · [Same PDF/firestop](e-firestop-review.png) · [Same PDF/lighting](e-lighting-review.png)
- [Add all samples](add-all-samples.png): seven rows, one primary action, no scan started automatically.

Schlage ND passes, with only applicable/shared rules visible and 23 other-product rules hidden. Every tray item reached manufacturer verification, including zero-match items. Off-topic uploads use zero Tavily credits. The empty nightly line is absent; mock browser coverage also verifies display-only quote cleanup leaves stored raw quotations unchanged.

## Spend and persistence

The endpoint replacement preserved **$0.55774920 / 80 credits** exactly before any further calls. The same persistent filesystem holds the ledger, cache, uploads and native pages. Superseded endpoint removed; Fly was not used.

Final hosted ledger: **$0.67351110 / 91 credits**. Local push ledger delta: **$0.64693362 / 38 credits**, including conservative timeout settlements. Combined push: **$1.32044472 / 129 credits**. No holds; blocked false. Judging allowance remaining: **$74.32648890 / 5,909 credits**. Daily remaining at this checkpoint: $7.32648890 / 509 credits. These are ledger amounts based on returned usage and configured rates, not a separately read provider invoice.

## Limits a judge can hit

1. Drafts are unreviewed. The UBC example returned 65 rows despite its prompt limit, so 35 were deleted to save 30; semantic review remains necessary.
2. Large tray runs take minutes; uncertain sources leave could-not-confirm notes. No passing replacement was found.
3. A long candidate URL can extend beyond its Outcome cell. This display issue was visible in the final tray screenshot and remains after code freeze.

No cloud job or nightly schedule was run. Application code is frozen at `eea71cfeb93aa0caa44b7ef54bc2743e2d871751`. [Deployment proof](../../deployment/final-deployment.json).

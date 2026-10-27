# Judge playground — October 27, 2026

[Public Nebius demo](https://port8000-ddh028qg63p3bzj.tunnel.applications.eu-west1.nebius.cloud) · [Deployment and smoke](../deployment/README.md)

PR #13 is merged. Off-topic uploads, upload spec selection, editable unreviewed checklists, product-type scoping and Try-one links are implemented. The raw mock panel remains 6/8 calls, 5/6 problems, 0/2 false alarms and 0/5 passing replacements. No reviewed checklist or case expectation was changed.

All five public private-browser checks passed, including the seven-item tray and the same PDF under two specs. Each check uses a fresh Chromium context and genuine live API replies; no routes are intercepted. [Public traces, screenshots and all-attempt costs](public/README.md) retain actual run IDs and ledger deltas.

- [Off-topic Review](public/a-review.png): doesn't match the selected spec; zero web calls.
- [Try-one Review](public/b-review.png): RectorSeal produces quoted spec findings.
- [Bring-your-own Review](public/c-review.png): Schlage ND passes; five of seven applicable rules matched; 23 other-product rules are hidden. [Edited draft](public/c-draft-edited.png) · [Other types](public/c-other-product-types.png) · [Outcome](public/c-outcome.png).

[Final local scoped checks and costs](local-scoped/README.md) supersede the earlier blocked local attempt. Local push spend was $0.64693362 / 38 credits, including conservative owner-authorized timeout settlements. No holds remained before deployment. [Earlier local failures and observations](history-20261027.md) remain available without being represented as passes.

[Download verification](pdf-links.json) confirms all five Try-one links returned plain HTTPS PDFs under 15 MB with extractable page-one text, including UBC (7 pages) and Schlage (14 pages). Raw PDFs are not bundled in Git. No cloud job or passing live replacement is claimed.

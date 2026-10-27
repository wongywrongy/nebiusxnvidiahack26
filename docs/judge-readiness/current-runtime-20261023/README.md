# Current unit-runtime image and source research — 2026-10-23

This is a local engineering checkpoint, not release approval. G2 still has no fully evidenced replacement.
No full-set/blind run, final recording, provider request, real wallet transfer, registry publication or
cloud resource is created by these checks. Original case expectations and reviewed checklists are unchanged.

## Current local image

Local tag `speccheck:unit-source-local` has image/index ID
`sha256:f9b23899e35c38fdb1dff56ab7661dd3723b22701cc625bfc21abef062edf586`.
Its runtime hash is `00e67a6b689a02864de9286e2f4b7d39fbb31b845fee871a7a09d5964783a3a3`,
matching the tested unit correction `a9df48c` and current checkout. [Build/image identity](image-metadata.json),
[runtime/input inventory](image-privacy.json). Dependency and frontend layers were cached; this is not an
uncached dependency/build proof. The default command remains `python scripts/serve.py`.

- All 13 locked PDFs are native/readable and match their hashes; [preflight](document-preflight.json).
- Blind PDFs, uploads, private app cache/authority and `.env` are absent. All key-presence booleans are false.
- A private-stdin check finds no configured secret string in 8,562 regular image files; [booleans](image-secret-scan.json).
  Virtual filesystems, symlinks and deleted layers are outside this scan.
- The existing synthetic quantity reproducer drops the forged claim and web value, returns unverified and
  refuses the release claim; [actual image output](image-unit-gate.json).
- Image mock evaluation preserves **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 fixes**, zero invalid
  items and expected exit 1 for the disclosed policy disagreements; [actual score/output](image-mock.json).

The [existing isolated reproducer](../preproduction-packaging-20261023/reproduce.py) ran with only its pinned
image constant changed; [script identity](reproducer.json). It uses synthetic credentials and a new private
temporary mount, Docker networking disabled and no public ports. Startup creates no wallet; explicit
synthetic import and two process/container restarts preserve authority, app markers and replay results.
Explicit replay returns 10 historical recorded results. All eight public items replay under a synthetic
zero day cap; fresh re-check returns HTTP 429. [Actual API/restart results](capped-replay-restart.json).
The temporary container was removed. No real key environment or authority was mounted. This is not hosted
storage/reboot behavior, a fresh upload or a new live evaluation. The final registry digest and release
approval remain unset; rebuild if final validation changes runtime or packaged inputs.

```bash
docker build --progress=plain --metadata-file /tmp/speccheck-unit-image-metadata.json --tag speccheck:unit-source-local .
docker run --rm --network none --entrypoint python speccheck:unit-source-local scripts/check_pdfs.py --required
docker run --rm -i --network none --entrypoint python speccheck:unit-source-local - < docs/judge-readiness/quantity-units-20261023/reproduce.py
docker run --rm --network none --entrypoint python speccheck:unit-source-local scripts/eval.py --out /tmp/image-mock.json
# Expected mock exit 1. Use the linked existing reproducer with this inspected local image ID for replay/restart.
```

## Additional primary-source research

Three unauthenticated manufacturer HTTP GETs returned 200. [Dated requests, response hashes and short
page quotes](manufacturer-research.json); full responses remain only in the ignored private cache.

| Source | New evidence | What it does not establish |
| --- | --- | --- |
| [Williams LT QuickShip PDF](https://hew.com/specifications/LT_quickship.pdf), page 1 | Explicit stock/shipping wording for six listed configurations | No submitted selection; no availability proof for every LT driver/configuration or selected DLC listing |
| [Elite 24-LITE-LED-7 PDF](https://media.iuseelite.com/specsheet2/24-lite-led-7-ml-cct.pdf), pages 1–2 | The same sheet states conflicting minimum dimming percentages | No reliable dimming pass; the favorable page cannot settle the contradiction |
| [Utopia RSHL-C page](https://prod.utopialighting.com/product/rshl-c-recessed-lay-in-light) | Manufacturer directs availability inquiries to its team | No affirmative stock/availability statement |

These are manual source observations, not pipeline scores or a new answer-key contradiction. No source is
injected into a case, selected for the owner, added to a prompt or declared passing. The pending
[replacement-proposal policy decision](../document-revisions-20261023/replacement-policy-question.md) remains
separate from proving the applicable source facts. Reproduce the observations by GETting the recorded
URLs and checking the saved page excerpts/hashes; a changed source requires renewed review.

This checkpoint adds **$0 / 0 paid provider charges**. The actual ledger remains **$2.9516488 / 457 credits**,
engineering **$1.8930438 / 159**, with no holds or persistent block; [accounting after checks](campaign-after.json).
The earlier dashboard/API differences are unresolved. G2 and later gates remain open.

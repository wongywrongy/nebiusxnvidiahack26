# Packaging exclusion and capped replay — 2026-10-23

The existing local image included six unreviewed blind PDFs. `.dockerignore` now excludes `data/raw/blind`,
while keeping the 13 locked product/spec PDFs. No model prompt, quote/selection gate, original expectation,
reviewed requirement or application runtime changed in this packaging patch.

This evidence uses **frozen runtime `1c3c7fe` plus the packaging exclusion**. A concurrent `verify.py` change
appeared while integration was being checked. It was left untouched. These results do not establish that
newer runtime's correctness, a passing replacement, complete evaluation or production readiness.

## Actual before and after

| Check | Observed result |
| --- | --- |
| Prior local image `e92d0c23…` | All 13 locked PDFs plus six `data/raw/blind/20261023/` PDFs |
| Isolated build with exclusion | All 13 locked PDFs plus the raw manifest; no blind PDF |
| Native PDF preflight | 13/13 match the lock and are readable; no low-text documents |
| Runtime identity | `f96aca7736fbc9f8730b7e51ba197a7cfdfe23913841286775cb4bc6fa3e212a` |
| Isolated mock Python suite | **626 passed, 2 skipped in 31.76 s** |
| Raw mock eval | **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**, zero invalid items; 48/65 claims and 8/20 web values retained |
| Whole image filesystem/configuration check | **8,562 regular files** checked; no configured secret string found |
| Synthetic authority import and restart | Source fenced; state, authority and app files preserved |
| Actual loopback API, temporary zero day cap | Historical live scoreboard served; explicit replay returns 10 results; all eight public items replay |
| Public item coverage | Seven tray items including s3/s4, plus one watched item |
| Fresh re-check at zero cap | HTTP **429**; no replay presented as fresh |
| Second container restart | All eight replayed results remain, with their replay source retained |

The local image/index ID is
`sha256:60c7b9f12562ef1db4210c7a651b9ae6dc5aa9cdbcadd5337aa2e893b3e56ad1`.
It is unpublished. The runtime build inputs were compared byte-for-byte with the frozen commit; the only
packaging delta is [source.patch](source.patch). [Identity](source-identity.json), [actual build](build.txt),
[image checks](image-proof.json), [native preflight](document-preflight.json),
[image secret scan](image-secret-scan.json), [mock output](pytest.txt), [mock scoreboard](mock-score.json).

The replay and restart proof uses a new temporary ext4 mount, generated synthetic credentials and a
new synthetic wallet. Its $0.123 / four-credit seed is test data, never actual provider spend. Docker
networking is disabled and no host port is published. Real credentials, wallet, caps and private receipts
are never mounted or changed. Its temporary container is removed in `finally`.
[Actual API/restart response](capped-api-proof.json), [executed reproducer](reproduce.py).
The scoreboard/replay source is historical `20261022-181611-a9d0b5`, not a new live evaluation.
Initial diagnostic assertions used the wrong tray count/Specs response field; the probe was corrected to
the actual API contract. No application behavior was changed to make those assertions pass.

## Public prices and billing observation

The raw official pricing pages explicitly describe Virtual Networks and Container Registry as free and
SecretStash as free while in preview. The rendered web reader omitted these bodies; unauthenticated `.md`
GETs returned HTTP 200 with the statements. [Hashed observations](public-cost-addendum.json),
[registry/secret responses](registry-secret-pricing.json), [network response](vpc-pricing-response.md).
Sources: [Virtual Networks](https://docs.nebius.com/vpc/resources/pricing.md),
[Container Registry](https://docs.nebius.com/container-registry/resources/pricing.md),
[SecretStash](https://docs.nebius.com/mysterybox/resources/pricing.md).
This resolves those public service-rate questions; private tax treatment, grant expiry, IAM/quota and
final operating/retention dates still require account evidence. No resource or approval was created.

At **07:46:54 UTC**, authenticated Tavily `GET /usage` with `Cache-Control: no-cache` returned HTTP 200:
**421** for both key and account, comprising 368 search + 49 extract + 4 map. The response Date header
matches that time; it does not prove the backend counter has no lag. The local campaign then reported
**$2.6351023 / 442** and was unchanged by the GET. [Redacted request, response and headers](tavily-usage-no-cache.json).
This matches Kyle's earlier credit reading numerically at a different time, not a synchronized invoice
reconciliation. Local credits were 21 higher; no cause or ledger correction is inferred. Later concurrent
validation is separate from these observations. Packaging itself adds **$0 / 0 provider charges**.

## Reproduce safely

```bash
# Use this checkpoint, with locked public PDFs present. Preserve the real cache and wallet.
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/packaging-mock.json
# Expected mock exit 1: the approved selection-policy disagreements remain visible.
docker build --progress=plain --tag speccheck:packaging-check .
```

Inspect the built image's `/app/data/raw` inventory against `data/documents.lock.json`; only the locked
files and manifest should remain. For the synthetic API/restart proof, the checked-in reproducer pins the
tested **local** image ID. A fresh build may have a different image ID/base digest: replace that single
constant with the inspected new local ID, execute `python reproduce.py`, and retain its new report/hash.
Do not claim the old image identity for a new build. It requires Linux and a local Unix Docker socket,
creates its own temporary state and refuses a remote socket. Never substitute real credentials/state.

For billing, repeat only the documented Tavily usage GET with the private key, retain the allowed usage
fields and redact authorization. Compare with `scripts/campaign_budget.py status` and a synchronized
owner dashboard reading. Do not lower accounting to force a match.

G2 still lacks a complete replacement. Full current cases/samples/reviewed blind evidence, final recording,
owner release dispositions and approved hosted proof remain pending. No gate or owner review is granted here.

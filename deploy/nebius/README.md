# Nebius rollout preparation — 2026-10-23

**No deployment is approved or verified.** Keep the Endpoint + Serverless Jobs design. The October 16–17
and October 22 rollout dates are historical targets, not completed deployments. No cloud resources have
been created in this session. [Ownership and open work](../../docs/judge-readiness/ownership.md).

## Release blockers

- G2 has no fully evidenced passing replacement. Final cases/samples/blind validation and the new public
  recording are pending their gates.
- Local SQLite proves local reservations; placing it on an S3 mount does not establish a cloud authority.
- The controller-owned allowance/claim/child-wallet/receipt/settlement protocol and explicit private wallet
  transfer/cutover tools are tested locally. No real wallet was moved; hosted persistence is unverified.
- Jobs now return signed usage/evidence without a shared controller/archive mount. Unknown creation,
  billing or completion retains its reservation; a missing/corrupt receipt persists an accounting block.
- Final image digest, owner IAM/account configuration, credit expiry and storage design remain incomplete.

The [current unit-runtime local image](../../docs/judge-readiness/current-runtime-20261023/README.md) includes
the tested unit/revision corrections and blind-data exclusion, with isolated capped replay/restart proof.
It predates the latest link/unit-instruction/status-merge corrections. It remains unpublished; final
validation, image rebuild, registry identity and release approval remain pending.
The earlier image evidence below stays historical. No registry or hosted durability proof is claimed.

Keep the GitHub repository variable `ENABLE_NEBIUS_JOBS` disabled and the application launcher settings
unset while these blockers remain. That variable is not an application environment switch.
Do not run old direct-job recipes. [Bounded rollout, IAM risks, expiry and rollback draft](rollout.pending.md)
fills the proposed public-platform choices; private inputs and the final image remain approval blockers.

## What is implemented and checked locally

`POST /api/watch/run` requires `X-Admin-Token` and an `Idempotency-Key` of 1–128 letters, digits, underscores
or hyphens. Repeating an existing key returns its existing job, including after it falls out of the public
five-job display. The controller keeps full history and blocks overlapping new requests; unknown cloud states
remain in flight. Only the documented `COMPLETED` mapping is initially assumed. A callback alone is not
proof that compute stopped.

The public browser shows status and the latest report; it cannot launch paid cloud compute. Browser-approved
items use **Check approved now** in-process. Cloud re-checks use the bundled watched list only.

The disabled nightly workflow requests this same controller with GitHub's private `SPECCHECK_ADMIN_TOKEN`
secret and `SPECCHECK_URL` variable. Its idempotency key uses the GitHub run ID. It neither signs into Nebius
nor directly creates a job. Configure/enable it only after hosted safety and one real job have passed.

Cloud commands require MysteryBox selectors for `NEBIUS_API_KEY`, `TAVILY_API_KEY` and `WORKER_TOKEN`.
Missing selectors disable launch; raw credential values are never put into command arguments. All tested
quality limits, including output/fix limits, are forwarded. This is fake-CLI evidence, not cloud validation.

`CONTROLLER_STATE_DIR` must be a dedicated mounted POSIX filesystem, with `CAMPAIGN_BUDGET_FILE` exactly
`<directory>/campaign.sqlite3`. Jobs receive neither the mount nor `ADMIN_TOKEN`. The authority marker binds
one VM boot identity; a process restart on that VM can resume, while VM reboot/replacement fails closed.
Use no second endpoint writer against the same filesystem. The explicit `scripts/transfer_authority.py`
prepare/export/receive protocol binds the destination boot/mount, fences the source before releasing a
snapshot, preserves receipts/holds and supports exact interrupted-transfer recovery. Writer cutover and
recovery after a destination reboot require pinned owner approval of the authenticated stopped-host
observation; the CLI does not itself verify cloud state. Do not copy a live wallet or run the legacy local
`install-controller` command as a remote migration. [Transfer commands, evidence and trust boundary](../../docs/judge-readiness/authority-transfer-20261023/README.md).

## Build preparation

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/release-mock.json
# Expected eval exit 1: raw 6/8 policy disagreements are disclosed, not rewritten.
.venv/bin/python scripts/check_pdfs.py --required --out /tmp/release-documents.json
cd web && npm ci && npm run test:presentation && npm run build
```

`data/documents.lock.json` freezes the 13 required public documents' hashes and source URLs. The Dockerfile
fetches missing PDFs, then requires every locked file to open and match. A blocked host or changed PDF fails
the build. Download blocked public files in a browser into their exact `data/raw/` paths; keep them out of Git.
A changed hash needs Kyle's source/text review before changing the lock. Never build a release that silently
substitutes fixture excerpts for missing native documents.

Pin the final image by digest after its clean build. The existing Dockerfile pins Python 3.12, Node 22 and
Nebius CLI 0.12.289. Verify the pinned CLI's local help against the final account/region before approving
commands; do not assume newer convenience flags exist. No final image digest has been produced here.

A [local packaging image](../../docs/judge-readiness/image-build-20261023/README.md) now builds at source
commit `b9de109`, with matching runtime code, all 13 locked PDFs, the real CLI 0.12.289, required help flags,
mock eval and a network-disabled API/static smoke. Its filesystem scan excludes configured keys and private
state. It is not published, is not the final release artifact, and proves no hosted behavior. The final
registry digest remains unset; rebuild from the final validated source before publication approval.

## Persistent application startup

The image now starts `python scripts/serve.py`. For a controller, mount its private POSIX filesystem at
`/controller` and set the nonsecret values in [controller.env.example](controller.env.example), supplying
credentials through the separately approved private selectors. Startup derives raw/upload/cache/run/score
and evidence paths under `/controller/app/`; requirements, fixed inputs and committed replay stay in the image.
It checks/atomically seeds locked public PDFs and refuses changed existing documents or escaping paths.
It never initializes or imports a wallet. Do not share this mount with jobs or expose it as an archive bucket.

The existing API can serve health while the wallet is absent, with paid admission blocked and project/watch
state unavailable. Prepare/export/receive the exact authority through the approved private transfer process.
The running API can then read it without reseeding. A replacement VM still needs owner-approved writer cutover.
Final publication, profile/secrets and any job-enabled settings must be pinned in the approved rollout manifest.

[Local build, actual ext4/synthetic transfer/restart proof and refusal tests](../../docs/judge-readiness/controller-startup-20261023/README.md)
verify this preparation locally. No real wallet transfer, hosted mount/reboot proof, deployment or final
registry image is established. The proof container was removed; the image remains local and unpublished.

## Current price worksheet

[Machine-readable rates, source hashes and forecasts](cost-manifest.json) were prepared from official public
pages read on October 23. These forecasts are not actual cloud charges or an approved spending allowance.
At 2 vCPU / 8 GiB, current component rates give **cpu-d3 $0.066/h** and **cpu-e2 $0.060/h** for compute.
The Intel Ice Lake option is documented for eu-north1 only; owner quotas/preset availability remain unchecked.
The new controller-storage rows include a separate 32-GiB SSD filesystem and bounded worker compute.
The initial 24-hour/two-job illustration is **$1.881085**, excluding public IP/egress, taxes and both
providers. Current public Virtual Networks and Container Registry pricing is free; SecretStash is free
during preview. [Actual response hashes and dates](../../docs/judge-readiness/preproduction-packaging-20261023/public-cost-addendum.json)
resolve those public rates without establishing private quotas, taxes or grant terms. The earlier general forecasts exclude durable storage and remain labelled as such.

Sources: [Compute rates](https://docs.nebius.com/compute/resources/pricing),
[Object Storage rates](https://docs.nebius.com/object-storage/resources/pricing),
[Serverless billing](https://docs.nebius.com/serverless/pricing-quotas).

The endpoint's container disk is removed on stop/delete. Persistent mounted resources have their own charges.
Shared filesystems document POSIX semantics within one VM and limitations for conflicting access across VMs;
that is not permission to share a SQLite wallet between endpoint and jobs.
[Endpoint lifecycle/storage](https://docs.nebius.com/serverless/overview),
[Filesystem guarantees](https://docs.nebius.com/compute/storage/types#posix-compliance-and-consistency-guarantees-for-filesystems).

Kyle must read the actual grant expiry, remaining cloud balance, region/IAM rights and billing scope from the
private console. Public builder-program expiry terms do not establish the terms of this hackathon grant.
The agent must finish the durable-authority design and costed resource manifest before requesting approval.

## Hosted proof, after approval

The agent will execute the approved plan and retain redacted evidence:

1. Create a bounded test endpoint from the immutable image, with controller-only authority and least-privilege
   credentials. Import the existing campaign state; never initialize a fresh zero wallet.
2. Run `python scripts/smoke.py "$SPECCHECK_URL" --preflight-only` first. This only reads configuration/health.
3. Run one authorized paid smoke with `ADMIN_TOKEN` in a private environment. It shares a run/item allowance
   across c01 and a tiny PDF and makes no automatic retries. Invalid/replayed/cached-only evidence fails.
4. Exercise public upload without the admin header, capped full-tray replay, source/archive retrieval and
   evidence/report persistence after an actual endpoint restart. Test corrupt/missing authority fail-closed.
5. Submit one authenticated idempotent manual job; verify its lease, actual usage, report, state strings and
   completion. Repeat the same launch/callback without a second charge or changed publication.
6. Verify concurrent scheduled/manual admission and unknown completion retain the allowance. Then test the
   disabled workflow once before Kyle decides whether to enable scheduling.
7. Restore temporary caps, capture console and browser evidence, document measured costs/timings, and prepare
   the final production/rollback commands for Kyle's approval. Do not infer a deployment from local tests.

Stop/delete only the resources explicitly included in that approved plan. Mounted storage may remain billable
when an endpoint is stopped; the final manifest must include its retention and cleanup policy.

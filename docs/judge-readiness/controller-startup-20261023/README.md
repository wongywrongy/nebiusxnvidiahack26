# Controller startup and uncertainty states — 2026-10-23

This is **local packaging and synthetic storage evidence**, not Nebius deployment, live accuracy or owner
approval. No real wallet was transferred. No provider calls, registry publication or cloud resources were
made. Cumulative actual spend remains **$2.5255318 / 419 credits**, no holds or persistent block.

## What changed

`scripts/serve.py` is the image's default command. Without a controller mount it starts the existing API.
With `CONTROLLER_STATE_DIR`, it first verifies the dedicated POSIX mount and exact wallet location, then
prepares persistent application paths. It neither creates a wallet nor imports/cuts over an authority.
The separate pinned transfer protocol remains mandatory; every paid admission still checks the authority.

| State | Location |
| --- | --- |
| Wallet / authority / private worker receipts | Private mount root, unchanged by startup |
| Required public PDFs | `<mount>/app/raw/`, seeded from the immutable image and checked against the reviewed lock |
| Uploaded PDFs and upload metadata | `<mount>/app/raw/uploads/` |
| Provider/document cache | `<mount>/app/cache/` |
| Runs and current scores | `<mount>/app/runs/` and its `scores.json` |
| Source archives and published watch evidence | `<mount>/app/evidence/` |
| Reviewed requirements, case inputs and committed replay | Remain in the immutable image; not copied over persistent state |

Seed publication is atomic and never replaces different existing bytes. Existing caches, uploads, runs,
authority and receipts remain. A changed stored document/manifest, bad image hash, unreadable PDF, escaping
path, wrong wallet path or unsupported/non-mounted directory refuses startup. The startup prepares only the
locked required PDFs; it does not copy private local caches, wallets, uploads or unreviewed validation sets.

The existing API already boots without a wallet: health reports accounting unavailable and zero remaining
allowance. Project/watch state returns 503 until the authority exists, and fresh scans refuse. After explicit
activation, the same process reads the imported authority; no new maintenance server or zero-wallet seed is
needed. A new VM boot still requires the existing approved cutover protocol. A process/container restart on
the same boot is not proof of VM replacement recovery.

Uncertainty wording also changes: absent **accepted** claims say `Couldn't confirm` / `Not confirmed`;
unconfirmed replacement rows no longer imply the document never stated a property. Both unconfirmed
currency-comparison paths now use `verdict=unverified` rather than an internal failure value. Outer decisions,
severity, quote gates and requirements are unchanged. Historical recordings remain untouched.

## Actual checks

- Full Python suite: **602 passed, 2 skipped in 31.93 seconds**; [actual output](pytest.txt).
- Mock run `20261023-061339-55e73a`: unchanged **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 fixes**,
  zero invalid items, one unnecessary note, 48/65 claims and 8/20 web values; [score](mock-score.json).
  Expected exit 1 preserves the disclosed selection-policy disagreements. Fresh charges are $0 / 0.
- Eleven synthetic startup tests cover repeated preparation, retained state, changed/unsafe/unreadable
  documents, wrong mount/path, no-wallet health/admission, generic refusal and the existing noncontroller command.
- The local image builds, including web packaging and all 13 locked native PDFs. Tag
  `speccheck:controller-startup-local`; local image/index ID
  `sha256:aa8292661e33256a99aa3758105ec484c2fd20faac291e69e12ae94ae60e6a7f`.
  [Metadata](image.json), [build footer](build-footer.txt), [matching runtime source hash](runtime-manifest.json).
  It is unpublished and not a final release artifact.
  Applying [source.patch](source.patch) to clean `23028a0` reproduces the tested runtime code hash and
  Dockerfile exactly; [actual reconstruction](source-reproduction.json).
- An actual **network-disabled** local container uses an ext4 bind mount and generated synthetic credentials.
  Before import it seeds **13/13** required readable PDFs, creates no authority/wallet and reports blocked
  accounting; [before](before.json). The mode field is a test configuration, not a successful provider call.
- A newly created **synthetic** wallet is explicitly prepared/exported/received using the existing transfer
  protocol; its source retires and the API sees its nonzero test seed. No owner approval or real authority is
  fabricated. [Synthetic import booleans/hashes](imported.json).
- `docker restart` preserves that synthetic state hash, authority marker and cache/upload/run sentinels.
  Project, scores, specs and app routes return 200; [actual restart probe](restarted.json). This is local
  container evidence only; Nebius single-VM filesystem, reboot and recovery behavior remain unverified.
- The real image refuses `/tmp` as an unmounted controller directory, exit **2**, before API startup;
  [generic response](refused-unmounted-directory.txt).
- A fresh image with no environment credentials reports all key-presence booleans false; `.env`, `.cache`,
  private spending state and uploads are absent from their application paths; [booleans](fresh-image-privacy.txt).
  This is a presence/path check, not a new whole-filesystem secret scan.
- Both GitHub workflows for preceding commit `23028a0` completed successfully; [observed jobs](preceding-ci.json).
  No current-source CI pass is inferred from that earlier commit.

All temporary containers were removed. The unpublished image and private synthetic files under `/tmp`
remain for reproduction. Synthetic amounts are not real spend and are not added to the campaign ledger.
[Actual campaign](campaign-status.json) and [day report](daily-ledger.json) remain unchanged. No new private
dashboard reading, invoice reconciliation, live evaluation or final recording is claimed.

## Reproduce and rollout boundary

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/controller-startup-mock.json
# Expected mock exit 1; raw key disagreements remain disclosed.
docker build --progress=plain --tag speccheck:controller-startup-local .
docker run --rm --network none speccheck:controller-startup-local
# Standard noncontroller mock API; stop this temporary container after inspection.
docker run --rm --network none --env SPECCHECK_MODE=mock --env CONTROLLER_STATE_DIR=/tmp --env CAMPAIGN_BUDGET_FILE=/tmp/campaign.sqlite3 speccheck:controller-startup-local
# Expected exit 2: /tmp is not a dedicated controller mount.
.venv/bin/python docs/judge-readiness/controller-startup-20261023/reproduce.py
# A fresh synthetic-only reproduction using the local Unix Docker socket; no real state is mounted.
```

For the persistence proof, use a new empty temporary private ext4 mount and a file containing **synthetic**
credentials, keep Docker networking disabled, and mount it at `/controller`. Call the existing
`authority_transfer.prepare/export/receive` only on a new synthetic source, retain its test hashes and
sentinel files, then restart the same container and compare. Never point this reproduction at the real wallet.
The [standalone reproducer](reproduce.py) creates its own temporary state/credentials, refuses a remote
Docker socket, disables container networking and removes only its newly created container. Its actual
[successful result](standalone-reproduction.json) repeats the seed/import/restart checks.

The [nonsecret controller template](../../../deploy/nebius/controller.env.example) pins the production caps
and previously authorized targeted quality profile. It grants no rollout approval. The final manifest still
needs the final source/image reference, private account/IAM/resource identities, current pricing and grant
expiry, operating/cleanup schedule and approved rollback/cutover commands. Jobs stay disabled until their
concrete plan is approved. G2 still has no passing replacement; broader validation, final recording and
hosted proof remain gated and agent-owned. The last targeted live panel belongs to source `23028a0`'s
recorded code before these startup/wording changes; it is not current-source release evidence.

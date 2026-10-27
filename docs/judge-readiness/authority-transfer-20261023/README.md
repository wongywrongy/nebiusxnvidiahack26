# Private accounting handoff — 2026-10-23

The transfer and writer-cutover tooling is implemented and tested with **synthetic wallets and simulated
mount/boot identities**. No cloud resource was created, no real wallet was exported, and no real cutover
approval was generated. This is local protocol evidence. Hosted filesystem, SSH, restart, control-plane
state and billing behavior remain unverified. G2–G5 remain open.

The complete regression suite passes **560 tests, 2 skipped in 30.79 seconds**. The raw mock run
`20261023-042244-894557` remains **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing fixes**,
zero invalid items and one unnecessary note. Mock fresh spend is $0 / 0. The actual campaign ledger remains
**$1.9702294 / 391 credits**, no holds; its real source is active and was not retired by this work.
The earlier sandboxed broader focused run was explicitly interrupted after it stopped progressing; it
does not count as a passing run. The completed full suites ran outside that restricted environment.

## What the protocol guarantees locally

`scripts/transfer_authority.py` is an explicit operator CLI. It performs no network calls, creates no
resources and prints only artifact hashes, campaign identity and non-secret authority metadata. Its private
artifacts contain accounting history and worker receipts; keep them under ignored `evidence/` or on the
approved private mount, outside git. Transport uses authenticated private SSH/SCP after rollout approval.

1. **Prepare on the destination.** A private `handoff.json` binds a random nonce, the absolute mount path,
   the VM boot ID and the resource ID. The mount must pass the existing dedicated POSIX-filesystem guard.
2. **Export at the source.** Pin the request hash from its trusted destination. An immediate SQLite
   transaction validates the entire wallet and receipt history. Active requests and unsettled jobs refuse
   transfer. Already-unknown holds may transfer only with their accounting block retained.
3. **Fence before releasing.** The source is retired to the exact portable snapshot hash before its export
   becomes available. All later source mutations, including settlements and attempts to unretire it, fail.
   A failed output write can be retried only for the same destination and snapshot. A fenced snapshot can
   be recovered read-only after source boot loss; this cannot reactivate the source.
4. **Receive at the bound destination.** Pin the export hash printed at the source. Verify the destination,
   full state, every receipt path and receipt hash. Publish private files atomically, with restrictive
   permissions and fsync. The activation marker is last. Interrupted imports can resume from identical
   state, while a changed staged wallet refuses overwrite. Retrying an active import preserves later spend.
5. **Replace a boot explicitly.** An unapproved boot cannot use the wallet. Cutover needs a recent,
   hash-pinned owner approval binding the previous marker, campaign, old/new boots and old/new resources.
   Retired authorities and unsettled jobs refuse cutover; unknown usage remains blocked. The normal
   transaction path rechecks writer ownership after obtaining the SQLite lock.
6. **Recover a destination reboot during import.** Preserve the original request and export. A separate
   owner-approved recovery record must bind that request hash and exact transfer hash to the new boot.
   The original snapshot and source fence do not change. An old import cannot reactivate a cut-over wallet.

The tests include incorrect hashes/boots/requests, object mounts, active requests, unsettled jobs,
missing/corrupt receipts, lost output after fencing, changed staged state, post-activation fsync failure,
labelled synthetic owner approvals, expired or incorrect approvals and duplicate operations. They also
check original UTC charges, phase allocations, unknown holds, full job history and private file permissions.
No keys or wallet bodies are printed by CLI errors.

## Trust and hosted limits

The cutover approval is an **operator-pinned local record, not authenticated cloud evidence by itself**.
Before preparing a real record, the agent must capture and authenticate the previous endpoint's actual
stopped state and obtain Kyle's approval of the concrete cutover. Never infer that a VM stopped from an
HTTP failure, timeout, callback, unknown state or copied JSON. The CLI accepts the documented `STOPPED`
state; it does not infer deletion from a missing response. No real approval is stored in this checkpoint.

Nebius documents endpoint container-disk removal on stop and separate persistence/billing for mounted
storage. It also documents SSH access to managed workload VMs.
[Endpoint storage and access](https://docs.nebius.com/serverless/overview).
Shared-filesystem POSIX guarantees apply within one VM; conflicting access across VMs has weaker guarantees.
Keep exactly one active controller VM, and never mount its wallet into jobs.
[Filesystem guarantees](https://docs.nebius.com/compute/storage/types#posix-compliance-and-consistency-guarantees-for-filesystems).
The control-plane `status.state` field documents `STOPPED` for endpoints.
[Endpoint lifecycle](https://docs.nebius.com/serverless/lifecycle).

These public documents support the design constraints. They do not prove this account's permissions,
mount behavior, durability, quotas, image compatibility or successful deployment. The immutable resource,
storage, startup/persistence, IAM, expiry/cost and rollback plan still needs completion and approval.
Keep the retired source and all private handoff artifacts for reconciliation; never reset accounting.

## Commands after concrete rollout approval

The following are the intended command shapes, with placeholders rather than invented resource IDs or
approvals. Run them only after the approved host has its private mount, authenticated access and secure
provider environment. The agent executes these steps; Kyle reviews the resulting evidence.
Keep paid API processes stopped or in maintenance until transfer/cutover succeeds and the retained totals
and holds have been checked. The deployment startup/maintenance mechanism is part of the pending resource plan.

```bash
# Destination host, before starting the paid API:
python scripts/transfer_authority.py prepare /mnt/controller --resource-id <actual-endpoint-id>
# Securely copy /mnt/controller/handoff.json back to ignored evidence/controller-bootstrap/.
# Verify its printed hash through the authenticated destination session.

# Source host. This retires the source, so no further local live validation may start afterward:
.venv/bin/python scripts/transfer_authority.py export evidence/budget/campaign.sqlite3 evidence/controller-bootstrap/handoff.json evidence/controller-bootstrap/transfer.json --sha256 <request-hash>
# Securely copy the resulting private export to the destination. Pin the source's printed export hash.

# Destination host:
python scripts/transfer_authority.py receive /private/transfer.json /mnt/controller --sha256 <export-hash>
# Configure CONTROLLER_STATE_DIR=/mnt/controller and CAMPAIGN_BUDGET_FILE=/mnt/controller/campaign.sqlite3.
# Confirm the imported campaign/day/phase totals and holds before serving paid requests.

# Only after authenticated stopped-host observation and Kyle's concrete approval:
python scripts/transfer_authority.py cutover /private/cutover-approval.json /mnt/controller --sha256 <approval-hash>

# If the prepared destination rebooted before import finished, use its distinct recovery approval:
python scripts/transfer_authority.py receive /private/transfer.json /mnt/controller --sha256 <export-hash> --proof /private/import-recovery-approval.json --proof-sha256 <recovery-approval-hash>
```

The agent prepares real approval records from authenticated observations for Kyle to review. They contain
version, approver, aware observation/approval times, observed state, campaign ID, exact previous authority
hash, old/new resource IDs and old/new boot IDs. Import recovery additionally binds the original request
hash and transfer hash. An approval expires after one hour. No script self-approves or contacts Nebius.

Failures retain the original financial state. Preserve artifacts and diagnose before retrying; never delete
the wallet or marker to make an import work. Repeating `prepare`, `export`, `receive` or `cutover` is allowed
only under its documented same-identity conditions. Unknown usage still needs owner billing reconciliation.

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q tests/test_authority_transfer.py tests/test_authority.py tests/test_campaign.py
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/authority-transfer-mock.json
# Expected eval exit 1: the documented raw-key disagreements remain visible.
.venv/bin/python scripts/campaign_budget.py status
```

No broader scoring-set validation, blind evaluation, final recording or deployment allowance was consumed.

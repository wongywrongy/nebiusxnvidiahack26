# Controller protocol checkpoint — 2026-10-23

This is offline controller/worker evidence, not a deployment or a completed readiness gate. No provider
calls or cloud resources were made. The original keys, reviewed checklists and recording remain unchanged.

The controller imports an existing wallet into its own mounted POSIX filesystem, fences the source, and
binds the authority to one VM boot identity. Object mounts, missing/corrupt identities and another VM fail
closed. A process restart on the same VM retains authority. VM reboot/replacement requires an explicit
cutover; cross-VM SQLite sharing and automatic snapshot recovery are unsupported.

Each job receives one prepaid allowance, one worker session and an immutable code/configuration/document
manifest. It gets provider credentials and a separate signed-callback credential, with no admin credential,
controller filesystem or shared archive write path. Its local wallet cannot exceed the assigned allowance
and is sealed before reporting. The controller retains the private hashed receipt before attempting
publication. Only a matching receipt plus independently observed terminal cloud state can settle known
charges and publish a complete valid report. Missing/unknown usage keeps its hold; known charges retain
their original UTC dates. Duplicate launches and callbacks do not pay or publish twice.

The independent AI review found three general failures, fixed and covered by regressions:

| Before | After | Reproduction |
| --- | --- | --- |
| A retired source could initialize a different volume at the same pathname | Every retired source requires explicit reconciliation | `test_retired_source_cannot_initialize_another_volume_at_the_same_path` |
| Receipt loss retained the allowance but did not persist a global accounting block | Loss/corruption/archive failure persists a reconciliation block until the original evidence can be verified | `test_receipt_loss_blocks_other_paid_work_until_original_receipt_is_restored`; `test_evidence_failure_retains_durable_receipt_and_hold_until_identical_retry` |
| Launch accepted URL paths rejected by the worker | Both sides require the same HTTPS origin before any reservation or cloud create | `test_bad_controller_origin_is_rejected_before_reserving_or_creating` |

Additional tests cover allowance admission before CLI launch, ambiguous creation, concurrent admission,
one-session claims, process restart, invalid evidence, unknown usage, receipt path/hash validation, directory
fsync, original-day accounting and full history beyond the five-job public display. The review found no
additional concrete issue in these paths; that is not a hosted durability certification.

## Reproduce

```bash
SPECCHECK_MODE=mock .venv/bin/python -m pytest -q
SPECCHECK_MODE=mock .venv/bin/python scripts/eval.py --out /tmp/controller-mock.json
# Expected eval exit 1: unchanged raw key, disclosed 6/8 selection-policy panel.
.venv/bin/python scripts/campaign_budget.py status
```

[Full pytest output](pytest.txt), [mock scoreboard](mock-score.json), [mock output](mock-eval.txt) and
[campaign status](campaign-status.json) preserve the measured results. Mock costs are estimates; fresh
charges are zero. [Verification](verification.json): **435 passed, 2 skipped in 21.08 seconds**. Raw mock
remains **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 passing replacements**, with no invalid items,
one unnecessary note and **48/65 claims / 8/20 web values**. Cumulative actual spend stays **$1.4867368 /
359 credits**, with no holds. Previous browser/build evidence is linked in the [reliability checkpoint](../reliability-20261023/README.md);
no frontend code changed here, and those checks were not rerun.

## Still agent-owned

Remote source-fencing/export/import and approved writer-cutover tooling are unfinished. The current
`install-controller` command is a cold import with direct access to the authoritative source; copying a
live local wallet to a remote VM does not fence the original. An interrupted import leaves the source
retired and needs explicit reconciliation. No actual campaign wallet was moved or reset in this checkpoint.

The immutable image, mounted filesystem/account support, IAM, cost/expiry/rollback manifest and hosted
restart/storage/job proof remain pending. G2 still lacks a passing replacement; final case/sample/blind
validation, release promotion and public recording remain pending their gates. See [ownership](../ownership.md).

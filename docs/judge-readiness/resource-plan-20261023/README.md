# Public resource-plan evidence — 2026-10-23

**Unapproved preparation only.** No account lookup, resource creation, image publication, hosted run or
real wallet transfer occurred. The proposed [bounded rollout](../../../deploy/nebius/rollout.pending.md)
now specifies resource/storage paths, credential boundaries and IAM risks, a 24-hour trial, expiry/stop
rules, admission/transfer sequence and rollback. Final image, private account inputs, full cost bounds and
owner approval are still required; null manifest fields deliberately block approval.

[Unauthenticated HTTP observations](public-source-observations.json) record actual source hashes/statuses
and times, without storing full documentation bodies. The official endpoint reference and the pinned CLI
both support a filesystem `--volume`; local network-disabled CLI output is in
[endpoint help](endpoint-create-help.txt) and [filesystem help](filesystem-create-help.txt).
They prove syntax only, not permissions, service availability or a real mount.

The worksheet includes private SSD filesystem costs. A Decimal assertion independently recomputed every
resource subtotal within $0.000000001; [check](forecast-check.json). The proposed 24-hour endpoint plus
two bounded one-hour jobs totals **$1.881085**, excluding registry/IP/network/egress, taxes and both
providers. The public network pricing page returned HTTP 200 but exposed no usable table through the web
reader; no zero price is assumed. Forecasts are not actual cloud bills or approved spending.

The environment template previously set `ENABLE_NEBIUS_JOBS=false`, but that variable controls only the
GitHub workflow. Source inspection shows the app instead gates job launch on its launcher profile/image/
URL/secret settings. The unused environment assignment is removed and the draft says to leave those
settings absent until manual commissioning. No new application switch or runtime change was added.

```bash
docker run --rm --network none --entrypoint nebius speccheck:controller-startup-local compute filesystem create --help
docker run --rm --network none --entrypoint nebius speccheck:controller-startup-local ai endpoint create --help
```

The existing local image contains CLI 0.12.289 but predates the latest pipeline fixes. Its use here proves
local CLI syntax only. No containers from these `--rm` invocations remain. The agent still owns the final
image/IAM/complete-price binding and all hosted execution after separate concrete approval.

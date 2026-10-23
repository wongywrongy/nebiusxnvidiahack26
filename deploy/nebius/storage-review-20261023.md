# Public storage/resource review — 2026-10-23

No deployment is approved or executed. This review fills public-platform facts in the proposed Endpoint +
Jobs plan; account availability, credentials, quotas and grant expiry remain unverified.

Endpoints explicitly support a shared filesystem mounted by ID or name, using
`--volume '<filesystem-id>:/controller:rw'`. The reviewed configuration keeps this private mount on one
controller and omits it from workers. [Endpoint volume reference](https://docs.nebius.com/serverless/endpoints/manage).

Shared filesystems are mounted through virtiofs. Full POSIX semantics apply within one VM; cross-VM
conflicting access has weaker guarantees. This supports the existing single-writer restriction, not a shared
SQLite writer pool. The hosted mount and reboot/cutover behavior still need actual proof.
[Filesystem guarantees](https://docs.nebius.com/compute/storage/types#posix-compliance-and-consistency-guarantees-for-filesystems).

The published `cpu-d3` catalog includes `2vcpu-8gb` in `eu-north1`. This is a proposed preset/region, not
proof of this account's capacity. [Platform/preset catalog](https://docs.nebius.com/compute/virtual-machines/types).
Use a regular CPU workload, one controller, a 32-GiB boot disk and a separate 32-GiB private filesystem.
The worker command already specifies the same preset, a 32-GiB boot disk, one-hour job timeout and no restart.
The initial two-job estimate covers manual plus scheduled commissioning; longer scenarios assume one job/day.

The current published USD rates are $0.015/vCPU-hour, $0.0045/GiB RAM-hour, $0.071/GiB per 730 hours for
network SSD disk, and $0.08/GiB per 730 hours for shared SSD filesystem.
[Compute and volume pricing](https://docs.nebius.com/compute/resources/pricing).
The machine-readable [worksheet](cost-manifest.json) computes resource-only forecasts from these rates,
including both the endpoint disk and the private filesystem. It excludes registry/IP/network/egress, taxes
and both providers. These are estimates, not an approved total budget or measured cloud spend.

Stopping an endpoint removes its container disk; a mounted filesystem remains separately billable.
The final approval must pin UTC operating/stop dates, grant expiry, filesystem retention and cleanup.
[Serverless lifecycle and billing](https://docs.nebius.com/serverless/overview),
[Serverless pricing](https://docs.nebius.com/serverless/pricing-quotas).
The public Virtual Networks pricing page did not expose a usable price table in this read; no zero network
cost is assumed. Private billing/availability and a complete reviewed rollout/rollback manifest are still
required before any resource action.

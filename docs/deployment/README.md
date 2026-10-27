# Deployment evidence — October 27, 2026

[Local packaging proof](packaging.json) covers the clean image at `7dce26a`: all 13 locked public PDFs and the committed live recording, no configured provider keys, no networking, real native page rendering, and persisted allowance/upload state after replacement of the container. The accounting amount used in that restart test is synthetic and never represents a provider charge.

The source passed 767 Python tests / 2 skipped, with the unchanged raw mock panel and a clean web build. PR #13 is merged; deployment preparation is in PR #14.

The image is published and anonymously readable at its pinned GHCR digest. The first Nebius attempt in `eu-north1` failed validation with `ResourceExhausted: compute.instance.non-gpu.vcpu (limit 0, requested 2)`. Storage creation succeeded; the unused filesystem and secret from that region were deleted. [Recorded outcome](nebius-attempt.json).

The tenant quota list subsequently confirmed 200 unused non-GPU vCPUs in `eu-west1`. Endpoint creation there passed validation and was accepted as `aiendpoint-e01kyrtp1ayc0j6nj8`, with its own persistent filesystem. Fly login is stopped. Public health, smoke and private-browser checks remain pending; no cloud-job execution is claimed.

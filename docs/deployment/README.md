# Deployment evidence — October 27, 2026

[Local packaging proof](packaging.json) covers the clean image at `7dce26a`: all 13 locked public PDFs and the committed live recording, no configured provider keys, no networking, real native page rendering, and persisted allowance/upload state after replacement of the container. The accounting amount used in that restart test is synthetic and never represents a provider charge.

The source passed 767 Python tests / 2 skipped, with the unchanged raw mock panel and a clean web build. PR #13 is merged; deployment preparation is in PR #14.

The image is now published and anonymously readable at its pinned GHCR digest. Nebius endpoint validation failed because non-GPU CPU quota is zero; the unused filesystem and secret created for that attempt were deleted. [Recorded outcome](nebius-attempt.json). The approved Fly fallback is prepared and awaits account login. No public health, smoke or cloud-job result is claimed.

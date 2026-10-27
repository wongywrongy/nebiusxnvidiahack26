# Local image packaging — 2026-10-23

Built and checked locally from commit **`b9de109842e9d5bcbcd48e11bc27d3419ec0c761`**.
The image is **not published or approved for release**. No cloud resource was created. This checkpoint
verifies packaging; it adds no live accuracy, hosted persistence, deployment or scheduled-job evidence.

Local tag: `speccheck:readiness-b9de109`.
Docker reports local image/index identity
`sha256:653211984dbebafe719ad79b666043f0db0aeddace2f9b1b12392a4c496dd528`.
The [build footer](build-footer.txt) also records the platform manifest and config hashes. This local
identity does not establish a registry-published, deployable reference. The final registry digest remains
unset in the deployment cost manifest. The local image occupies 687,135,607 bytes as reported by Docker.

## Actual checks

| Check | Result and limit |
| --- | --- |
| Docker build | Passed, including clean web dependency/build steps and required native-document preflight. Public package/image downloads are build traffic, not provider calls. |
| Required PDFs inside image | **13/13** locked documents pass hash/readability checks; [report](required-pdfs.json). |
| Runtime source identity | Image code hash matches the tested source; [runtime manifest](runtime-manifest.json). Its mock/default configuration is not the approved targeted live profile. |
| Pinned CLI | `nebius version` returns **0.12.289**. The initial `--version` probe exits 2 because that flag is unsupported; both responses are retained. |
| Actual CLI syntax | Real profile-create, job-create/get/get-by-name and endpoint-create help includes the flags used by SpecCheck; [create excerpts](cli-help-excerpts.json), [remaining flags](remaining-cli-help.json). Help does not establish credentials, quotas, preset availability, valid secret contents or successful cloud calls. |
| Image mock evaluation | Run **`20261023-043429-5814d5`**: **6/8 calls, 5/6 problems, 0/2 major false alarms, 0/5 fixes**, no invalid items, one unnecessary note; [scoreboard](mock-score.json). Expected exit 1 preserves the documented selection-policy disagreements. Fresh provider spend is $0 / 0. |
| Temporary image API | Network-disabled API serves health, project, scores, index HTML and both generated JS/CSS assets with HTTP 200; [probe](packaging-probes.json). No host port was opened. |
| Bundled scoreboard | `/api/scores` serves the historical live recording **`20261022-181611-a9d0b5`**, 6/8, while this API is in mock mode. Its live label belongs to that dated recording; it is not a new live evaluation or the pending final recording. |
| Privacy | **8,566 files** scanned: none contains the configured provider/admin key strings. Direct `settings.keys_present` reports false for all three. `.env`, `.cache`, the private spending directory and uploaded PDFs are absent; [booleans](image-secret-scan.json). |
| Cleanup | Every temporary container created for these checks was removed. The local image remains available. No registry push or cloud mutation. |

All verification containers used `--network none` and received no credentials or real wallet. The initial
HTTP probe requested a nonexistent `keys_present` response field; its null is retained in that probe.
The correct direct `settings.keys_present` check is separately recorded in the filesystem scan. No key
value was printed or placed in the image. Source `.cache/`, `.env`, wallet and uploads remain untouched.

The source commit's GitHub CI passed Python, mock eval, presentation/build and eight Chromium journey
checks; [job evidence](source-ci.json). Its local full suite passed 560 tests, 2 skipped, as recorded in the
[authority-transfer checkpoint](../authority-transfer-20261023/README.md). No new production code or UI
changed during image verification, so those regressions were not repeated here.

Campaign usage remains **$1.9702294 / 391 Tavily credits**, no holds. Image preparation adds $0 / 0 provider
spend. The local image and offline API are not deployment success. G2 still lacks a passing replacement;
blind-label review, broader validation, final recording and cloud approval remain pending.

## Reproduce

Use a clean checkout of the recorded source commit, Docker and the 13 public PDFs matching
`data/documents.lock.json`. `.dockerignore` excludes credentials, the real wallet/cache and uploads.

```bash
docker build --progress=plain --tag speccheck:readiness-b9de109 --iidfile /tmp/speccheck-image.iid .
docker run --rm --network none --entrypoint nebius speccheck:readiness-b9de109 version
docker run --rm --network none --entrypoint nebius speccheck:readiness-b9de109 ai job create --help
docker run --rm --network none --entrypoint nebius speccheck:readiness-b9de109 profile create --help
docker run --rm --network none --env SPECCHECK_MODE=mock --entrypoint python speccheck:readiness-b9de109 scripts/check_pdfs.py --required
docker run --rm --network none --env SPECCHECK_MODE=mock --entrypoint python speccheck:readiness-b9de109 scripts/eval.py --out /tmp/image-mock.json
# Expected mock exit 1; no provider calls. Rebuilt base-image/package metadata may produce a different digest.
```

For the smoke, start a temporary container from this image with networking disabled, run local HTTP probes
through `docker exec` against container loopback, then remove that container. Keep the API in mock mode.
The real deployment still needs the final image publication, maintenance/startup and persistent app-state
layout, private controller mount, authenticated transfer, IAM, price/expiry review and rollback plan.

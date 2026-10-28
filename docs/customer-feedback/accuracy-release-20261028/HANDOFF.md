# Deploy handoff for the Nebius session

Source: branch `release/accuracy-20261028` (local commit; PR #20 code plus the new recording and evidence). Kyle approved replacing the endpoint, same as the morning release. Freeze by **19:00 PT October 28 = 02:00 UTC October 29**.

1. **Image.** Build per `deploy/nebius/README.md` from a clean tracked checkout of this commit plus the 13 locked public PDFs. It must contain `runs/recorded/20261028-171142-5ca0fc/` and **no** `runs/scores.json`. Push an immutable GHCR tag and deploy by digest.
2. **Endpoint.** Create a new endpoint from that digest with the morning settings (`cpu-d3`, `2vcpu-8gb`, 32 GiB disk, port 8000, `--auth none`, judging env, MysteryBox secrets), mounting `computefilesystem-e01syzwfv7rqexfcys` at `/state`. **Stop `aiendpoint-e01fxw4c8jd1yq6nn5` before the new one writes.** Record the judging ledger before and after the switch; the last public reading was **$1.15974648 / 324 credits**, no holds.
3. **Vercel.** Point `deploy/vercel/vercel.json` at the new tunnel origin and redeploy. The stable URL stays https://speccheck-wongywrongys-projects.vercel.app.
4. **Public checks through the Vercel URL.** `python scripts/smoke.py <url>` with no admin token; the five browser journeys a–e via `docs/playground/capture.mjs`; the memo/PDF; Check approved now. Confirm `/api/scores` and the Scoreboard show run **`20261028-171142-5ca0fc`** (6/8, 5/6, 0/2, 0/5, wrong-spec 0/14). If they still show `20261028-065522-3dd974`, a `/state` scores file or a newer archived `evidence/scores.json` is overriding the recorded run (`api/main.py` `scores()`). Report that; do not delete state without Kyle.
5. **Delete the old endpoint only after step 4 passes.** Keep the filesystem.
6. **Docs.** Fill the deployment section of `README.md` in this folder, the endpoint/origin/digest/run in `docs/deployment/README.md` and `final-deployment.json`, and a new `freeze.json`. Add the hosted charges to `accounting.json`. Do not push without Kyle's permission.

Local spend so far: $0.83968200 / 27 credits (recording + wrong-spec), cron run $0.

## Completed by Codex

Public deployment and checks completed October 28, 18:43 UTC. Runtime source `a81d9d2` fixes the approved fresh-draft regression beyond `8f91ae9`; image, endpoint, Vercel deployment, evidence, accounting and freeze are in [README.md](README.md) and [final-deployment.json](../../deployment/final-deployment.json). All required public gates passed before both stopped endpoints were deleted. The retained filesystem remains.

Review local branch `deploy/accuracy-release` at `.cache/accuracy-deploy`; root `video/pipeline` was left untouched. The runtime fix is also on `fix/public-draft-gate` at `a81d9d2`. Smoke-tool commit `20cca85` preserves cached product evidence and uses a labelled new PDF probe. No Git push, PR #20 merge or new CI run was performed. The remote merge state remains a review item; this deployment uses the explicitly handed-off local release tree plus the approved fix.

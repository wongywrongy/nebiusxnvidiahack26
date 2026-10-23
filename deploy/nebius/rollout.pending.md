# Proposed bounded rollout — requires final validation and owner approval

This plan creates nothing. G2 is open; the published release image, private identities and billing/expiry facts are
not available yet. Null fields in `cost-manifest.json` are blockers, not permission to guess defaults.
The agent owns filling and executing this plan after the gates. Kyle supplies private account access,
grant terms and approval of the final concrete resources/costs.

## Resources and data paths

| Resource | Proposed configuration | Lifetime / authority |
| --- | --- | --- |
| Controller endpoint | Regular `cpu-d3`, `2vcpu-8gb`, 32-GiB container disk, image pinned by registry digest; `python scripts/serve.py`, HTTP 8000 | One running VM; initial 24-hour validation window only |
| Controller filesystem | Same project, `network_ssd`, 32 GiB, 4096-byte blocks, deletion protection, mounted `/controller:rw` | Independent private volume; exactly one controller VM; no worker attachment |
| Re-check jobs | Existing command: same image/preset, 32-GiB disk, `--timeout 1h`, no restart | One unsettled allowance/job at a time; ephemeral child wallet, no controller mount/admin credential |
| Evidence | `/controller/app/evidence`, served through the existing application | No new archive bucket required for the proposed first trial; private receipts/wallet never public |

`eu-north1` is proposed, subject to the owner's project and quota. Public documentation supports the
filesystem mount; hosted locking, persistence, permissions and cold/replacement boots still need proof.
[Storage facts and rates](storage-review-20261023.md). Keep locked inputs/reviewed requirements/recording
in the image; persist uploads/cache/runs/evidence with the controller startup already tested locally.

The public demo uses the managed HTTPS URL and application admin authentication. Endpoint-wide bearer
authentication would prevent a judge's unauthenticated browser/upload flow. Omit `--auth token` for the
approved public trial, retain mandatory application admin/worker authentication, and verify public access
on the actual account. The managed URL does not itself require `--public`; temporary SSH adds a dynamic
IP, whose quota and price must be confirmed. Neither an IP nor network cost is assumed free.

## Identities and secrets to pin before approval

Record actual tenant/project/subnet, endpoint/filesystem names, SSH public-key fingerprint, service-account
ID/public-key ID, registry reference and exact secret **version selectors** in the private approved manifest.
Never place a PEM, provider key, admin token or worker token in git, CLI arguments or evidence output.

- The deployment operator needs documented endpoint/filesystem creation rights. The controller's job
  launcher uses the existing project-scoped service-account profile and the three worker secret selectors.
  The public role reference documents `editor` for creation and separately `mysterybox.payload-viewer`
  for payload access; `editor` does not imply secret read. Scope payload access to the three worker secrets.
- Do not grant tenant admin. The documented project `editor` role is broad: it can modify resources,
  including storage in that project. A separate worker project would reduce that exposure, but cross-project
  secret/registry access is unverified. The final IAM/account review must choose and verify the isolation;
  this draft does not claim a granular job-only role exists or that the broad grant is least privilege.
- Controller secret injection covers the two providers, admin token, worker token and launcher PEM.
  Workers receive only provider credentials and worker token through selectors, never the admin token,
  launcher PEM or private filesystem. Verify the actual job spec and denied access during commissioning.
- Pin nonsecret caps/quality from `controller.env.example`. Keep launcher profile/image/URL unset until
  manual job commissioning is approved. `ENABLE_NEBIUS_JOBS` is a **GitHub repository variable**, not an
  application switch; setting it in the endpoint environment does not disable the admin job API.

[Official roles](https://docs.nebius.com/iam/authorization/roles),
[official endpoint flags](https://docs.nebius.com/serverless/endpoints/manage).

## Cost, expiry and operating window

The checked worksheet includes endpoint compute/boot disk, the private filesystem and bounded job compute:

| Illustration | Controller hours | One-hour jobs, maximum | Resource subtotal USD |
| --- | ---: | ---: | ---: |
| Initial trial | 24 | 2 | 1.881085 |
| One week | 168 | 7 | 12.683808 |
| Fifteen-day illustration | 360 | 15 | 27.179589 |
| Fifty-four-day illustration | 1296 | 54 | 97.846521 |

These are computed forecasts, not bills or approved allowances. Current public pricing makes Virtual
Networks and Container Registry free, and SecretStash free during preview; [actual public responses](../../docs/judge-readiness/preproduction-packaging-20261023/public-cost-addendum.json)
resolve those service-rate questions. Public IP/egress, taxes, Token Factory and Tavily remain excluded
and must be bounded before final approval. Free Virtual Networks does not establish free public IPs or traffic. A stopped
endpoint still leaves the private filesystem billable: 32 GiB costs $2.56 per 730 retained hours at the
published rate. Deletion protection deliberately prevents accidental wallet deletion.

The official [testing requirement](https://nebiusglobalaihackathon.devpost.com/rules) calls for judge access
through December 15, 2026, 12:00 PST / 20:00 UTC. This initial trial does not establish that delivery window.
Before submission, pin a separately approved accessible build/demo route and its funding, provider grant
expiries, stop/recovery plan and final artifact. Do not extend this trial or enable an indefinite schedule
by inference. The [official FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs) identifies the
published promotional credits as Token Factory credits, with no separate published AI Cloud grant;
private cloud funding must be verified. The accepted Endpoint + Jobs commissioning scope stays in force.
[Actual rules/source check](../../docs/judge-readiness/submission-requirements-20261023.md).

The initial trial must have an actual UTC start and stop time. Proposed stop time is the earlier of
start + 24 hours and verified cloud-grant expiry minus 24 hours; refuse a trial with no positive window.
Record separate cloud/Token Factory/Tavily balances and expiration terms. The Token Factory grant is not
assumed to pay Compute charges. The agent owns the stop operation and evidence capture at the approved
deadline; this draft provides no automatic shutdown or cloud-budget enforcement.

Keep the existing campaign authority and $20 / 2,000-credit whole-pass ceiling. Production day caps remain
$8 / 600 credits. The single watched item currently reserves at most $3 / 60 credits per cloud job; a
54-job compute illustration does **not** authorize 54 provider allowances. No wallet reseeding or ceiling
increase is implied. Capped-day replay must work. GitHub's `09:17 UTC` schedule remains disabled until a
manual job and one explicitly requested workflow run settle correctly. Afterward, any enabled schedule
must have an approved stop/expiry review, not an indefinite promise of nightly operation.

## Execution and rollback, after concrete approval

1. Freeze final validation source/inputs/configuration and build/scan that exact image; publish only after
   registry approval, verify its digest, then fill the final manifest. The [current local candidate](../../docs/judge-readiness/current-runtime-20261023/README.md)
   contains tested runtime `a9df48c`, the unit/revision corrections and blind-PDF exclusion, with synthetic full-tray
   capped replay/restart proof. It predates source `e1a4c2e` and must be rebuilt from final validated source.
   It is unpublished and not release-approved. Earlier image proofs remain historical.
2. Verify account permissions, region/preset/quota, complete price bounds and actual stop/expiry fields.
   Create only the approved private filesystem and endpoint. Start with paid admission blocked because
   no wallet exists; launcher settings remain absent. Confirm mount/boot/resource identities privately.
3. Use the [existing pinned transfer protocol](../../docs/judge-readiness/authority-transfer-20261023/README.md).
   Prepare the actual destination, pin its hash via authenticated access, finish local paid validation,
   fence/export the real source, privately transfer exact artifacts and receive at the bound destination.
   Compare full campaign/day/phase charges, holds and receipts. Never initialize a zero wallet.
4. Read-only preflight, bounded fresh public upload/smoke, capped full-tray replay and source/archive checks
   precede job commissioning. Prove process restart preservation, then separately observe a real stopped
   endpoint and obtain approval for the new-boot cutover before restart paid admission. Test corrupt/missing
   authority refusal without modifying the only good authority or receipt copy.
5. Configure the approved launcher identity/selectors and immutable worker image. One manual job and one
   requested workflow run must prove authenticated idempotent admission, bounded child spend, actual cloud
   states, terminal compute and signed receipt settlement/publication. Unknown state/usage remains held.
   Restore temporary caps; enable the daily schedule only on a further explicit owner decision.
6. At failure or trial expiry, disable the GitHub schedule first, block new paid/job admission and inspect
   all active jobs/holds. A timeout is not proof compute stopped. Stop/delete only approved compute after
   authenticating state, retain the private filesystem and exact artifacts, and document continuing storage
   charges. An old local source remains fenced. Resuming another VM or rolling back an image requires the
   same pinned, source-fenced full-state transfer/cutover; never restore a stale wallet snapshot or delete
   a marker to restart. A safe read-only replay/demo may remain separate from paid execution.

Final commands must use the actual approved IDs and pinned CLI. Local `--help` checks confirm filesystem
create flags, endpoint volume/secret injection, default auth and public-IP semantics; no command in this
review authenticates to Nebius or creates a resource. The remaining hosted assertions are work to execute,
not tasks handed to Kyle to debug.

# SpecCheck on Nebius AI Cloud

One image serves the FastAPI/React demo as a **Serverless Endpoint**, runs watched-item re-checks as
**Serverless Jobs**, and runs evaluations as jobs. A mounted **Object Storage** bucket holds source text,
approved/watched submittal PDFs, and evaluation scores. Models run on Token Factory; Tesseract runs locally.

All development checks use fixtures, respx and a fake CLI. **No deployment, provider key, paid call or credit
was used to validate this change.** Commands below are for the owner when live work is authorized.
Check the AI Cloud credit expiry in Billing before deploying.

## Prepare the image and identity

```bash
# From the repository root. The Dockerfile includes CLI 0.12.289 and local OCR.
docker build -t ghcr.io/<owner>/speccheck:latest .
docker push ghcr.io/<owner>/speccheck:latest
# Make the GHCR package public, or configure a registry secret separately.
curl -fsSL https://artifacts.nebius.cloud/cli/install.sh -o /tmp/install-nebius.sh
NEBIUS_CLI_VERSION=0.12.289 bash /tmp/install-nebius.sh
```

The public installer resolved stable to **0.12.289 on 2026-10-13**. Its `version` and local help were checked;
installation does not authenticate or create cloud resources. The Dockerfile pins `NEBIUS_CLI_VERSION`.
Sources: [CLI installation](https://docs.nebius.com/cli/install),
[job flags](https://docs.nebius.com/cli/reference/ai/job/create),
[endpoint flags](https://docs.nebius.com/cli/reference/ai/endpoint/create).

In the Nebius console, create a service account and an **authorized key**. Store its PEM privately with mode
0600. Grant that account permission to create/get jobs in the project, read the relevant MysteryBox secrets,
and read/write the evidence bucket; verify the tenant's role names and scope in IAM. Do not grant a public
application account billing or tenant administration permissions.

```bash
chmod 600 "$PRIVATE_KEY_PATH"
nebius profile create --endpoint api.nebius.cloud \
  --service-account-id "$SA_ID" --public-key-id "$PUBLIC_KEY_ID" \
  --private-key-file "$PRIVATE_KEY_PATH" --parent-id "$PROJECT_ID" --profile speccheck
```

Create MysteryBox secrets in the console with payload keys matching the environment variables they supply.
A selector is a secret name/ID, version ID, or `SECRET_ID@VERSION_ID`; **it is not the secret value**.

| Owner variable / GitHub secret | MysteryBox payload key |
| --- | --- |
| `NEBIUS_SECRET_NEBIUS_API_KEY` | `NEBIUS_API_KEY` |
| `NEBIUS_SECRET_TAVILY_API_KEY` | `TAVILY_API_KEY` |
| `NEBIUS_SECRET_ADMIN_TOKEN` | `ADMIN_TOKEN` |
| `NEBIUS_SECRET_PRIVATE_KEY` (endpoint only) | `NEBIUS_PRIVATE_KEY` (PEM text) |
| `NEBIUS_SECRET_SPECCHECK_URL` (endpoint only, use an unversioned selector) | `SPECCHECK_URL` |

The endpoint gets `NEBIUS_SA_ID`, `NEBIUS_PUBLIC_KEY_ID`, `NEBIUS_PROJECT_ID` and the PEM via MysteryBox.
At startup the app writes the PEM to a 0600 temporary file and creates a private CLI profile; it removes the
file on shutdown. CLI stdout/stderr and full job specifications never enter application logs or `jobs.json`.
App-created jobs prefer the three `NEBIUS_SECRET_*` selectors above; an unset selector falls back to `--env`
and logs only the variable name. Configure all three selectors for production. The scheduled workflow requires them.

## Create the evidence bucket

In Object Storage in the same project/region, create a private bucket named `$NEBIUS_EVIDENCE_BUCKET`, and
configure the service account's bucket access and S3 credentials using the console's connection instructions.
Confirm the CLI's default S3 credentials profile can access it. Both endpoint and job commands mount:

```bash
# Flag used on both nebius ai endpoint create and nebius ai job create:
--volume "s3://$NEBIUS_EVIDENCE_BUCKET:/app/evidence:rw"
```

The CLI also supports `:rw:PROFILE@SECRET_SELECTOR` for S3 credentials in MysteryBox; see the job flag reference.
When using that form, configure the same credential profile for endpoint, workflow and app-created jobs.
The app's `NEBIUS_EVIDENCE_BUCKET` setting uses the default profile; verify its mount in the one-day test.
Set `EVIDENCE_DIR=/app/evidence` and `EVIDENCE_LABEL="Nebius Object Storage"`. Without `EVIDENCE_DIR`, archiving
is skipped. Source text goes to `<case>/<retrieved_at>/<sha256>.txt`, PDFs to the same shape with `.pdf`.
Review links archived source text. A local directory works too; leave its label as `disk`.

## Test October 16–17, delete, then production October 22

Use a single endpoint process/replica (the app's job mutex and rate limits are per process).
Create a **one-day test endpoint on Oct 16**, inspect it and run the smoke command below, then **delete it on
Oct 17**. Create production on **Oct 22** after checking credit expiry and replacing the image with the tested
immutable tag/digest. No endpoint or job has been created by this development session.

Set the variables from your account. Initialize the `SPECCHECK_URL` MysteryBox entry to an empty value before
first creation; this hides the app's job action until its callback URL is configured.

```bash
export ENDPOINT_NAME=speccheck-test # use speccheck on Oct 22
export SPECCHECK_IMAGE=ghcr.io/<owner>/speccheck:<tested-commit>
nebius ai endpoint create --profile speccheck --name "$ENDPOINT_NAME" --image "$SPECCHECK_IMAGE" \
  --platform cpu-d3 --preset 2vcpu-8gb --disk-size 32Gi --on-demand \
  --container-port 8000 --auth none \
  --volume "s3://$NEBIUS_EVIDENCE_BUCKET:/app/evidence:rw" \
  --env SPECCHECK_MODE=live --env THINKING=off --env PUBLIC_UPLOADS_LIVE=true \
  --env BUDGET_USD_PER_RUN=3 --env BUDGET_USD_PER_DAY=8 \
  --env BUDGET_TAVILY_CREDITS_PER_ITEM=60 --env BUDGET_TAVILY_CREDITS_PER_DAY=600 --env MAX_CONCURRENCY=2 \
  --env EVIDENCE_DIR=/app/evidence --env EVIDENCE_LABEL="Nebius Object Storage" \
  --env NEBIUS_EVIDENCE_BUCKET="$NEBIUS_EVIDENCE_BUCKET" --env SPECCHECK_IMAGE="$SPECCHECK_IMAGE" \
  --env NEBIUS_SA_ID="$SA_ID" --env NEBIUS_PUBLIC_KEY_ID="$PUBLIC_KEY_ID" --env NEBIUS_PROJECT_ID="$PROJECT_ID" \
  --env NEBIUS_SECRET_NEBIUS_API_KEY="$NEBIUS_SECRET_NEBIUS_API_KEY" \
  --env NEBIUS_SECRET_TAVILY_API_KEY="$NEBIUS_SECRET_TAVILY_API_KEY" \
  --env NEBIUS_SECRET_ADMIN_TOKEN="$NEBIUS_SECRET_ADMIN_TOKEN" \
  --env-secret "NEBIUS_PRIVATE_KEY=$NEBIUS_SECRET_PRIVATE_KEY" \
  --env-secret "SPECCHECK_URL=$NEBIUS_SECRET_SPECCHECK_URL" \
  --env-secret "NEBIUS_API_KEY=$NEBIUS_SECRET_NEBIUS_API_KEY" \
  --env-secret "TAVILY_API_KEY=$NEBIUS_SECRET_TAVILY_API_KEY" \
  --env-secret "ADMIN_TOKEN=$NEBIUS_SECRET_ADMIN_TOKEN"
export ENDPOINT_ID=$(nebius ai endpoint get-by-name --profile speccheck --name "$ENDPOINT_NAME" --format 'jsonpath={.metadata.id}')
nebius ai endpoint get --profile speccheck "$ENDPOINT_ID" --format json | jq '.status.public_endpoints'
```

Copy the managed HTTPS URL into your shell's `SPECCHECK_URL`, the latest version of the unversioned MysteryBox
`SPECCHECK_URL` entry, and GitHub's `SPECCHECK_URL` variable. Restart the **same endpoint**, then verify its
health and `jobs_available`; verify secret refresh in the test deployment before relying on it in production.
A deleted/re-created endpoint can have a different URL. The pinned convenience CLI has no `ai endpoint update`;
do not assume such a command exists. `--auth none` exposes the managed HTTP port; no `--public` flag is needed.

```bash
nebius ai endpoint restart --profile speccheck "$ENDPOINT_ID"
curl --fail --silent --show-error "$SPECCHECK_URL/api/health"
# Read-only preflight, then c01 + a tiny PDF share one run/item budget; no retries.
python scripts/smoke.py "$SPECCHECK_URL"
# Finish the Oct 16–17 test, even if a check failed:
nebius ai endpoint delete --profile speccheck "$ENDPOINT_ID"
# On Oct 22, repeat creation with ENDPOINT_NAME=speccheck and configure its new URL.
```

Owner planning figures: `cpu-d3/2vcpu-8gb` **$0.066/h**; AI Cloud target **$90 of $125**, Token Factory **$150**,
Tavily **9,000 credits**. Confirm current prices, disk/storage charges and credit expiry in Billing. The alternative
`cpu-e2` planning price is **$0.060/h, eu-north1 only**; use it only if `nebius ai endpoint create --help` lists it
for your environment. A stopped endpoint pays no compute; it may still hold billable storage. Stop when not needed:
`nebius ai endpoint stop --profile speccheck "$ENDPOINT_ID"` and resume with `start`.
Caps are per process/job and the daily ledger is local; they are not an account-wide spending limit shared by
endpoint and jobs. The per-run/item caps still apply inside each job.

## Re-check jobs from the app and GitHub

Outcome keeps **Check approved now** as its primary action (in-process). With live mode, a working profile,
image and callback URL, the secondary **Run as a Nebius Serverless Job** action calls `/api/watch/run`.
It creates at most one app job in flight and defaults to one request per hour per endpoint, in addition to the
public per-IP limit. `/api/watch/jobs` shows the last five jobs with 15-second polling; reports link by `JOB_NAME`.
The job currently re-checks the server's bundled watched list; browser-only approvals are checked by the primary
button. It does not claim to have persisted the browser's decisions as a shared watch list.

```bash
curl --fail-with-body -X POST "$SPECCHECK_URL/api/watch/run"
curl --fail --silent --show-error "$SPECCHECK_URL/api/watch/jobs"
curl --fail --silent --show-error "$SPECCHECK_URL/api/watch"
# For a returned id:
nebius ai job get --profile speccheck "$JOB_ID" --format json
nebius ai job logs --profile speccheck "$JOB_ID"
```

Async create JSON is an **Operation**: use `resource_id`, not its `id`, for the job. If creation is ambiguous,
the app retains its reservation and polls by name; it never automatically submits another paid job. Unknown
CLI states keep their raw text and remain in flight. Only `COMPLETED → done` is configured initially.
Set `NEBIUS_JOB_STATE_MAP` to exact observed strings mapped to `queued|starting|running|done|failed` after the
owner's first run. A report arriving alone is not proof that cloud compute has stopped.

**TODO(owner): paste the real CLI state strings and their observed meanings here and in nightly-recheck.yml.**
No state names, job duration or cold-start measurements have been fabricated. The UI's “Nebius starts a job in
a few minutes” is service guidance, not a measured latency guarantee.

For `.github/workflows/nightly-recheck.yml`, set GitHub secrets `NEBIUS_SA_ID`, `NEBIUS_PUBLIC_KEY_ID`,
`NEBIUS_PRIVATE_KEY`, `NEBIUS_PROJECT_ID` and the three `NEBIUS_SECRET_*` selectors. Set variables
`SPECCHECK_URL`, `SPECCHECK_IMAGE`, `NEBIUS_EVIDENCE_BUCKET`. Enable `ENABLE_NEBIUS_JOBS=true` **only after**
the owner verifies the test job. It is disabled by default, even when merged. GitHub cron creates the job;
Nebius jobs have no native schedule. The workflow records raw states and accepts only documented completion
plus a report with the matching job name; a polling timeout fails visibly. Avoid overlapping scheduled and
manual launches: the app mutex does not cover a job submitted directly by GitHub.

## Evaluation as a job

This is deliberately **mock** unless the owner explicitly changes it to live. It needs no provider secrets,
although creating cloud compute itself spends AI Cloud credits. `--write` and `--out` are aliases.

```bash
export JOB_NAME="speccheck-eval-$(date -u +%Y%m%d-%H%M%S)"
nebius ai job create --profile speccheck --name "$JOB_NAME" --image "$SPECCHECK_IMAGE" \
  --container-command python --args 'scripts/eval.py --write /app/evidence/scores.json' \
  --platform cpu-d3 --preset 2vcpu-8gb --disk-size 32Gi --timeout 1h --restart-policy never --on-demand \
  --volume "s3://$NEBIUS_EVIDENCE_BUCKET:/app/evidence:rw" \
  --env SPECCHECK_MODE=mock --env EVIDENCE_DIR=/app/evidence --env EVIDENCE_LABEL="Nebius Object Storage" \
  --env RECHECK_RUNNER="Nebius Serverless Job" --env JOB_NAME="$JOB_NAME" --async --format json
```

`GET /api/scores` uses the bucket's `scores.json` when newer than the local score file. Scoreboard shows the
recorded runner, job name and date, and still says **mock** for fixture scores. The bucket survives endpoint
replacement. Provider caches are not shared by this mount; do not assume that tomorrow's re-check is free.

For local, free verification: `SPECCHECK_MODE=mock python -m pytest -q` and
`SPECCHECK_MODE=mock python scripts/eval.py --out /tmp/speccheck-baseline.json`. The tests install
`tests/fake_nebius.py` on a temporary PATH and exercise create/poll/limits without contacting Nebius.

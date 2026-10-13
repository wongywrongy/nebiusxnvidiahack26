# Running SpecCheck on Nebius AI Cloud

Two Serverless AI deployments from one image:

| What | Nebius Serverless | Why there |
| --- | --- | --- |
| The demo (web app + API) | **Endpoint**: a long-running container with a managed `https://` URL | the hackathon demo URL, live through judging |
| The nightly re-check (`scripts/recheck.py`) | **Job**: a container that runs to completion and exits | background work that should not share the web app's process; the track encourages Serverless Jobs for exactly this |

Both run on a CPU platform (`cpu-d3`); the models run on Token Factory, not in the container.

## 0. Once: image, keys, CLI

```bash
# image: GitHub Actions builds ghcr.io/<you>/speccheck:latest on every push to master (.github/workflows/image.yml).
# To ship the manufacturer PDFs (not in git) bake them in from a checkout that ran scripts/fetch_docs.py:
docker build -t ghcr.io/<you>/speccheck:latest . && docker push ghcr.io/<you>/speccheck:latest
# Make the package public (GitHub → Packages → speccheck → Package settings → Change visibility), or pass
# --registry-username/--registry-password below.

curl -sSL https://artifacts.nebius.cloud/cli/install.sh | bash && exec -l $SHELL
nebius profile create --endpoint api.nebius.cloud --parent-id <project_id>   # browser sign-in
export ADMIN_TOKEN=$(openssl rand -hex 24)
```

Credits: the Builders & Brews code gives $100 AI Cloud; redeem it in the console under Billing → Apply promo code.
Serverless AI bills through Compute per second while running; a stopped endpoint costs nothing.

## 1. The demo endpoint

```bash
nebius ai endpoint create \
  --name speccheck \
  --image ghcr.io/<you>/speccheck:latest \
  --platform cpu-d3 --preset 2vcpu-8gb --disk-size 32Gi --on-demand \
  --container-port 8000 \
  --auth none \
  --env SPECCHECK_MODE=live --env THINKING=off \
  --env BUDGET_USD_PER_DAY=5 --env BUDGET_TAVILY_CREDITS_PER_DAY=400 \
  --env NEBIUS_API_KEY=<token factory key> --env TAVILY_API_KEY=<tavily key> --env ADMIN_TOKEN=$ADMIN_TOKEN

export ENDPOINT_ID=$(nebius ai endpoint get-by-name --name speccheck --format jsonpath='{.metadata.id}')
nebius ai endpoint get $ENDPOINT_ID --format json | jq -r '.status.public_endpoints[]'
curl -s https://<that host>/api/health     # "mode": "live", every key true
```

Notes

- `--auth none` is the default and what a public demo needs: judges open the URL in a browser with no header.
- Keys in `--env` are visible to anyone with access to the Nebius project. For a tidier setup put them in
  MysteryBox and pass `--env-secret NEBIUS_API_KEY=<secret name>` instead.
- The `2vcpu-8gb` preset is about $0.07/h plus disk; with `--disk-size 32Gi` a month is roughly $55. If the
  preset name is refused, `nebius ai endpoint create --help` lists the presets for `cpu-d3`
  (the Nebius quickstart uses `4vcpu-16gb`).
- Caps: live tray items and re-checks are cached after their first run, so a day of judges costs cents; a judge's
  own PDF runs live only with the admin token. `BUDGET_USD_PER_DAY` and `BUDGET_TAVILY_CREDITS_PER_DAY` are the
  hard ceilings; past them a step reads "couldn't confirm" instead of failing.
- Redeploy: push a new image, then delete and re-create the endpoint (`nebius ai endpoint delete $ENDPOINT_ID`;
  the managed URL changes, so update `SPECCHECK_URL` and the Devpost form), or `nebius ai endpoint update` if
  your CLI version has it (`nebius ai endpoint --help`).
- `/api/health` is the judge's proof: it reports `mode`, which keys are set (true/false only), the model ids and
  today's spend.

## 2. The nightly job

The job is created by `.github/workflows/nightly-recheck.yml` on a schedule (Serverless Jobs have no cron of
their own). One-time setup:

1. Nebius console → IAM → Service accounts → create `speccheck-ci`, give it the editor role on the project, add
   an **authorized key** (download the private key PEM, note the public key id).
2. GitHub → repository → Settings → Secrets and variables → Actions:
   secrets `NEBIUS_SA_ID`, `NEBIUS_PUBLIC_KEY_ID`, `NEBIUS_PRIVATE_KEY` (the PEM), `NEBIUS_PROJECT_ID`,
   `NEBIUS_API_KEY`, `TAVILY_API_KEY`, `SPECCHECK_ADMIN_TOKEN`; variable `SPECCHECK_URL` (the endpoint's https URL).
3. Run it once by hand: Actions → nightly-recheck → Run workflow. The log ends with the job's own output: one line
   per approved item (`no_change`, `changed`, `discontinued`, `unverified`). The Outcome step of the demo then shows
   "Nightly re-check last ran … (Nebius Serverless Job)".

By hand, the same job is:

```bash
nebius ai job create --name speccheck-recheck \
  --image ghcr.io/<you>/speccheck:latest \
  --container-command python --args "scripts/recheck.py --post https://<endpoint host>" \
  --platform cpu-d3 --preset 2vcpu-8gb --disk-size 32Gi --timeout 1h --restart-policy never --on-demand \
  --env SPECCHECK_MODE=live --env RECHECK_RUNNER="Nebius Serverless Job" \
  --env NEBIUS_API_KEY=... --env TAVILY_API_KEY=... --env ADMIN_TOKEN=$ADMIN_TOKEN
nebius ai job logs $(nebius ai job get-by-name --name speccheck-recheck --format jsonpath='{.metadata.id}')
```

A job runs a few minutes and costs about a cent of compute plus the Token Factory and Tavily calls
(cached across nights when nothing changed).

## If AI Cloud credits are not available

Host the web app anywhere that runs a container (Fly.io, Render, Railway) with the same environment variables,
and keep the nightly re-check on Nebius Serverless Jobs: the workflow only needs `SPECCHECK_URL` to point at the
app. The submission requirement is a runtime call to Token Factory, which the app makes wherever it is hosted.

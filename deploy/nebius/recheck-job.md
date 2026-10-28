# Daily re-check as a Nebius Serverless Job, launched by the app server

Nebius jobs have no schedule or trigger (CLI 0.12.296: `nebius ai job --help` lists cancel, create, delete,
get, get-by-name, list, logs, operation, restart, run, ssh; `create` has no schedule flag; no top-level
scheduler service). So the app server launches the job itself (`api/daily_recheck.py`, Nebius Python SDK):

- After `RECHECK_HOUR_UTC` (default 09:00 UTC) it creates `speccheck-recheck-<YYYY-MM-DD>` from
  `SPECCHECK_IMAGE`. The launch is written to `/state/runs/watch/launches.json` **before** the create call,
  so a crash, restart or retry can never launch twice in one UTC day. A failed create is not retried that day.
- The job starts its own ledger capped at **$0.50 and 40 Tavily credits**, re-checks the watched items live,
  and posts its report to `SPECCHECK_URL` with the admin token it reads from MysteryBox.
- The app accepts a report signed "Nebius Serverless Job <name>" only if this server launched `<name>`.
  The Outcome line shows only such stored reports, and nothing when none exists.

Job states (SDK `JobStatus.State`): PROVISIONING, STARTING, IMAGE_PULLING, RUNNING, CANCELLING, DELETING,
COMPLETED, FAILED, CANCELLED, ERROR.

## Where the key lives

The app server is the Nebius Serverless AI endpoint `aiendpoint-e01nkwwp6azgh9ge1k` (project
`project-e01ab4axpa005e506zq7nq`, eu-west1, cpu-d3 2vcpu-8gb, `/state` on filesystem
`computefilesystem-e01syzwfv7rqexfcys`). The service account's private key is a MysteryBox secret injected
into that endpoint's environment as `NEBIUS_PRIVATE_KEY` with `--env-secret`. The SDK reads it from memory;
it is never written to disk, baked into the image or put in a URL, and logs redact it.

You run every command below. Keys go into prompts or files you delete, never into chat.

## 1. Service account that may create jobs

```bash
export PROJECT_ID=project-e01ab4axpa005e506zq7nq
export TENANT_ID=<your tenant id>            # nebius iam tenant list
export SA_ID=$(nebius iam service-account create --name speccheck-recheck --parent-id $PROJECT_ID \
  --format jsonpath='{.metadata.id}')
EDITORS=$(nebius iam group get-by-name --name editors --parent-id $TENANT_ID --format jsonpath='{.metadata.id}')
nebius iam group-membership create --parent-id $EDITORS --member-id $SA_ID
```

`editors` can create jobs but cannot read secret payloads. In the console: IAM → Groups → create
`speccheck-secret-readers` with an access permit for role `mysterybox.payload-viewer` on the project, and add
the `speccheck-recheck` service account.

## 2. Its key (RSA, generated locally)

```bash
umask 077
openssl genrsa -out sa.pem 4096 && openssl rsa -in sa.pem -pubout -out sa.pub.pem
export PUBLIC_KEY_ID=$(nebius iam auth-public-key create --account-service-account-id $SA_ID \
  --data "$(cat sa.pub.pem)" --format jsonpath='{.metadata.id}')
nebius mysterybox secret create --name speccheck-server-sa --parent-id $PROJECT_ID \
  --secret-version-payload "$(jq -nc --rawfile k sa.pem '[{key:"NEBIUS_PRIVATE_KEY",string_value:$k}]')"
shred -u sa.pem sa.pub.pem
echo $PUBLIC_KEY_ID   # if empty: nebius iam auth-public-key list-by-account --account-service-account-id $SA_ID
```

## 3. The job's keys (one secret, three payload keys)

```bash
read -rs NEBIUS_API_KEY; read -rs TAVILY_API_KEY; read -rs ADMIN_TOKEN   # ADMIN_TOKEN = the app's admin token
nebius mysterybox secret create --name speccheck-recheck --parent-id $PROJECT_ID \
  --secret-version-payload "$(jq -nc --arg a "$NEBIUS_API_KEY" --arg b "$TAVILY_API_KEY" --arg c "$ADMIN_TOKEN" \
    '[{key:"NEBIUS_API_KEY",string_value:$a},{key:"TAVILY_API_KEY",string_value:$b},{key:"ADMIN_TOKEN",string_value:$c}]')" >/dev/null
unset NEBIUS_API_KEY TAVILY_API_KEY ADMIN_TOKEN
export RECHECK_SECRET_ID=$(nebius mysterybox secret get-by-name --name speccheck-recheck --parent-id $PROJECT_ID \
  --format jsonpath='{.metadata.id}')
```

## 4. Endpoint settings (applied with the Package H redeploy)

Add to the endpoint's environment:

| Variable | Value |
|---|---|
| `NEBIUS_SA_ID` | `$SA_ID` |
| `NEBIUS_PUBLIC_KEY_ID` | `$PUBLIC_KEY_ID` |
| `NEBIUS_PROJECT_ID` | `project-e01ab4axpa005e506zq7nq` |
| `SPECCHECK_IMAGE` | the new image digest from Package H |
| `SPECCHECK_URL` | `https://speccheck-wongywrongys-projects.vercel.app` |
| `RECHECK_MYSTERYBOX_SECRET_ID` | `$RECHECK_SECRET_ID` |
| `NEBIUS_PRIVATE_KEY` | `--env-secret NEBIUS_PRIVATE_KEY=speccheck-server-sa` |

## 5. Check it

The first launch happens on the first 10-minute tick after 09:00 UTC. Then:

```bash
nebius ai job get-by-name --name speccheck-recheck-$(date -u +%F) --parent-id $PROJECT_ID --format json | jq .status
curl -s https://speccheck-wongywrongys-projects.vercel.app/api/watch | jq '{checked_at, runner, items: [.items[] | {id, status}]}'
```

Screenshot the job in the console (AI → Jobs) for the README.

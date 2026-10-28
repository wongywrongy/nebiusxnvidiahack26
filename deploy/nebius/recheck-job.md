# Daily re-check as a Nebius Serverless Job

GitHub Actions (`.github/workflows/nightly-recheck.yml`) runs once a day at 09:17 UTC, signs in as a service
account, and launches `nebius ai job create` with the public SpecCheck image. The job re-checks the watched
items live, posts its report to the public URL with the admin token, and exits. The Outcome step shows
"Re-checked by Nebius Serverless Job <name> · <date time> · N items, M flagged" only once a report exists.

Spend per run is capped inside the job: $0.50 of Token Factory and 40 Tavily credits (one watched item today).
A cap ends a check as "couldn't confirm".

You run every command below. Keys go into prompts (`read -rs`), never into a file, an image or a URL.

## 1. Service account (Nebius CLI, signed in as you)

```bash
export PROJECT_ID=project-e01ab4axpa005e506zq7nq
export TENANT_ID=<your tenant id>            # nebius iam tenant list
export SA_ID=$(nebius iam service-account create --name speccheck-recheck --parent-id $PROJECT_ID \
  --format jsonpath='{.metadata.id}')
EDITORS=$(nebius iam group get-by-name --name editors --parent-id $TENANT_ID --format jsonpath='{.metadata.id}')
nebius iam group-membership create --parent-id $EDITORS --member-id $SA_ID
```

`editors` lets it create jobs but does **not** let it read secret payloads. In the console: IAM → Groups →
create `speccheck-secret-readers`, give it an access permit with role `mysterybox.payload-viewer` on the
project, and add the `speccheck-recheck` service account.

## 2. Authorized key

```bash
nebius iam auth-public-key generate --service-account-id $SA_ID --output ~/.nebius/speccheck-recheck.json
```

## 3. MysteryBox secret

The endpoint already reads its keys from MysteryBox; reuse that secret if its payload keys are exactly
`NEBIUS_API_KEY`, `TAVILY_API_KEY` and `ADMIN_TOKEN` (`nebius mysterybox secret list --parent-id $PROJECT_ID`).
Otherwise create one. `ADMIN_TOKEN` must equal the deployed app's admin token.

```bash
read -rs NEBIUS_API_KEY; read -rs TAVILY_API_KEY; read -rs ADMIN_TOKEN
nebius mysterybox secret create --name speccheck-recheck --parent-id $PROJECT_ID \
  --secret-version-payload "$(jq -nc --arg a "$NEBIUS_API_KEY" --arg b "$TAVILY_API_KEY" --arg c "$ADMIN_TOKEN" \
    '[{key:"NEBIUS_API_KEY",string_value:$a},{key:"TAVILY_API_KEY",string_value:$b},{key:"ADMIN_TOKEN",string_value:$c}]')"
unset NEBIUS_API_KEY TAVILY_API_KEY ADMIN_TOKEN
```

## 4. GitHub settings

```bash
gh secret set NEBIUS_SA_CREDENTIALS < ~/.nebius/speccheck-recheck.json && rm ~/.nebius/speccheck-recheck.json
gh variable set NEBIUS_PROJECT_ID --body "$PROJECT_ID"
gh variable set SPECCHECK_URL --body https://speccheck-wongywrongys-projects.vercel.app
gh variable set SPECCHECK_IMAGE --body ghcr.io/wongywrongy/speccheck@sha256:e5c92a98a7d384e3e89c21819546fc9928ce6c6971f951cf1a4bc1c888dcbab2
gh variable set MYSTERYBOX_SECRET --body speccheck-recheck   # or the reused secret's name/ID
gh variable set ENABLE_NEBIUS_JOBS --body true
```

## 5. First run, by hand

```bash
gh workflow run nightly-recheck --ref feat/final-push
gh run watch
```

The "Wait" step prints every job state the CLI reports. Send those to Claude; they replace the `TERMINAL`
TODO in the workflow. Then screenshot the job in the Nebius console (AI → Jobs) for the README.

## If it is not working by 13:00 Wed

Fall back to a GitHub-hosted re-check that posts the same report with `RECHECK_RUNNER` unset; the Outcome
line then reads "Re-checked · <date time> · …" without the word Nebius.

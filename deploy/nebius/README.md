# SpecCheck: one public container

Kyle approved the CPU endpoint and persistent application state on October 27. PR #13 is merged at `ddec9d5`; controller/authority topology is out of scope. [Historical rollout preparation](history-20261023.md) is retained for reference only.

Build the final image locally from a clean tracked checkout plus the 13 locked public PDFs and `runs/recorded/20261022-181611-a9d0b5/`. Publish an immutable GHCR tag and deploy its digest. Provider credentials and the admin token go through MysteryBox `--env-secret`; never put their values in an image, command argument or URL.

Use `cpu-d3`, `2vcpu-8gb`, 32 GiB container disk, port 8000 and `--auth none`. Mount one Nebius shared filesystem at `/state`; one container/process owns that state. Set the nonsecret values in [judging.env.example](judging.env.example). The managed HTTPS endpoint supplies the public URL; a separate public VM IP is unnecessary. [Official endpoint flags](https://docs.nebius.com/serverless/endpoints/manage).

Check regional CPU quota before creating resources. On October 27, `eu-north1` rejected the two-vCPU endpoint with `ResourceExhausted: compute.instance.non-gpu.vcpu (limit 0, requested 2)`. The authenticated quota list showed 200 unused vCPUs in `eu-west1`, where the same endpoint passed validation and creation was accepted. This was a regional CPU quota failure; persistent storage was available. [Recorded regional limits](../../docs/deployment/cpu-quotas-20261027.json).

`python scripts/serve.py` initializes a fresh allowance-only database only when JUDGING_USD/JUDGING_CREDITS are set and no database exists. Explicit owner command: `python scripts/campaign_budget.py init-judging --usd 75 --credits 6000`; it refuses to replace an existing file. The allocator's internal active bucket retains its existing engineering label; this new database contains no historical spend.

APP_STATE_DIR must already exist. Startup stores the database, raw/upload PDFs, cache, runs and scores there, copies only missing locked public PDFs from the image, and rejects changed stored source bytes. The committed replay stays in the image. A process/container restart reuses the existing allowance and uploaded data. Unknown provider usage settles conservatively at its pre-call reservation, logs a warning and permits later calls; model timeouts retry once with a new reservation. Missing or corrupt accounting still refuses paid calls.

If deploying without a persistent mount, omit APP_STATE_DIR: a replaced container starts a fresh allowance, still bounded by configured daily caps. Such a deployment does not provide a durable campaign ceiling and is not the preferred configuration.

The judging allowance is a ceiling of **$75 / 6,000 credits**; daily caps **$8 / 600**, per-run **$3**, concurrency **2**. Keep the endpoint up through **December 15, 2026, 20:00 UTC**. Start the 90-minute fallback timer with the first endpoint-creation attempt. If live health is not serving by then, use the approved always-on Render/Fly persistent host up to $25/month.

After deployment, run `python scripts/smoke.py <url>` without an admin token and repeat the private-browser a–e checks using `docs/playground/capture.mjs`. Keep actual traces/screenshots and ledger deltas. Then apply the approved three UI polish items and freeze code. No cloud-job execution is claimed; the optional job has not been run.

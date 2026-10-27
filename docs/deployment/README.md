# Public deployment — October 27, 2026

**[Open SpecCheck](https://port8000-xbq07jkkdkpet9f.tunnel.applications.eu-west1.nebius.cloud)** · [Final configuration and validation](final-deployment.json) · [All public browser checks](../playground/public-final/README.md)

One Nebius Serverless Endpoint in eu-west1 serves the frozen image at `eea71cf`. Native PDFs and the recorded `20261022-181611-a9d0b5` fallback are included. No provider keys are in the image. [Original isolated packaging proof](packaging.json) covers actual native rendering and restart persistence; the final image repeated its no-key/native-PDF check with networking disabled.

[Initial fresh no-admin smoke](smoke.txt) passed before UI polish. After replacement, [no-admin read-only preflight](final-preflight.txt) and all five private-browser workflows passed on the final URL, including fresh provider calls. [Replacement health](replacement-health.json) proves the ledger retained $0.55774920 / 80 credits before further calls. [Final settled health](final-health.json) shows no holds and blocked false.

Final hosted spend: **$0.67351110 / 91 credits**. Combined engineering push, including local attempts and conservative timeout settlements: **$1.32044472 / 129 credits**. Judging allowance remaining: **$74.32648890 / 5,909 credits**; daily caps remain $8 / 600, run $3, concurrency 2.

The first eu-north1 dry-run failed with `ResourceExhausted: compute.instance.non-gpu.vcpu (limit 0, requested 2)`. Storage creation succeeded. The tenant had 200 unused CPU vCPUs in eu-west1, where deployment worked. [Quota evidence](cpu-quotas-20261027.json). Fly login was stopped and no Fly resources were created.

The superseded endpoint was deleted after the replacement became healthy. One persistent filesystem retains ledger/cache/uploads/runs; code is frozen. No cloud job or nightly schedule was run. Planned availability continues through December 15, 2026, 20:00 UTC.

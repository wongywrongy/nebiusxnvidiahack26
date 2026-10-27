# Current-source local image — 2026-10-23

This is an **unpublished local candidate**, not release approval or hosted evidence. It contains tested
runtime source `1c3c7fe`, including the scope, replacement-research and catalog corrections. G2 still has
no passing replacement. No real wallet transfer, provider call, registry publication or cloud resource
occurs in these checks.

| Identity | Actual value |
| --- | --- |
| Local tag | `speccheck:readiness-1c3c7fe` |
| Local image/index ID | `sha256:e92d0c23c9233f21607b4171b250e8598f220d8982d4d859c05ac69cd63387b7` |
| Runtime code hash | `f96aca7736fbc9f8730b7e51ba197a7cfdfe23913841286775cb4bc6fa3e212a` |
| Default command | `python scripts/serve.py` |
| Installed Nebius CLI | `0.12.289` |

[Image metadata](image.json), [runtime hash / absent-key and excluded-path booleans](runtime-privacy.json),
[actual CLI response](cli-version.txt). The locally reported repository digest is not proof of a published
registry reference. Final registry binding remains pending separate approval.

The actual Docker build succeeds, including the [required 13-document native-PDF lock check](document-preflight.json). Dependency
and frontend build layers were reused from the preceding successful build. No new uncached dependency or
frontend build is claimed. The runtime hash matches the [current targeted live confirmation](../catalog-fallback-20261023/README.md).

An actual network-disabled image invocation reproduces the raw mock **6/8 calls, 5/6 problems, 0/2 major
false alarms, 0/5 passing fixes**, zero invalid items and one unnecessary note. Its expected eval exit is
1; the policy exception is not hidden. Fresh charges are $0 / 0. [Output](mock-eval.txt).
Both GitHub workflows for source `1c3c7fe` pass pytest, mock-policy assertions, web presentation/build
and mock browser journey/failure checks; [actual job/step statuses](ci.json).

The existing synthetic-only reproducer runs against this tag by changing only its local image constant.
It creates its own temporary mount and synthetic credentials, disables container networking, proves no
wallet is initialized on startup, explicitly imports a new synthetic wallet and restarts the same
container. State, authority and cache/upload/run markers survive; accounting becomes available.
[Actual result](synthetic-restart.json), [script identity](reproducer.json).
Its test seed is not real spend, and no real campaign data is mounted. Its temporary container is removed
by the reproducer. The private synthetic directory remains under `/tmp` for inspection.

A separate stdin-only check finds none of the configured real secret strings in **126 regular files
under `/app`**. [Boolean report](application-secret-scan.json). This does not scan image layers or the
entire filesystem. A fresh image reports provider/admin keys absent, and `.env`, `.cache`, private
evidence and uploaded PDFs absent from their application paths. No key is printed or saved in artifacts.

The real local campaign remains active at **$2.6351023 / 442 credits**, with no holds or persistent block;
[authority report](campaign-status.json). Packaging adds **$0 / 0 provider charges**.

## Reproduction

Use source `1c3c7fe` with the required public PDFs already downloaded and hash-checked.

```bash
docker build --progress=plain --tag speccheck:readiness-1c3c7fe .
docker run --rm --network none --entrypoint nebius speccheck:readiness-1c3c7fe version
docker run --rm --network none --entrypoint python speccheck:readiness-1c3c7fe scripts/eval.py --out /tmp/image-mock.json
# Expected exit 1 for the disclosed raw mock policy disagreements.
.venv/bin/python - <<'PY'
from pathlib import Path
import subprocess
source = Path('docs/judge-readiness/controller-startup-20261023/reproduce.py').read_text()
old = 'image = "speccheck:controller-startup-local"'
assert source.count(old) == 1
script = Path('/tmp/speccheck-reproduce-current-image.py')
script.write_text(source.replace(old, 'image = "speccheck:readiness-1c3c7fe"'))
subprocess.run(['.venv/bin/python', str(script)], check=True)
PY
```

This proof requires Linux and a local Unix Docker socket. Rebuilding later can resolve different base
image digests; it is not a promise of bit-identical rebuilds. Never substitute the real wallet or real
credentials into the synthetic proof. The [bounded rollout draft](../../../deploy/nebius/rollout.pending.md)
still needs account/IAM/quota/price/expiry facts, a published immutable image, final validation and owner
approval. Hosted restart/VM cutover, public fresh upload and actual manual/scheduled job proof remain
agent-owned work after those gates. Local process restart does not establish Nebius durability.

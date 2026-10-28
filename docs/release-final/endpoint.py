"""Replace the public endpoint with a new image, as on October 28 (deploy/nebius/README.md). Second use: the ui/grouped-package image.

Run with an authenticated Nebius CLI (`nebius` on PATH, or NEBIUS="<cli> --config <file>"), in order:
  python docs/release-final/endpoint.py stop-old
  python docs/release-final/endpoint.py create ghcr.io/wongywrongy/speccheck@sha256:<digest> <source-commit>
  python docs/release-final/endpoint.py get-new
  python docs/release-final/endpoint.py delete-old      # only after the public checks pass

Settings, subnet, filesystem and MysteryBox secret references are copied from the live endpoint's own spec;
only the image and SPECCHECK_COMMIT change. Outputs are saved beside this file (no secret values are returned).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

OLD = "aiendpoint-e01cg2e1rfwpvfpnb0"  # speccheck-final-20261028; was aiendpoint-e01y93s8ffx7g7wern
FS = {"source": "computefilesystem-e01syzwfv7rqexfcys", "container_path": "/state", "mode": "READ_WRITE"}
OUT = Path(__file__).parent / "endpoint"


def nebius(*args, name):
    out = subprocess.run([*os.environ.get("NEBIUS", "nebius").split(), *args, "--format", "json"], capture_output=True, text=True)
    if out.returncode:
        sys.exit(out.stderr)
    data = json.loads(out.stdout or "{}")
    OUT.mkdir(exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


def get(endpoint_id, name):
    return nebius("ai", "endpoint", "get", "--id", endpoint_id, name=name)


mode = sys.argv[1]
if mode == "stop-old":
    old = get(OLD, "old-before-stop")
    assert old["spec"]["volumes"] == [FS], "unexpected volume on the live endpoint"
    nebius("ai", "endpoint", "stop", "--id", OLD, name="old-stopped")
    print(get(OLD, "old-after-stop")["status"]["state"])
elif mode == "create":
    image, commit = sys.argv[2], sys.argv[3]
    assert image.startswith("ghcr.io/wongywrongy/speccheck@sha256:") and len(image.rsplit(":", 1)[1]) == 64
    old = get(OLD, "old-before-create")
    assert old["status"]["state"] == "STOPPED", "one writer: stop the old endpoint first"
    s, m = old["spec"], old["metadata"]
    args = ["ai", "endpoint", "create", "--parent-id", m["parent_id"], "--name", "speccheck-ui-20261028",
            "--image", image, "--platform", s["platform"], "--preset", s["preset"], "--disk-size", "32Gi",
            "--container-port", "8000", "--auth", "none", "--subnet-id", s["subnet_id"],
            "--volume", f"{FS['source']}:/state:rw"]
    for e in s["environment_variables"]:
        if ref := e.get("mysterybox_secret"):
            args += ["--env-secret", f"{e['name']}={ref['secret_id']}@{ref['version_id']}"]
        else:
            args += ["--env", f"{e['name']}={commit if e['name'] == 'SPECCHECK_COMMIT' else e['value']}"]
    if not any(e["name"] == "SPECCHECK_COMMIT" for e in s["environment_variables"]):
        args += ["--env", f"SPECCHECK_COMMIT={commit}"]
    new = nebius(*args, name="new-created")
    print(json.dumps(new.get("metadata"), indent=2))
elif mode == "get-new":
    new = json.loads((OUT / "new-created.json").read_text())
    print(json.dumps(get(new["metadata"]["id"], "new-current")["status"], indent=2))
elif mode == "delete-old":
    assert get(OLD, "old-before-delete")["status"]["state"] == "STOPPED"
    nebius("ai", "endpoint", "delete", "--id", OLD, name="old-deleted")
    print("deleted", OLD)
else:
    sys.exit(__doc__)

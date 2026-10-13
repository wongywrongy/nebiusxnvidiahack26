#!/usr/bin/env python3
"""Offline CLI double. Tests control JSON state through files; this executable makes no network calls."""
import json
import os
import stat
import sys
from pathlib import Path

args = sys.argv[1:]
if path := os.environ.get("FAKE_NEBIUS_CALLS"):
    with Path(path).open("a") as f:
        f.write(json.dumps(args) + "\n")
if args[:2] == ["profile", "create"]:
    pem = Path(args[args.index("--private-key-file") + 1])
    assert stat.S_IMODE(pem.stat().st_mode) == 0o600
    # Deliberately hostile output: the application must neither log nor persist CLI output.
    print(pem.read_text(), file=sys.stderr)
    print(pem.read_text())
elif args[:3] == ["ai", "job", "create"]:
    print(json.dumps({"id": "fixture-operation-id", "resource_id": "fixture-job-id"}))
elif args[:3] == ["ai", "job", "get-by-name"]:
    print("fixture-job-id")
elif args[:3] == ["ai", "job", "get"]:
    path = os.environ.get("FAKE_NEBIUS_STATE")
    raw = Path(path).read_text().strip() if path else "COMPLETED"
    print(json.dumps({"metadata": {"id": "fixture-job-id"}, "status": {"state": raw}}))
else:
    sys.exit(2)

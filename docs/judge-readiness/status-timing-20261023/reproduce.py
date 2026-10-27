"""Offline synthetic lifecycle responses; run from the source checkout in mock mode."""

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd()))

from api import release
from api.config import settings
from api.pipeline import verify
from api.pipeline.decide import decide
from api.readiness import manifest
from api.schemas import ClaimsOut, Evidence, VerifyOut

if settings.live:
    raise SystemExit("Offline reproduction requires SPECCHECK_MODE=mock")

url = "https://maker.test/notice"
product = ClaimsOut(product="ZX-7", manufacturer="Synthetic maker", model="ZX-7", family="ZX", claims=[])
observations = []
for name, status, quote in [
    ("future discontinuation", "discontinued", "As of May 1, 2035, the ZX family will be discontinued."),
    ("undated plan", "discontinued", "The ZX family will be discontinued."),
    ("past effective date", "discontinued", "As of May 1, 2001, the ZX family will be discontinued."),
    ("future availability", "active", "The ZX family is available from May 1, 2035."),
    ("expired availability", "active", "The ZX family is available until May 1, 2001."),
    ("ungrounded metadata", "discontinued", "The ZX family is discontinued."),
]:
    output = VerifyOut(status=status, status_family="ZX", status_date="1999-01-01",
                       status_quote=quote, replacement="XR-9")
    request = output.model_dump()
    pages = [{"url": url, "raw_content": quote + " Other product XR-9."}]
    confirmed = verify.gate(output, pages, submitted=product)
    findings, _ = verify.compare(product, output, confirmed, [], pages)
    observations.append({"name": name, "request": request, "response": {
        "status": output.status, "status_date": output.status_date, "replacement": output.replacement,
        "status_findings": [{"check": f.check, "verdict": f.verdict, "severity": f.severity}
                            for f in findings if f.check == "status"], "decision": decide(findings)}})

quote = observations[0]["request"]["status_quote"]
proof = SimpleNamespace(submitted=product, output=VerifyOut(**observations[0]["request"]),
                        sources=[Evidence(url=url, title="Synthetic notice", tier="manufacturer")])
with patch.object(release, "_archived", return_value=[quote]):
    try:
        now = datetime.now(timezone.utc)
        release._verification(proof, product, now, now)
        release_accepted = True
    except ValueError:
        release_accepted = False

print(json.dumps({"scope": "Offline synthetic responses only; no model, HTTP or paid provider request",
    "observed_at": datetime.now(timezone.utc).isoformat(), "code_hash": manifest()["code_hash"],
    "observations": observations, "release_accepts_future_status": release_accepted}, indent=2))

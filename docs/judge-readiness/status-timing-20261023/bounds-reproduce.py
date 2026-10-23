"""Offline synthetic availability bounds, with a fixed evaluation date."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd()))

from api.config import settings
from api.pipeline import verify
from api.readiness import manifest
from api.schemas import ClaimsOut, VerifyOut

if settings.live:
    raise SystemExit("Offline reproduction requires SPECCHECK_MODE=mock")


class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2030, 6, 1, tzinfo=timezone.utc)


product = ClaimsOut(product="ZX-7", manufacturer="Synthetic maker", model="ZX-7", family="ZX", claims=[])
observations = []
for ending in ("until Q4 2001.", "through FY2001.", "until end of 2001.",
               "through distributors.", "until further notice."):
    quote = "The ZX family is available " + ending
    output = VerifyOut(status="active", status_family="ZX", status_quote=quote)
    request = output.model_dump()
    with patch.object(verify, "datetime", Clock):
        verify.gate(output, [{"url": "https://maker.test/notice", "raw_content": quote}],
                    measure=False, submitted=product)
    observations.append({"request": request, "response": output.model_dump()})

print(json.dumps({"scope": "Offline synthetic responses; no model, HTTP or provider request",
                  "observed_at": datetime.now(timezone.utc).isoformat(),
                  "evaluated_at": Clock.now().isoformat(), "code_hash": manifest()["code_hash"],
                  "observations": observations}, indent=2))

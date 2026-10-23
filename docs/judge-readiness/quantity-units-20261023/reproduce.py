"""Offline forged-response check. Run from the source checkout with SPECCHECK_MODE=mock."""

import asyncio
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd()))

from api.config import settings
from api.pipeline import extract, spec_check, verify
from api.readiness import manifest
from api.release import _claims
from api.schemas import Claim, ClaimsOut, Requirement, Usage, VerifyOut

if settings.live:
    raise SystemExit("Offline reproduction requires SPECCHECK_MODE=mock")

quote = "Dimming control interface: 0-12 V."
text = "Model ZX-9. " + quote
claim = Claim(id="q", product="ZX-9", manufacturer="Synthetic maker", model="ZX-9",
              property="dim_min_percent", value=0, unit=None, page=1, quote=quote,
              scope="product_wide", scope_quote=quote)
forged = ClaimsOut(product="ZX-9", manufacturer="Synthetic maker", model="ZX-9", claims=[claim])


async def read(*args):
    return forged.model_copy(deep=True), Usage(task="extract_claims", tier="extract", model="synthetic")


pages = [{"page": 1, "text": text}]
with patch.object(extract, "_read_claims", read):
    result, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), [claim.property]))
requirement = Requirement(id="q", section="synthetic", paragraph="", property=claim.property,
                          operator="lte", value=7, unit="%", text="Synthetic quantity limit")
url = "https://maker.test/ZX-9.pdf"
web = VerifyOut(status="unknown", current_values=[dict(property=claim.property, value=0, unit=None,
    quote=quote, model="ZX-9", identity_quote="Model ZX-9", scope="product_wide", scope_quote=quote, source_url=url)])
verify.gate(web, [{"url": url, "raw_content": text}], submitted=result)
try:
    _claims(forged, forged.claims, None, {1: text})
    release_accepted = True
except ValueError:
    release_accepted = False

print(json.dumps({"scope": "Offline synthetic provider response; no model, HTTP or paid call",
    "code_hash": manifest()["code_hash"], "request": claim.model_dump(),
    "observed_response": {"extracted_claims_kept": len(result.claims),
        "spec_verdict": spec_check.check([requirement], result.claims, {"product_data"})[0].verdict,
        "web_values_kept": len(web.current_values), "release_claim_gate_accepted": release_accepted}}, indent=2))

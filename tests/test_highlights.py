"""Document highlights: quotes found in a real PDF, clean fallback without one, fixture quotes stay verbatim."""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("SPECCHECK_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from api.config import settings  # noqa: E402
from api.main import app  # noqa: E402
from api.pipeline.cases import all_cases  # noqa: E402
from api.schemas import Claim, Finding, Result  # noqa: E402

client = TestClient(app)
C03_PDF = settings.raw_dir / all_cases()["c03"]["submittal"][0]["file"]


@pytest.fixture
def stored_result():
    """Write a result into a throwaway run folder; yields a function that stores one and returns its run id."""
    run_dir = settings.runs_dir / "test-highlights"

    def store(result: Result) -> str:
        (run_dir / "results").mkdir(parents=True, exist_ok=True)
        (run_dir / "results" / f"{result.case_id}.json").write_text(result.model_dump_json())
        return run_dir.name

    yield store
    shutil.rmtree(run_dir, ignore_errors=True)


def _result(source: str, quote: str) -> Result:
    claim = Claim(id="k1", product="IC 15WB+", manufacturer="3M", property="voc_g_per_l", value="0", page=1, quote=quote)
    finding = Finding(id="currency-outdated", check="currency", verdict="outdated", severity="major",
                      title="Out of date", claim_ids=["k1"])
    return Result(case_id="c03", title="t", decision="send_back", summary="", findings=[finding],
                  claims=[claim], document_source=source)


@pytest.mark.skipif(not C03_PDF.exists(), reason="run scripts/fetch_docs.py to download the c03 PDF")
def test_rects_for_a_quote_in_the_downloaded_pdf(stored_result):
    run_id = stored_result(_result("pdf", "Fire Barrier"))
    body = client.get(f"/api/runs/{run_id}/results/c03/highlights").json()
    assert body["pages"][0]["image"] is True and len(body["pages"]) == 4
    (h,) = body["highlights"]
    assert h["tone"] == "amber" and h["page"] == 1 and h["rects"]
    assert all(0 <= v <= 1 for r in h["rects"] for v in r)
    png = client.get("/api/cases/c03/pages/1.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"


def test_falls_back_to_fixture_text_without_a_pdf(stored_result):
    # c08's submittal is not downloadable (Cloudflare), and a fixture-sourced result never uses the PDF anyway.
    run_id = stored_result(_result("pdf", "not on any page").model_copy(update={"case_id": "c08"}))
    body = client.get(f"/api/runs/{run_id}/results/c08/highlights").json()
    assert body["pages"][0]["image"] is False and body["pages"][0]["text"]
    (h,) = body["highlights"]
    assert h["rects"] == [] and h["page"] == 1 and h["quote"] == "not on any page"
    assert client.get("/api/cases/c08/pages/1.png").status_code == 404


def test_fixture_quotes_appear_verbatim_on_their_page():
    for path in sorted(settings.fixtures_dir.glob("c0*.json")):
        fx = json.loads(path.read_text())
        pages = {p["page"]: p["text"] for p in fx["pages"]}
        for c in fx.get("claims", {}).get("claims", []):
            assert c.get("quote") and c["quote"] in pages[c["page"]], (path.name, c["id"])

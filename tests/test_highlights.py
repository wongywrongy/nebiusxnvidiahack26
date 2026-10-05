"""Real PDF pages: every fixture quote lands on the page, locate() fallbacks, and the document endpoints."""

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("SPECCHECK_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from api.config import settings  # noqa: E402
from api.main import app  # noqa: E402
from api.pipeline.cases import all_cases  # noqa: E402
from api.pipeline.render import locate  # noqa: E402

client = TestClient(app)


def _pdf(case_id: str) -> Path:
    return settings.raw_dir / all_cases()[case_id]["submittal"][0]["file"]


C03, C06 = _pdf("c03"), _pdf("c06")
needs = lambda p: pytest.mark.skipif(not p.exists(), reason="run scripts/fetch_docs.py to download the PDFs")  # noqa: E731


def test_fixture_quotes_appear_verbatim_on_their_page():
    for path in sorted(settings.fixtures_dir.glob("c0*.json")):
        fx = json.loads(path.read_text())
        pages = {p["page"]: p["text"] for p in fx["pages"]}
        for c in fx.get("claims", {}).get("claims", []):
            assert c.get("quote") and c["quote"] in pages[c["page"]], (path.name, c["id"])


def test_every_fixture_quote_resolves_to_a_box():
    checked = 0
    for cid in sorted(all_cases()):
        pdf = _pdf(cid)
        if not pdf.exists():
            continue  # c08 sits behind Cloudflare until downloaded by hand
        for c in json.loads((settings.fixtures_dir / f"{cid}.json").read_text())["claims"]["claims"]:
            page, boxes = locate(pdf, c["page"], c["quote"])
            assert boxes, (cid, c["id"], c["quote"])
            assert all(0 <= b[k] <= 1 for b in boxes for k in ("x0", "y0", "x1", "y1"))
            checked += 1
    if not checked:
        pytest.skip("no PDFs downloaded")


@needs(C06)
def test_locate_falls_back_to_normalized_text_then_the_key_value_line():
    page, exact = locate(C06, 3, "1606.0")
    assert page == 3 and exact
    page, other_page = locate(C06, 1, "1606.0")  # wrong page given: found on the page that has it
    assert page == 3 and other_page
    page, line = locate(C06, 3, "1500 lumen package at 20.5 W")  # not verbatim: line holding "20.5"
    assert page == 3 and line
    assert locate(C06, 3, "qqq zzz nowhere") == (3, [])


@needs(C03)
def test_locate_ignores_line_breaks_and_dash_style():
    _, boxes = locate(C03, 1, "not  to exceed\n120°F (48°C).")
    assert boxes


@needs(C03)
def test_doc_endpoints_serve_pages_and_reject_other_files():
    info = client.get("/api/docs/c03/3m_ic15wb_2005.pdf/pages").json()
    assert info["count"] == 4 and info["pages"][0]["width"] > 0
    png = client.get("/api/docs/c03/3m_ic15wb_2005.pdf/pages/1.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    assert client.get("/api/docs/c03/3m_ic15wb_2005.pdf/pages/9.png").status_code == 404
    for bad in ("..%2F..%2F..%2Fetc%2Fpasswd", "manifest.json", "lithonia_ldn6_2017-10.pdf"):  # traversal, non-submittal, other case
        assert client.get(f"/api/docs/c03/{bad}/pages").status_code == 404, bad


def test_missing_pdf_falls_back_to_text():
    if _pdf("c08").exists():
        pytest.skip("c08 PDF is downloaded")
    assert client.get("/api/docs/c08/lithonia_lqm_2019-09.pdf/pages").status_code == 404
    assert client.get("/api/cases/c08/text").json()["pages"][0]["text"]

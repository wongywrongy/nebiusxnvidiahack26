import hashlib
import json

import pymupdf
import pytest

from api.config import settings
from scripts import check_pdfs, fetch_docs


@pytest.mark.parametrize("fault", [None, "missing", "html", "changed", "corrupt", "coverage", "blank", "scan"])
def test_release_document_preflight_rejects_unusable_or_unreviewed_inputs(tmp_path, monkeypatch, fault):
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(settings, "raw_dir", raw)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(fetch_docs, "targets", lambda: [(["https://maker.test/sheet.pdf"], "sheet.pdf")])
    doc = pymupdf.open()
    page = doc.new_page()
    if fault == "scan":
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 4, 4), False)
        pixmap.clear_with(255)
        page.insert_image(page.rect, pixmap=pixmap)
    elif fault != "blank":
        page.insert_text((72, 72), "Product data sheet")
    data = doc.tobytes() if fault != "corrupt" else b"%PDF-unreadable"
    locked = {"sheet.pdf": {"url": "https://maker.test/sheet.pdf", "sha256": hashlib.sha256(data).hexdigest()}}
    (tmp_path / "documents.lock.json").write_text(json.dumps({"documents": locked if fault != "coverage" else {}}))
    if fault == "html":
        data = b"<html>Cloudflare</html>"
    elif fault == "changed":
        data += b"\nchanged"
    if fault != "missing":
        (raw / "sheet.pdf").write_bytes(data)
    result = check_pdfs.required_documents()
    assert result["passed"] is (fault is None)
    assert bool(result["failures"]) is (fault is not None)
    if fault is None:
        assert result["documents"][0]["pages"] == 1
        assert result["documents"][0]["text_chars"] > 0

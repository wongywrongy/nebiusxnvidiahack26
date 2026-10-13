"""Local OCR turns image text into quoteable evidence without inventing highlight coordinates."""

import asyncio
import shutil

import pymupdf
import pytest

from api.config import settings
from api.llm import load_fixture
from api.pipeline import ingest, runner


def document(text="SPEC CHECK VOC 250", *, scanned=False, pages=1):
    with pymupdf.open() as source:
        page = source.new_page()
        page.insert_text((72, 72), text, fontsize=24)
        if not scanned:
            for _ in range(pages - 1): source.new_page()
            return source.tobytes()
        image = page.get_pixmap(dpi=200).tobytes("png")
    with pymupdf.open() as doc:
        for _ in range(pages):
            page = doc.new_page()
            page.insert_image(page.rect, stream=image)
        return doc.tobytes()


def test_sparse_page_uses_200dpi_ocr_and_dense_text_skips_it(monkeypatch):
    seen = []
    def ocr(image, timeout):
        seen.append((image.size, image.info["dpi"], timeout))
        return "SPEC CHECK VOC 250"
    monkeypatch.setattr(ingest.pytesseract, "image_to_string", ocr)
    result = asyncio.run(ingest.pdf_pages(document(scanned=True)))
    assert result == [{"page": 1, "text": "SPEC CHECK VOC 250", "ocr": True}]
    assert abs(seen[0][1][0] - 200) < 1 and seen[0][2] == 15
    native = asyncio.run(ingest.pdf_pages(document("Native PDF text already contains enough words to avoid OCR processing.")))
    assert not native[0]["ocr"] and len(seen) == 1


def test_ocr_failure_retains_native_text_and_work_is_capped(monkeypatch):
    def fail(*args, **kwargs): raise RuntimeError("Tesseract timed out")
    monkeypatch.setattr(ingest.pytesseract, "image_to_string", fail)
    assert asyncio.run(ingest.pdf_pages(document()))[0] == {"page": 1, "text": "SPEC CHECK VOC 250\n", "ocr": False}
    monkeypatch.setattr(ingest, "MAX_OCR_PAGES", 1)
    calls = []
    monkeypatch.setattr(ingest.pytesseract, "image_to_string", lambda *a, **kw: calls.append(1) or "text")
    pages = asyncio.run(ingest.pdf_pages(document(scanned=True, pages=2)))
    assert len(calls) == 1 and [p["ocr"] for p in pages] == [True, False]
    with pymupdf.open() as doc:
        doc.new_page(width=10000, height=10000)
        assert not asyncio.run(ingest.pdf_pages(doc.tobytes()))[0]["ocr"]
    assert len(calls) == 1


def test_ocr_page_flags_reach_result_and_suppress_native_highlights(monkeypatch, tmp_path):
    pages = [{**p, "ocr": True} for p in load_fixture("c01")["pages"]]
    async def load(case): return pages
    monkeypatch.setattr(runner, "load_submittal_pages", load)
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    run = asyncio.run(runner.execute(runner.Run(["c01"], delay_ms=0)))
    result = run.results["c01"]
    assert result.ocr_pages == len(pages)
    highlights = [h for f in result.findings for h in f.highlights]
    assert highlights and all(h.boxes == [] for h in highlights)


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Local Tesseract executable is not installed")
def test_real_tesseract_reads_generated_image_pdf():
    pages = asyncio.run(ingest.pdf_pages(document(scanned=True)))
    assert pages[0]["ocr"] and "SPEC CHECK VOC 250" in pages[0]["text"]

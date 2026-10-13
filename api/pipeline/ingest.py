"""Step 1: PDF to pages of text.

Live: reads the downloaded PDFs in data/raw/ with PyMuPDF.
Mock, or when a PDF is missing: uses the page text stored in the case fixture.
Uploads always read their own PDF.
Scanned pages use local Tesseract OCR; Nemotron still reads the resulting text through the model router.
"""

from __future__ import annotations

from pathlib import Path
from io import BytesIO
import asyncio
import logging

import pytesseract
from PIL import Image

from ..config import settings
from ..llm import load_fixture

log = logging.getLogger("speccheck.ingest")
MAX_OCR_PAGES = 20
MAX_OCR_PIXELS = 40_000_000


async def pdf_pages(path) -> list[dict]:
    """Text per page. path: a file path, or the PDF's bytes."""
    import pymupdf as fitz

    pages, attempts = [], 0
    with (fitz.open(stream=path, filetype="pdf") if isinstance(path, bytes) else fitz.open(path)) as doc:
        for i, page in enumerate(doc, start=1):
            text, ocr = page.get_text("text"), False
            if len(text.strip()) < 40 and attempts < MAX_OCR_PAGES and page.rect.width * page.rect.height * (200 / 72) ** 2 <= MAX_OCR_PIXELS:
                attempts += 1
                try:
                    with Image.open(BytesIO(page.get_pixmap(dpi=200, colorspace=fitz.csRGB, alpha=False).tobytes("png"))) as image:
                        # Only Tesseract runs on a worker; PyMuPDF document access stays on the event loop.
                        text = await asyncio.to_thread(pytesseract.image_to_string, image, timeout=15) or text
                    ocr = True
                except (RuntimeError, pytesseract.TesseractNotFoundError, pytesseract.TesseractError):
                    log.warning("OCR unavailable or failed for page %d; retaining native text", i)
            pages.append({"page": i, "text": text, "ocr": ocr})
    return pages


def submittal_pdfs(case: dict) -> list[Path]:
    """The case's submittal PDFs that are downloaded, in package order."""
    return [p for doc in case.get("submittal", []) if (p := settings.raw_dir / doc["file"]).exists()]


async def load_submittal_pages(case: dict) -> list[dict]:
    pages: list[dict] = []
    for local in submittal_pdfs(case) if settings.live or case.get("upload") else []:
        offset = len(pages)
        pages += [{**p, "page": p["page"] + offset} for p in await pdf_pages(local)]
    if pages:
        return pages
    return load_fixture(case.get("fixture", case["id"])).get("pages", [])


async def load_spec_text(section: str, spec: dict) -> str:
    local = settings.raw_dir / spec["file"]
    if local.exists():
        return "\n".join(p["text"] for p in await pdf_pages(local))
    return ""


"""Step 1: PDF to pages of text.

Live: reads the downloaded PDFs in data/raw/ with PyMuPDF.
Mock, or when a PDF is missing: uses the page text stored in the case fixture.
Optional upgrade: swap `pdf_pages` for Nemotron Parse on a Nebius Serverless Endpoint.
"""

from __future__ import annotations

from ..config import settings
from ..llm import load_fixture


def pdf_pages(path) -> list[dict]:
    import fitz  # PyMuPDF

    pages = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            pages.append({"page": i, "text": page.get_text("text")})
    return pages


def load_submittal_pages(case: dict) -> list[dict]:
    pages: list[dict] = []
    for doc in case.get("submittal", []):
        local = settings.raw_dir / doc["file"]
        if settings.live and local.exists():
            offset = len(pages)
            pages += [{"page": p["page"] + offset, "text": p["text"]} for p in pdf_pages(local)]
    if pages:
        return pages
    return load_fixture(case["id"]).get("pages", [])


def load_spec_text(section: str, spec: dict) -> str:
    local = settings.raw_dir / spec["file"]
    if local.exists():
        return "\n".join(p["text"] for p in pdf_pages(local))
    return ""

"""Step 1: PDF to pages of text.

Live: reads the downloaded PDFs in data/raw/ with PyMuPDF.
Mock, or when a PDF is missing: uses the page text stored in the case fixture.
Optional upgrade: swap `pdf_pages` for Nemotron Parse on a Nebius Serverless Endpoint.
"""

from __future__ import annotations

from pathlib import Path

from ..config import settings
from ..llm import load_fixture


def pdf_pages(path) -> list[dict]:
    import pymupdf as fitz

    pages = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            pages.append({"page": i, "text": page.get_text("text")})
    return pages


def submittal_pdfs(case: dict) -> list[Path]:
    """The case's submittal PDFs that are downloaded, in package order."""
    return [p for doc in case.get("submittal", []) if (p := settings.raw_dir / doc["file"]).exists()]


def load_submittal_pages(case: dict) -> list[dict]:
    pages: list[dict] = []
    for local in submittal_pdfs(case) if settings.live else []:
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


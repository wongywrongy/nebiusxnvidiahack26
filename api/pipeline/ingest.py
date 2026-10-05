"""Step 1: PDF to pages of text.

Live: reads the downloaded PDFs in data/raw/ with PyMuPDF.
Mock, or when a PDF is missing: uses the page text stored in the case fixture.
Optional upgrade: swap `pdf_pages` for Nemotron Parse on a Nebius Serverless Endpoint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import settings
from ..llm import load_fixture
from ..schemas import Result

TONE = {"fail": "red", "outdated": "amber", "note": "gray", "unverified": "gray"}


def pdf_pages(path) -> list[dict]:
    import fitz  # PyMuPDF

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


# ---------- page images and highlights for the result view ----------


def _open_page(case: dict, n: int):
    """(doc, page) for package page n (1-based, counted across all submittal PDFs), or None."""
    import pymupdf

    if n < 1:
        return None
    for path in submittal_pdfs(case):
        doc = pymupdf.open(path)
        if n <= doc.page_count:
            return doc, doc[n - 1]
        n -= doc.page_count
        doc.close()
    return None


def page_png(case: dict, n: int, scale: float = 1.5) -> Optional[bytes]:
    import pymupdf

    opened = _open_page(case, n)
    if not opened:
        return None
    doc, page = opened
    with doc:
        return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes("png")


def highlights(case: dict, result: Result) -> dict:
    """Pages to show and where each finding's claims sit on them.

    Rects are [x0, y0, x1, y1] as fractions of the page. With no PDF (mock mode) the pages carry
    their text instead of an image and rects are empty: the UI marks the quote in the text.
    """
    pdfs = submittal_pdfs(case) if result.document_source == "pdf" else []
    if pdfs:
        import pymupdf

        count = 0
        for p in pdfs:
            with pymupdf.open(p) as doc:
                count += doc.page_count
        pages = [{"page": i, "image": True, "text": None} for i in range(1, count + 1)]
    else:
        pages = [{"page": p["page"], "image": False, "text": p["text"]} for p in load_fixture(case["id"]).get("pages", [])]

    claims = {c.id: c for c in result.claims}
    out = []
    for f in result.findings:
        if f.verdict == "pass":
            continue
        for cid in f.claim_ids:
            c = claims.get(cid)
            if c is None or c.page is None:
                continue
            rects: list[list[float]] = []
            if pdfs and c.quote and (opened := _open_page(case, c.page)):
                doc, page = opened
                with doc:
                    # ponytail: assumes unrotated pages; rotated scans need page.rotation_matrix applied to rects
                    w, h = page.rect.width, page.rect.height
                    rects = [[round(r.x0 / w, 4), round(r.y0 / h, 4), round(r.x1 / w, 4), round(r.y1 / h, 4)]
                             for r in page.search_for(c.quote)]
            out.append({"finding_id": f.id, "claim_id": cid, "page": c.page, "quote": c.quote,
                        "tone": TONE.get(f.verdict, "gray"), "rects": rects})
    return {"pages": pages, "highlights": out}

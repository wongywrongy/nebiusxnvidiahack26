"""Report how well PyMuPDF reads each downloaded document in data/raw/.

    python scripts/check_pdfs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf as fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402

SCANNED_CHARS_PER_PAGE = 200  # below this a page has little or no text layer


def table_report(doc) -> str:
    """Tables found by PyMuPDF and the share of non-empty cells (low share = garbled)."""
    tables = cells = filled = 0
    for page in doc:
        for t in page.find_tables().tables:
            tables += 1
            for row in t.extract():
                cells += len(row)
                filled += sum(1 for c in row if c and c.strip())
    if not tables:
        return "no tables detected"
    return f"{tables} tables, {filled}/{cells} cells filled ({filled / max(cells, 1):.0%})"


def check(path: Path) -> None:
    rel = path.relative_to(settings.raw_dir)
    if path.read_bytes()[:4] != b"%PDF":
        print(f"\n== {rel}\n   NOT A PDF")
        return
    with fitz.open(path) as doc:
        texts = [p.get_text("text") for p in doc]
        chars = sum(len(t.strip()) for t in texts)
        scanned = [i + 1 for i, t in enumerate(texts) if len(t.strip()) < SCANNED_CHARS_PER_PAGE]
        images = sum(len(p.get_images()) for p in doc)
        print(f"\n== {rel}")
        print(f"   pages={len(doc)}  chars={chars:,}  chars/page={chars // max(len(doc), 1):,}  images={images}")
        print(f"   low-text pages: {scanned or 'none'}" + ("  -> LOOKS SCANNED" if len(scanned) == len(doc) else ""))
        print(f"   tables: {table_report(doc)}")
        print("   page 1: " + " ".join(texts[0].split())[:300] if texts else "   (empty)")


def main() -> None:
    files = sorted(p for p in settings.raw_dir.rglob("*") if p.is_file() and p.name != "manifest.json")
    if not files:
        sys.exit("data/raw/ is empty: run python scripts/fetch_docs.py first")
    for p in files:
        check(p)


if __name__ == "__main__":
    main()

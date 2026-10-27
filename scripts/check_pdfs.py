"""Report how well PyMuPDF reads each downloaded document in data/raw/.

    python scripts/check_pdfs.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
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


def required_documents() -> dict:
    """Release builds require the frozen public document set, never text-fixture fallback."""
    from scripts.fetch_docs import targets
    locked = json.loads((settings.data_dir / "documents.lock.json").read_text())["documents"]
    rows, failures = [], []
    expected = {rel for _, rel in targets()}
    if set(locked) != expected:
        failures.append("Document lock must cover exactly the required spec, case and sample PDFs")
    for rel in sorted(expected):
        path = settings.raw_dir / rel
        row = {"file": rel, "url": locked.get(rel, {}).get("url"), "ok": False}
        try:
            data = path.read_bytes()
            if not data.startswith(b"%PDF"):
                raise ValueError("Not a PDF")
            row["sha256"] = hashlib.sha256(data).hexdigest()
            if row["sha256"] != locked.get(rel, {}).get("sha256"):
                raise ValueError("Document changed; owner must review its URL and text before updating the lock")
            with fitz.open(stream=data, filetype="pdf") as doc:
                if not len(doc) or doc.is_encrypted:
                    raise ValueError("PDF is empty or encrypted")
                lengths = [len(page.get_text().strip()) for page in doc]
                if not any(lengths):
                    raise ValueError("PDF has no readable native text; verify OCR or supply a text-layer copy before release")
                row.update(pages=len(doc), text_chars=sum(lengths),
                           low_text_pages=[n for n, chars in enumerate(lengths, 1) if chars < SCANNED_CHARS_PER_PAGE])
            row["ok"] = True
        except (OSError, ValueError, RuntimeError) as error:
            row["error"] = str(error)
            failures.append(f"{rel}: {row['error']}")
        rows.append(row)
    return {"passed": not failures, "documents": rows, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--required", action="store_true", help="fail if a required PDF is missing, unreadable or differs from the document lock")
    parser.add_argument("--out", type=Path, help="JSON report for --required")
    args = parser.parse_args()
    if args.required:
        report = required_documents()
        print(json.dumps(report, indent=2))
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2) + "\n")
        sys.exit(0 if report["passed"] else 1)
    files = sorted(p for p in settings.raw_dir.rglob("*") if p.is_file() and p.name != "manifest.json")
    if not files:
        sys.exit("data/raw/ is empty: run python scripts/fetch_docs.py first")
    for p in files:
        check(p)


if __name__ == "__main__":
    main()

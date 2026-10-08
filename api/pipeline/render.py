"""Real PDF pages for the review screen: page images, and where a quote sits on a page.

Boxes are fractions of the page size, {x0, y0, x1, y1} in 0-1, so the UI can draw them over
an image of any size.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pymupdf

from ..config import settings

Box = dict[str, float]

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—−"), "-")


@lru_cache(maxsize=64)
def _sha256(path: str, mtime: float) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def page_count(pdf_path: Path) -> int:
    with pymupdf.open(pdf_path) as doc:
        return doc.page_count


def page_sizes(pdf_path: Path) -> list[dict[str, float]]:
    with pymupdf.open(pdf_path) as doc:
        return [{"width": p.rect.width, "height": p.rect.height} for p in doc]


def render_page(pdf_path: Path, page_no: int, dpi: int = 144) -> bytes:
    """PNG of one page (1-based), cached on disk by file hash, page and dpi."""
    cached = settings.cache_dir / "pages" / f"{_sha256(str(pdf_path), pdf_path.stat().st_mtime)}_{page_no}_{dpi}.png"
    if cached.exists():
        return cached.read_bytes()
    with pymupdf.open(pdf_path) as doc:
        png = doc[page_no - 1].get_pixmap(dpi=dpi).tobytes("png")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(png)
    return png


def _norm(s: str) -> str:
    return s.translate(_DASHES).replace("®", "").replace("™", "").lower()


def _boxes(page, rects) -> list[Box]:
    # ponytail: assumes unrotated pages; rotated scans need page.rotation_matrix applied to rects
    w, h = page.rect.width, page.rect.height
    return [{"x0": round(r[0] / w, 4), "y0": round(r[1] / h, 4), "x1": round(r[2] / w, 4), "y1": round(r[3] / h, 4)} for r in rects]


def _line_rects(words: list) -> list[tuple]:
    """One rect per text line spanned by these words."""
    lines: dict[tuple, list] = {}
    for w in words:
        lines.setdefault((w[5], w[6]), []).append(w)
    return [(min(w[0] for w in ws), min(w[1] for w in ws), max(w[2] for w in ws), max(w[3] for w in ws)) for ws in lines.values()]


def _word_match(page, quote: str) -> list[tuple]:
    """The quote as a run of words, ignoring line breaks, spacing, dash style and ®/™."""
    want = _norm(quote).split()
    words = [w for w in page.get_text("words") if _norm(w[4]).strip()]
    toks = [_norm(w[4]) for w in words]
    for i in range(len(toks) - len(want) + 1):
        if toks[i:i + len(want)] == want:
            return _line_rects(words[i:i + len(want)])
    return []


def _same_token(word: str, key: str) -> bool:
    """Equal ignoring punctuation, or the word is the key with a unit glued on ("0.62W" for "0.62")."""
    w, k = re.sub(r"[^\w.]", "", word), re.sub(r"[^\w.]", "", key)
    return w == k or (w.startswith(k) and w[len(k):].isalpha() and len(w) - len(k) <= 3)


def _key_line(page, quote: str) -> list[tuple]:
    """Last resort: the line holding the quote's key token (first token with a digit, else its first two words)."""
    toks = _norm(quote).split()
    key = next(([t] for t in toks if any(c.isdigit() for c in t)), toks[:2])
    if not key:
        return []
    words = page.get_text("words")
    norm = [_norm(w[4]) for w in words]
    for i in range(len(words) - len(key) + 1):
        if norm[i:i + len(key)] == key or (len(key) == 1 and _same_token(norm[i], key[0])):
            line = (words[i][5], words[i][6])
            return _line_rects([w for w in words if (w[5], w[6]) == line])
    return []


def locate(pdf_path: Path, page_no: Optional[int], quote: Optional[str]) -> tuple[Optional[int], list[Box]]:
    """(page where the quote was found, boxes). Tries the given page first, then every page; ([], page_no) if nowhere."""
    if not quote or not quote.strip():
        return page_no, []
    with pymupdf.open(pdf_path) as doc:
        order = ([page_no] if page_no and 1 <= page_no <= doc.page_count else []) + [
            n for n in range(1, doc.page_count + 1) if n != page_no]
        for find in (lambda p: p.search_for(quote), lambda p: _word_match(p, quote), lambda p: _key_line(p, quote)):
            for n in order:
                page = doc[n - 1]
                if rects := find(page):
                    return n, _boxes(page, rects)
    return page_no, []


def attach_highlights(case: dict, claims: list, findings: list) -> None:
    """Give each finding the boxes of its claims on the real PDF pages (mock mode too, so replays have them).

    Claim pages count across the whole package; each highlight records which file and page it is on.
    With no PDF downloaded, highlights keep the quote and package page but no file or boxes.
    """
    from ..schemas import Highlight

    docs, offset = [], 0  # (first package page, file, path, page count)
    for d in case.get("submittal", []):
        path = settings.raw_dir / d["file"]
        if path.exists():
            n = page_count(path)
            docs.append((offset + 1, d["file"], path, n))
            offset += n
    by_id = {c.id: c for c in claims}
    for f in findings:
        if f.verdict == "not_applicable":
            continue
        kind = "checked" if f.verdict == "pass" else "problem"
        for cid in f.claim_ids:
            c = by_id.get(cid)
            if c is None:
                continue
            doc = next(((start, file, path) for start, file, path, n in docs if c.page and start <= c.page < start + n), None)
            if doc is None:
                f.highlights.append(Highlight(claim_id=cid, page=c.page, quote=c.quote, kind=kind))
                continue
            start, file, path = doc
            page, boxes = locate(path, c.page - start + 1, c.quote)
            f.highlights.append(Highlight(claim_id=cid, doc_file=file, page=page, quote=c.quote, boxes=boxes, kind=kind))

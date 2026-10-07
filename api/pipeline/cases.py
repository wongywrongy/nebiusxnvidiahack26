"""Load the test cases, the spec sources, and uploaded submittals."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from functools import lru_cache
from typing import Optional

from ..config import settings


@lru_cache
def all_cases() -> dict[str, dict]:
    data = json.loads(settings.cases_file.read_text())
    return {c["id"]: c for c in data["cases"]}


@lru_cache
def all_specs() -> dict[str, dict]:
    data = json.loads(settings.specs_file.read_text())
    return {s["section"]: s for s in data["specs"]}


def get_case(case_id: str) -> dict:
    case = all_cases().get(case_id) or get_upload(case_id)
    if case is None:
        raise KeyError(f"Unknown case {case_id}")
    return case


# ---------- uploads ----------
# An upload is a case like the others, stored as data/raw/uploads/<id>/case.json next to its PDF.

UPLOAD_ID = re.compile(r"^u-[0-9a-f]{8}$")
LIGHTING = re.compile(r"\b(lumens?|luminaire|led|troffer|downlight|cri|lm/w)\b", re.I)
FIRESTOP = re.compile(r"\b(firestop\w*|fire barrier|intumescent|penetration|f rating|t rating|ul system)\b", re.I)


def get_upload(case_id: str) -> Optional[dict]:
    if not UPLOAD_ID.match(case_id):
        return None
    p = settings.uploads_dir / case_id / "case.json"
    return json.loads(p.read_text()) if p.exists() else None


def _known_fixture(digest: str) -> Optional[str]:
    """The case whose submittal PDF has this sha256, so mock mode can replay its recorded answers."""
    manifest = settings.raw_dir / "manifest.json"
    files = json.loads(manifest.read_text()) if manifest.exists() else {}
    for cid, case in all_cases().items():
        if any(files.get(d["file"], {}).get("sha256") == digest for d in case["submittal"]):
            return cid
    return None


def _section(text: str) -> str:
    """Which project spec the document falls under: the section whose keywords it mentions more."""
    return "26 51 00" if len(LIGHTING.findall(text)) > len(FIRESTOP.findall(text)) else "07 84 00"


def add_upload(name: str, pdf: bytes, text: str) -> dict:
    case_id = f"u-{uuid.uuid4().hex[:8]}"
    stem = re.sub(r"[^\w.-]+", "_", name.rsplit("/", 1)[-1]).strip("._")[:80] or "upload"
    file = f"{stem.removesuffix('.pdf')}.pdf"
    folder = settings.uploads_dir / case_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / file).write_bytes(pdf)
    fixture = _known_fixture(hashlib.sha256(pdf).hexdigest())
    base = all_cases().get(fixture, {})
    case = {
        "id": case_id,
        "title": name.rsplit("/", 1)[-1],
        "section": base.get("section") or _section(text),
        "submittal": [{"role": d["role"], "file": f"uploads/{case_id}/{file}"} for d in base.get("submittal", [{"role": "product_data"}])][:1],
        "conditions": base.get("conditions", []),
        "not_applicable": base.get("not_applicable", []),
        "manufacturer_domains": base.get("manufacturer_domains", []),
        "fixture": fixture,
        "upload": True,
    }
    (folder / "case.json").write_text(json.dumps(case, indent=2))
    return case

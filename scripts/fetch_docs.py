"""Download the public test documents into data/raw/ and record their sha256.

The PDFs are manufacturers' and agencies' documents, so they are not committed to the repo.
Run this once on your machine:  python scripts/fetch_docs.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (SpecCheck hackathon; document fetch)"}


def targets() -> list[tuple[str, str]]:
    cases = json.loads(settings.cases_file.read_text())["cases"]
    specs = json.loads(settings.specs_file.read_text())["specs"]
    out = [(s["url"], s["file"]) for s in specs]
    for c in cases:
        out += [(d["url"], d["file"]) for d in c.get("submittal", [])]
    return out


def main() -> None:
    manifest = {}
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=60) as client:
        for url, rel in targets():
            dest = settings.raw_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                r = client.get(url)
                r.raise_for_status()
            except Exception as e:  # keep going; report at the end
                print(f"FAIL  {rel}  {e}")
                manifest[rel] = {"url": url, "error": str(e)}
                continue
            dest.write_bytes(r.content)
            digest = hashlib.sha256(r.content).hexdigest()
            kind = r.headers.get("content-type", "")
            is_pdf = r.content[:4] == b"%PDF"
            manifest[rel] = {"url": url, "sha256": digest, "bytes": len(r.content), "content_type": kind, "pdf": is_pdf}
            print(f"ok    {rel}  {len(r.content):>9,} bytes  {'PDF' if is_pdf else kind}")
    (settings.raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest: {settings.raw_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()

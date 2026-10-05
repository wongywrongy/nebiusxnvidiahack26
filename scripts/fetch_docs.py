"""Download the public test documents into data/raw/ and record their sha256.

The PDFs are manufacturers' and agencies' documents, so they are not committed to the repo.
Run this once on your machine:  python scripts/fetch_docs.py
Files already in data/raw/ are kept (download blocked ones by hand in a browser, then re-run for the manifest).
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def not_pdf_reason(r: httpx.Response) -> str:
    """Why a response is not a usable PDF, or "" if it is one."""
    if r.content[:4] == b"%PDF":
        return ""
    body = r.content[:20000].lower()
    if b"cloudflare" in body and (b"attention required" in body or b"challenge" in body or b"captcha" in body):
        return "Cloudflare challenge page"
    return f"not a PDF ({r.headers.get('content-type', 'unknown type')})"


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
            if dest.exists():
                data = dest.read_bytes()
                manifest[rel] = {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                                 "pdf": data[:4] == b"%PDF", "kept": True}
                print(f"skip  {rel}  already in data/raw/")
                continue
            try:
                r = client.get(url)
                reason = not_pdf_reason(r)
                if reason.startswith("Cloudflare"):  # comes back as 403; say why
                    raise ValueError(f"{r.status_code} {reason}")
                r.raise_for_status()
                if reason:
                    raise ValueError(reason)
            except Exception as e:  # keep going; report at the end
                print(f"FAIL  {rel}  {e}")
                manifest[rel] = {"url": url, "error": str(e)}
                continue
            dest.write_bytes(r.content)
            manifest[rel] = {"url": url, "sha256": hashlib.sha256(r.content).hexdigest(), "bytes": len(r.content),
                             "content_type": r.headers.get("content-type", ""), "pdf": True}
            print(f"ok    {rel}  {len(r.content):>9,} bytes")
    (settings.raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest: {settings.raw_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()

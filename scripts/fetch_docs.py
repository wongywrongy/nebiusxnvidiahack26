"""Download the public test documents into data/raw/ and record their sha256.

The PDFs are manufacturers' and agencies' documents, so they are not committed to the repo.
Run this once on your machine:  python scripts/fetch_docs.py
URLs come from data/cases/documents.json; each doc's URLs are tried in order, first real PDF wins.
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
from api.providers.tavily import BROWSER_HEADERS as HEADERS  # noqa: E402

DOCUMENTS = settings.data_dir / "cases" / "documents.json"



def not_pdf_reason(r: httpx.Response) -> str:
    """Why a response is not a usable PDF, or "" if it is one."""
    if r.content[:4] == b"%PDF":
        return ""
    body = r.content[:20000].lower()
    if b"cloudflare" in body and (b"attention required" in body or b"challenge" in body or b"captcha" in body):
        return "Cloudflare challenge page"
    return f"not a PDF ({r.headers.get('content-type', 'unknown type')})"


def targets() -> list[tuple[list[str], str]]:
    """(urls in priority order, file) for every spec and case submittal in documents.json."""
    docs = json.loads(DOCUMENTS.read_text())
    out = [(s["urls"], s["file"]) for s in docs["specs"]]
    for c in docs["cases"]:
        out += [(d["urls"], d["file"]) for d in c.get("submittal", [])]
    return out


def fetch(client: httpx.Client, url: str) -> bytes:
    r = client.get(url)
    reason = not_pdf_reason(r)
    if reason.startswith("Cloudflare"):  # comes back as 403; say why
        raise ValueError(f"{r.status_code} {reason}")
    r.raise_for_status()
    if reason:
        raise ValueError(reason)
    return r.content


def main() -> None:
    manifest = {}
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=60) as client:
        for urls, rel in targets():
            dest = settings.raw_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                data = dest.read_bytes()
                manifest[rel] = {"url": urls[0], "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "kept": True}
                print(f"skip  {rel}  already in data/raw/")
                continue
            errors = {}
            for url in urls:
                try:
                    data = fetch(client, url)
                except Exception as e:  # try the next URL; report at the end
                    errors[url] = str(e).splitlines()[0]
                    continue
                dest.write_bytes(data)
                manifest[rel] = {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                print(f"ok    {rel}  {len(data):>9,} bytes  {url}")
                break
            else:
                manifest[rel] = {"errors": errors}
                print(f"FAIL  {rel}  " + "; ".join(errors.values()))
    (settings.raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest: {settings.raw_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()

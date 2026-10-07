"""Tavily search, extract and map over its REST API. Live calls only.

Credits (Tavily docs): search basic 1 / advanced 2, extract 1 per 5 URLs (advanced 2),
map 1 per 10 pages (2 with instructions). Failed extract URLs are free.
Every call: disk cache, then the item/day credit caps, then the call, then the charge.
Each wrapper returns (results, credits spent); a cache hit costs 0.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

import httpx

from .. import cache
from ..config import settings
from . import AuthError, ProviderError, RateLimited, budget

API = "https://api.tavily.com"
log = logging.getLogger("speccheck.tavily")
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def search_credits(depth: str = "basic") -> int:
    return 2 if depth == "advanced" else 1


def extract_credits(urls: int, depth: str = "basic") -> int:
    return math.ceil(urls / 5) * (2 if depth == "advanced" else 1)


def map_credits(pages: int, instructions: Optional[str] = None) -> int:
    """With pages=limit it is the worst case."""
    return max(1, math.ceil(pages / 10)) * (2 if instructions else 1)


async def _post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(API + path, json=body, headers={"Authorization": f"Bearer {settings.secret('tavily_api_key')}"})
    if r.status_code in (401, 403):
        raise AuthError(f"Tavily refused the key ({r.status_code}): check TAVILY_API_KEY")
    if r.status_code in (429, 432, 433):
        raise RateLimited(f"Tavily limit ({r.status_code})")
    if r.is_error:
        raise ProviderError(f"Tavily {path} failed ({r.status_code})")
    return r.json()


async def _cached(ns: str, key: dict, estimate: int, call, credits_of) -> tuple[Any, int]:
    if (hit := cache.get(ns, key)) is not None:
        return hit, 0
    budget.reserve_credits(estimate, real=True)
    results = await call()
    spent = credits_of(results)
    budget.charge_credits(spent, real=True)
    log.info("%s credits=%d results=%d", ns, spent, len(results))
    cache.put(ns, key, results)
    return results, spent


async def search(query: str, include_domains: Optional[list[str]] = None, depth: str = "basic",
                 max_results: int = 5) -> tuple[list[dict], int]:
    async def call():
        body = {"query": query, "search_depth": depth, "max_results": max_results}
        if include_domains:
            body["include_domains"] = include_domains
        resp = await _post("/search", body)
        return [{"url": r["url"], "title": r.get("title", ""), "content": r.get("content", "")} for r in resp.get("results", [])]

    key = {"q": query, "d": include_domains, "depth": depth, "n": max_results}
    return await _cached("tavily_search", key, search_credits(depth), call, lambda _: search_credits(depth))


async def extract(urls: list[str], depth: str = "basic") -> tuple[list[dict], int]:
    """Pages Tavily could not read get one direct try with fetch_pdf (free)."""
    paid: list[int] = []

    async def call():
        resp = await _post("/extract", {"urls": urls, "extract_depth": depth})
        got = [{"url": r["url"], "raw_content": r.get("raw_content", "")} for r in resp.get("results", [])]
        paid.append(len(got))
        for u in set(urls) - {g["url"] for g in got}:
            if pages := await fetch_pdf(u):
                got.append({"url": u, "raw_content": "\n".join(p["text"] for p in pages)})
        return got

    key = {"urls": sorted(urls), "depth": depth}
    return await _cached("tavily_extract", key, extract_credits(len(urls), depth), call,
                         lambda _: extract_credits(paid[0], depth) if paid[0] else 0)


async def map(url: str, instructions: Optional[str] = None, limit: Optional[int] = None,
              max_depth: Optional[int] = None) -> tuple[list[str], int]:
    limit = limit or settings.map_limit
    max_depth = max_depth or settings.map_max_depth

    async def call():
        body = {"url": url, "limit": limit, "max_depth": max_depth, **({"instructions": instructions} if instructions else {})}
        return (await _post("/map", body)).get("results", [])[:limit]  # cap even if the server ignores limit

    key = {"url": url, "i": instructions, "limit": limit, "depth": max_depth}
    return await _cached("tavily_map", key, map_credits(limit, instructions), call, lambda r: map_credits(len(r), instructions))


async def fetch_pdf(url: str) -> Optional[list[dict]]:
    """Direct download with browser headers. Pages of text if the body is a real PDF, else None."""
    from ..pipeline.ingest import pdf_pages

    try:
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True, timeout=60) as c:
            r = await c.get(url)
    except httpx.HTTPError:
        return None
    if r.is_error or not r.content.startswith(b"%PDF"):
        return None
    try:
        return pdf_pages(r.content)
    except Exception:  # truncated or broken PDF
        return None

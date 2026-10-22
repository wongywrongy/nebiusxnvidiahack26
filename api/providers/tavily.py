"""Tavily search, extract and map over its REST API. Live calls only.

Credits (Tavily docs): search basic 1 / advanced 2, extract 1 per 5 URLs (advanced 2),
map 1 per 10 pages (2 with instructions). Reported API usage overrides these estimates.
Every call: disk cache, then the item/day credit caps, then the call, then the charge.
Each wrapper returns (results, credits spent); a cache hit costs 0.
"""

from __future__ import annotations

import logging
import math
import re
import asyncio
from datetime import datetime, timezone
from html import unescape
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

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


def _credits(response: dict, estimate: int) -> int:
    n = (response.get("usage") or {}).get("credits")
    if type(n) is not int or n < 0:
        budget.unknown_usage("Tavily did not report valid usage; credits are estimated")
    return n if type(n) is int and n >= 0 else estimate


def _pdf_syntax(text: str) -> bool:
    return text.lstrip().startswith("%PDF-") or ("startxref" in text[-1000:] and "%%EOF" in text[-1000:])


def _document_link(text: str, base: str) -> Optional[str]:
    from ..pipeline.investigate import Extract

    links = re.finditer(r'''href\s*=\s*["']([^"']+)["']|(https?://[^\s"'<>()[\]]+)''', text, re.I)
    candidates = [m[1] or m[2] for m in links]
    candidates += re.findall(r"\(([^\s)]+\.pdf(?:\?[^\s)]*)?)\)", text, re.I)
    for link in candidates:
        link = urljoin(base, unescape(link))
        if not re.search(r"\.pdf(?:[?#]|$)|/(?:PDS[_-]|[^/?#]*spec[_-]sheet)", link, re.I):
            continue
        try:
            return Extract(url=link).url
        except ValueError:
            continue
    return None


def _pdf_result(requested: str, pages: list[dict]) -> dict:
    return {"url": pages[0].get("source_url", requested), "requested_url": requested,
            "raw_content": "\n".join(p["text"] for p in pages), "pages": pages,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


async def _post(path: str, body: dict) -> dict:
    bound = (search_credits(body.get("search_depth", "basic")) if path == "/search" else
             extract_credits(len(body["urls"]), body.get("extract_depth", "basic")) if path == "/extract" else
             map_credits(body["limit"], body.get("instructions")))
    ticket = budget.reserve_payment(credits=bound)
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(API + path, json=body, headers={"Authorization": f"Bearer {settings.secret('tavily_api_key')}"})
    except httpx.HTTPError as e:
        budget.settle_payment(ticket)
        raise ProviderError("Tavily connection failed") from e
    except BaseException:
        budget.settle_payment(ticket)
        raise
    if r.is_error:
        # Tavily documents failed map/extract requests as free; failed search billing remains unknown.
        budget.settle_payment(ticket, **({"credits": 0} if path in ("/map", "/extract") else {}))
    if r.status_code in (401, 403):
        raise AuthError(f"Tavily refused the key ({r.status_code}): check TAVILY_API_KEY")
    if r.status_code in (429, 432, 433):
        raise RateLimited(f"Tavily limit ({r.status_code})")
    if r.is_error:
        raise ProviderError(f"Tavily {path} failed ({r.status_code})")
    try:
        response = r.json()
    except ValueError as e:
        budget.settle_payment(ticket)
        raise ProviderError("Tavily returned invalid JSON") from e
    usage = response.get("usage") if isinstance(response, dict) else None
    credits = usage.get("credits") if isinstance(usage, dict) else None
    budget.settle_payment(ticket, **({"credits": credits} if type(credits) is int and credits >= 0 else {}))
    return response


async def _cached(ns: str, key: dict, estimate: int, call, credits_of) -> tuple[Any, int]:
    entry = cache.get(ns, key)
    hit = False
    if isinstance(entry, dict) and entry.get("version") == 1 and not cache.REFRESH_WEB.get():
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(entry["retrieved_at"])).total_seconds()
            hit = 0 <= age < (86400 if entry["results"] else 3600)
        except (KeyError, ValueError, TypeError):
            pass
    if hit:
        for issue in entry.get("accounting_issues", []):
            budget.unknown_usage(issue)
        results, spent = entry["results"], 0
    else:
        budget.reserve_credits(estimate, real=True)
        results = await call()
        spent = credits_of(results)
        led = budget.LEDGER.get()
        entry = {"version": 1, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "results": results, "accounting_issues": led.accounting_issues.get(budget.ITEM.get(), []) if led else []}
        cache.put(ns, key, entry)
        log.info("%s credits=%d results=%d", ns, spent, len(results))
    if ns == "tavily_extract":
        results = [{**p, "retrieved_at": p.get("retrieved_at", entry["retrieved_at"]), "cache_hit": hit} for p in results]
    return results, spent


async def search(query: str, include_domains: Optional[list[str]] = None, depth: str = "basic",
                 max_results: int = 5, topic: str = "general", include_published_date: bool = False,
                 exact_match: bool = False, include_domains_mode: Optional[str] = None) -> tuple[list[dict], int]:
    body = {"query": query, "search_depth": depth, "max_results": max_results, "topic": topic,
            "include_published_date": include_published_date, "exact_match": exact_match}
    if include_domains:
        body["include_domains"] = include_domains
        if include_domains_mode:
            body["include_domains_mode"] = include_domains_mode  # without domains the API returns 400

    paid = []
    async def call():
        resp = await _post("/search", {**body, "include_usage": True})
        paid.append(_credits(resp, search_credits(depth)))
        return [{"url": r["url"], "title": r.get("title", ""), "content": r.get("content", ""),
                 **({"published_date": r["published_date"]} if "published_date" in r else {})}
                for r in resp.get("results", [])]

    return await _cached("tavily_search", body, search_credits(depth), call, lambda _: paid[0])


async def extract(urls: list[str], depth: str = "basic") -> tuple[list[dict], int]:
    """Pages Tavily could not read get one direct try with fetch_pdf (free)."""
    paid: list[int] = []

    async def call():
        resp = await _post("/extract", {"urls": urls, "extract_depth": depth, "include_usage": True})
        returned = resp.get("results", [])
        paid.append(_credits(resp, extract_credits(len(returned) if isinstance(returned, list) else len(urls), depth)))
        got = [{"url": r["url"], "raw_content": r.get("raw_content") or ""} for r in returned
               if r.get("raw_content") and not _pdf_syntax(r["raw_content"])]
        if len(got) < len(returned):
            log.warning("Tavily extract returned empty text or raw PDF syntax; trying direct PDF download")
        for u in set(urls) - {g["url"] for g in got}:
            if pages := await fetch_pdf(u):
                got.append(_pdf_result(u, pages))
        return got

    key = {"urls": sorted(urls), "depth": depth}
    results, spent = await _cached("tavily_extract", key, extract_credits(len(urls), depth), call, lambda _: paid[0])
    # Old cache entries may predate the raw-PDF check. Repair only those entries, without paid refetches.
    resolved = []
    for r in results:
        text = r.get("raw_content") or ""
        corrupt = _pdf_syntax(text)
        linked = (not r.get("document_checked") and not r.get("requested_url") and not urlparse(r["url"]).path.lower().endswith(".pdf") and
                  (_document_link(text, r["url"]) or re.search(r"\b(?:product data|spec(?:ification)?)\s+sheet", text, re.I)))
        if corrupt or linked:
            if corrupt:
                log.warning("Tavily extract cache contains raw PDF syntax; trying direct PDF download")
            if pages := await fetch_pdf(r["url"]):
                resolved.append(_pdf_result(r["url"], pages))
                continue
            if linked:
                r = {**r, "document_checked": True}
        if not corrupt:
            resolved.append(r)
    if resolved != results:
        entry = cache.get("tavily_extract", key)
        cache.put("tavily_extract", key, {**entry, "results": resolved})
    return resolved, spent


async def map(url: str, instructions: Optional[str] = None, limit: Optional[int] = None,
              max_depth: Optional[int] = None) -> tuple[list[str], int]:
    limit = limit or settings.map_limit
    max_depth = max_depth or settings.map_max_depth

    paid = []
    async def call():
        body = {"url": url, "limit": limit, "max_depth": max_depth, "include_usage": True,
                **({"instructions": instructions} if instructions else {})}
        resp = await _post("/map", body)
        returned = resp.get("results")
        paid.append(_credits(resp, map_credits(min(limit, len(returned)) if isinstance(returned, list) else limit, instructions)))
        return resp.get("results", [])[:limit]  # cap even if the server ignores limit

    key = {"url": url, "i": instructions, "limit": limit, "depth": max_depth}
    return await _cached("tavily_map", key, map_credits(limit, instructions), call, lambda _: paid[0])


async def fetch_pdf(url: str) -> Optional[list[dict]]:
    """Read a PDF or one linked data sheet, with a bounded total lookup time."""
    from ..pipeline.ingest import pdf_pages

    try:
        async with asyncio.timeout(15):
            async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True, max_redirects=3, timeout=10) as c:
                r = await c.get(url)
                if r.is_success and not r.content.startswith(b"%PDF"):
                    if link := _document_link(r.text, str(r.url)):
                        r = await c.get(link)
    except (httpx.HTTPError, TimeoutError):
        return None
    if r.is_error or not r.content.startswith(b"%PDF"):
        return None
    try:
        return [{**p, "source_url": str(r.url)} for p in await pdf_pages(r.content)]
    except Exception:  # truncated or broken PDF
        return None

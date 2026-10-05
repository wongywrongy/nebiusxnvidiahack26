"""Tavily wrapper with the same mock/live switch as the model router.

Credits (Tavily docs): search basic 1 / advanced 2, extract 1 per 5 URLs (advanced 2),
map 1 per 10 pages. Failed extract/map calls are free.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any, Optional

from . import cache
from .config import settings
from .llm import load_fixture


class WebClient:
    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self.credits = 0.0
        self._tavily = None

    @property
    def tavily(self):
        if self._tavily is None:
            from tavily import AsyncTavilyClient

            if not settings.tavily_api_key:
                raise RuntimeError("TAVILY_API_KEY is not set (live mode)")
            self._tavily = AsyncTavilyClient(api_key=settings.tavily_api_key)
        return self._tavily

    def _fixture(self) -> dict:
        return load_fixture(self.case_id).get("web", {})

    async def search(self, query: str, include_domains: Optional[list[str]] = None, depth: str = "basic") -> list[dict]:
        if not settings.live:
            self.credits += 1
            return self._fixture().get("search", [])
        key = {"q": query, "d": include_domains, "depth": depth}
        hit = cache.get("tavily_search", key)
        if hit is not None:
            return hit
        resp = await self.tavily.search(query=query, include_domains=include_domains or None, search_depth=depth, max_results=5)
        self.credits += 2 if depth == "advanced" else 1
        results = [{"url": r["url"], "title": r.get("title", ""), "content": r.get("content", "")} for r in resp.get("results", [])]
        cache.put("tavily_search", key, results)
        return results

    async def extract(self, urls: list[str], depth: str = "basic") -> list[dict]:
        if not urls:
            return []
        if not settings.live:
            self.credits += math.ceil(len(urls) / 5)
            pages = self._fixture().get("extract", {})
            return [{"url": u, "raw_content": pages[u]} for u in urls if u in pages]
        key = {"urls": sorted(urls), "depth": depth}
        hit = cache.get("tavily_extract", key)
        if hit is not None:
            return hit
        resp = await self.tavily.extract(urls=urls, extract_depth=depth)
        results = [{"url": r["url"], "raw_content": r.get("raw_content", "")} for r in resp.get("results", [])]
        if results:
            self.credits += math.ceil(len(results) / 5) * (2 if depth == "advanced" else 1)
        cache.put("tavily_extract", key, results)
        return results

    async def map(self, url: str, instructions: Optional[str] = None) -> list[str]:
        if not settings.live:
            self.credits += 1
            return self._fixture().get("map", {}).get(url, [])
        key = {"url": url, "i": instructions}
        hit = cache.get("tavily_map", key)
        if hit is not None:
            return hit
        resp = await self.tavily.map(url=url, instructions=instructions) if instructions else await self.tavily.map(url=url)
        links = resp.get("results", [])
        self.credits += max(1, math.ceil(len(links) / 10)) * (2 if instructions else 1)
        cache.put("tavily_map", key, links)
        return links


def snapshot(url: str, text: str) -> dict[str, Any]:
    """Evidence record for a fetched page: what we saw, when, and a hash of it."""
    return {
        "url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "excerpt": text[:400],
    }

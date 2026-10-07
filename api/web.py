"""Web lookups with the same mock/live switch as the model router. Credit math lives in providers/tavily.py."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from .config import settings
from .llm import load_fixture
from .providers import budget, tavily


class WebClient:
    """Mock answers from the case fixture; live goes to providers.tavily. Both charge the run's budget."""

    def __init__(self, case_id: Optional[str]) -> None:  # case_id: which fixture answers in mock mode
        self.case_id = case_id
        self.credits = 0.0

    def _fixture(self) -> dict:
        return load_fixture(self.case_id).get("web", {})

    def _mock_charge(self, n: int) -> None:
        budget.reserve_credits(n, real=False)
        budget.charge_credits(n, real=False)
        self.credits += n

    async def search(self, query: str, include_domains: Optional[list[str]] = None, depth: str = "basic") -> list[dict]:
        if not settings.live:
            self._mock_charge(tavily.search_credits(depth))
            return self._fixture().get("search", [])
        results, spent = await tavily.search(query, include_domains, depth)
        self.credits += spent
        return results

    async def extract(self, urls: list[str], depth: str = "basic") -> list[dict]:
        if not urls:
            return []
        if not settings.live:
            self._mock_charge(tavily.extract_credits(len(urls), depth))
            pages = self._fixture().get("extract", {})
            return [{"url": u, "raw_content": pages[u]} for u in urls if u in pages]
        results, spent = await tavily.extract(urls, depth)
        self.credits += spent
        return results

    async def map(self, url: str, instructions: Optional[str] = None,
                  limit: Optional[int] = None, max_depth: Optional[int] = None) -> list[str]:
        if not settings.live:
            self._mock_charge(1)
            return self._fixture().get("map", {}).get(url, [])[:limit or settings.map_limit]
        links, spent = await tavily.map(url, instructions, limit, max_depth)
        self.credits += spent
        return links


def snapshot(url: str, text: str) -> dict[str, Any]:
    """Evidence record for a fetched page: what we saw, when, and a hash of it."""
    return {
        "url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "excerpt": text[:400],
    }

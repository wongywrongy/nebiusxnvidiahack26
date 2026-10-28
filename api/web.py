"""Web lookups with the same mock/live switch as the model router. Credit math lives in providers/tavily.py."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .config import settings
from . import archive, cache
from .llm import load_fixture
from .providers import budget, tavily, failure_reason


class WebClient:
    """Mock answers from the case fixture; live goes to providers.tavily. Both charge the run's budget."""

    def __init__(self, case_id: Optional[str], on_step=None, on_warning=None) -> None:  # which fixture answers in mock mode
        self.case_id = case_id
        self.credits = 0.0
        self.on_step = on_step
        self.on_warning = on_warning
        self.investigation_step: Optional[int] = None

    async def warn(self, stage: str, error: Exception) -> None:
        if self.on_warning:
            await self.on_warning(stage, failure_reason(error))

    def _investigation_result(self):
        if self.investigation_step is None:
            return None
        steps = load_fixture(self.case_id).get("investigate", {}).get("steps", [])
        return steps[self.investigation_step].get("result", []) if self.investigation_step < len(steps) else []

    def _fixture(self) -> dict:
        return load_fixture(self.case_id).get("web", {})

    def _mock_charge(self, n: int) -> None:
        budget.reserve_credits(n, real=False)
        budget.charge_credits(n, real=False)
        self.credits += n

    async def search(self, query: str, include_domains: Optional[list[str]] = None, depth: Optional[str] = None,
                     topic: str = "general", include_published_date: bool = False, exact_match: bool = False,
                     include_domains_mode: Optional[str] = None, max_results: Optional[int] = None) -> list[dict]:
        depth = depth or settings.search_depth
        max_results = max_results if max_results is not None else settings.search_max_results
        if not settings.live:
            self._mock_charge(tavily.search_credits(depth))
            results = self._investigation_result() if self.investigation_step is not None else self._fixture().get("search", [])
            return results[:max_results]
        results, spent = await tavily.search(query, include_domains, depth, max_results=max_results, topic=topic,
                                            include_published_date=include_published_date, exact_match=exact_match,
                                            include_domains_mode=include_domains_mode)
        self.credits += spent
        return results

    async def image_text(self, url: str) -> list[str]:
        """OCR of the images embedded in a page (e.g. a replacement table on a discontinuation notice).
        Mock: fixture web.images[url]. Live: one direct GET of the page, no Tavily credits; cached by URL."""
        if not settings.live:
            return self._fixture().get("images", {}).get(url, [])
        if (hit := cache.get("page_image_ocr", {"url": url})) is not None:
            return hit
        try:
            async with httpx.AsyncClient(headers=tavily.BROWSER_HEADERS, follow_redirects=True, max_redirects=3, timeout=20) as c:
                html = (await c.get(url)).text
        except httpx.HTTPError as error:
            await self.warn("fix", error)
            return []
        # shortcut: inline data: images only (the case seen live); linked <img src=https://…> files are not fetched.
        found = re.findall(r'src="data:image/(?:png|jpe?g|gif);base64,([A-Za-z0-9+/=]{200,4000000})"', html)[:6]
        texts = [t for t in [await asyncio.to_thread(_ocr, base64.b64decode(b)) for b in found] if len(t.strip()) >= 20]
        cache.put("page_image_ocr", {"url": url}, texts)
        return texts

    async def extract(self, urls: list[str], depth: Optional[str] = None) -> list[dict]:
        depth = depth or settings.extract_depth
        if not urls:
            return []
        if not settings.live:
            self._mock_charge(tavily.extract_credits(len(urls), depth))
            if self.investigation_step is not None:
                results = self._investigation_result()
            else:
                pages = self._fixture().get("extract", {})
                results = [{"url": u, "raw_content": pages[u]} for u in urls if u in pages]
        else:
            results, spent = await tavily.extract(urls, depth)
            self.credits += spent
        sources = []
        for page in results:
            meta = snapshot(page["url"], page.get("raw_content", ""), page.get("retrieved_at"))
            meta["archived_path"] = archive.save(budget.ITEM.get() or self.case_id or "unknown",
                                                page.get("raw_content", "").encode(), "txt", meta["retrieved_at"])
            sources.append({**page, **meta})
        return sources

    async def map(self, url: str, instructions: Optional[str] = None,
                  limit: Optional[int] = None, max_depth: Optional[int] = None) -> list[str]:
        if not settings.live:
            results = (self._investigation_result() if self.investigation_step is not None
                       else self._fixture().get("map", {}).get(url, []))[:limit or settings.map_limit]
            self._mock_charge(tavily.map_credits(len(results), instructions))
            return results
        links, spent = await tavily.map(url, instructions, limit, max_depth)
        self.credits += spent
        return links


def snapshot(url: str, text: str, retrieved_at: Optional[str] = None) -> dict[str, Any]:
    """Evidence record for a fetched page: what we saw, when, and a hash of it."""
    return {
        "url": url,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "excerpt": text[:400],
    }


def _ocr(data: bytes) -> str:
    """Tesseract on one image: grey, 2x upscale, one column of text lines (--psm 4 reads tables row by row)."""
    import pytesseract
    from PIL import Image
    try:
        image = Image.open(io.BytesIO(data)).convert("L")
        image = image.resize((image.width * 2, image.height * 2), Image.BICUBIC)
        return pytesseract.image_to_string(image, config="--psm 4", timeout=20)
    except (OSError, RuntimeError, pytesseract.TesseractNotFoundError, pytesseract.TesseractError):
        return ""

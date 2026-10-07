"""Live spike: Tavily search, map and extract against 3 URLs from cases.json. Costs real credits.

    python scripts/spike_tavily.py

Everything is basic depth and cached in .cache/, so a re-run is free.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ["SPECCHECK_MODE"] = "live"  # before api.config is imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api.providers.tavily import map_credits  # noqa: E402
from api.web import WebClient  # noqa: E402

# (label, url, search query, domains, words that should show up in usable text)
TARGETS = [
    ("c01 Hilti FS-ONE MAX TDS (PDF)", "https://hilti.ca/media-canonical/ASSET_DOC_LOC_4226707_APC_RAW",
     "Hilti FS-ONE MAX intumescent firestop sealant technical data sheet", ["hilti.com", "hilti.ca"], ["FS-ONE", "ASTM"]),
    ("CPS 07 84 00 spec (PDF)", "https://www.cps.edu/globalassets/cps-pages/services-and-supports/school-facilities/facilities-standards/cps-infrastructure-handbook/firestopping-new/07-84-00-firestopping.pdf",
     "Chicago Public Schools 07 84 00 firestopping specification", ["cps.edu"], ["FIRESTOPPING", "UL 1479"]),
    ("c07 Acuity TL discontinuation (HTML)", "https://insights.acuitybrands.com/product-updates-blog/discontinuation-notice-lithonia-lighting-tl-recessed-luminaire-2",
     "Lithonia TL recessed troffer discontinued", ["acuitybrands.com"], ["TL", "discontinu"]),
]


def estimate() -> int:
    search = len(TARGETS)  # basic = 1 credit each
    extract = -(-len(TARGETS) // 5)  # 1 credit per 5 URLs, failed URLs are free
    mapping = len(TARGETS) * map_credits(settings.map_limit)  # worst case: every map hits the cap
    total = search + extract + mapping
    print(f"  search {search}  +  extract {extract}  +  map <= {mapping}  =  <= {total} credits"
          f"  (~${total * settings.tavily_credit_usd:.2f} at ${settings.tavily_credit_usd}/credit)")
    return total


def usable(text: str, words: list[str]) -> str:
    if not text:
        return "EMPTY"
    if text.lstrip().startswith("%PDF") or sum(not c.isprintable() and c not in "\n\t" for c in text[:2000]) > 50:
        return "RAW BINARY (not parsed)"
    hits = [w for w in words if w.lower() in text.lower()]
    return f"{'usable' if hits else 'text, but expected words missing'} ({len(text):,} chars, found {hits})"


async def main() -> None:
    if not settings.secret("tavily_api_key"):
        sys.exit("TAVILY_API_KEY is not set (put it in .env)")
    print("Estimated Tavily cost:")
    estimate()
    if input("Run live? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")

    web = WebClient("spike")

    print("\n### extract (one call, basic)")
    pages = {r["url"]: r["raw_content"] for r in await web.extract([t[1] for t in TARGETS])}
    for label, url, _, _, words in TARGETS:
        text = pages.get(url, "")
        print(f"\n== {label}\n   {usable(text, words) if url in pages else 'FAILED (not returned by Tavily)'}")
        if text:
            print("   " + " ".join(text.split())[:300])

    print("\n### search (basic)")
    for label, _, query, domains, _ in TARGETS:
        results = await web.search(query, include_domains=domains)
        print(f"\n== {label}: {query!r} in {domains}")
        for r in results:
            print(f"   {r['url']}")

    print(f"\n### map (limit {settings.map_limit}, depth {settings.map_max_depth})")
    for label, url, *_ in TARGETS:
        try:
            links = await web.map(url)
            print(f"\n== {label}: {len(links)} links")
            for link in links[:5]:
                print(f"   {link}")
        except Exception as e:
            print(f"\n== {label}: ERROR {type(e).__name__}: {str(e)[:200]}")

    print(f"\nCredits counted by WebClient: {web.credits}")


if __name__ == "__main__":
    asyncio.run(main())

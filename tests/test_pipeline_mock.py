"""End-to-end mocks preserve the key and Kyle's documented selection-policy disagreements."""

import asyncio
import os
import sys
from pathlib import Path

import pytest
os.environ.setdefault("SPECCHECK_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.pipeline.cases import all_cases  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402


def test_case_disagreements_are_exactly_the_reviewed_selection_policy():
    ids = sorted(all_cases())
    run = asyncio.run(execute(Run(ids, delay_ms=0)))
    disagreements = {cid: (all_cases()[cid]["expected"]["decision"], run.results[cid].decision)
                     for cid in ids if run.results[cid].decision != all_cases()[cid]["expected"]["decision"]}
    # Kyle accepted unselected configurations as unconfirmed on 2026-10-22; the raw key stays unchanged.
    assert disagreements == {"c05": ("approve", "approve_with_note"),
                             "c06": ("send_back", "approve_with_note")}
    from api.pipeline.scores import scores
    panel = scores(run, ids)
    assert panel["right_call"] == {"n": 6, "of": 8}
    assert panel["caught"] == {"n": 5, "of": 6}
    assert panel["validity"]["invalid_items"] == 0
    assert not panel["release_gate"]["passed"]
    stages = {e.stage for e in run.events}
    assert {"queued", "ingest", "triage", "extract", "spec_check", "verify", "report", "done"} <= stages


def test_code_decides_and_titles_are_short():
    run = asyncio.run(execute(Run(sorted(all_cases()), delay_ms=0)))
    for cid, res in run.results.items():
        assert "ultra" not in {u.tier for u in res.usage}, cid  # no model reviews or drops findings
        for f in res.findings:
            assert len(f.title.split()) <= 8, (cid, f.title)


def test_claims_without_their_quote_on_the_page_are_dropped():
    from api.pipeline.extract import quoted

    assert quoted("not  to exceed\n120°F", "Continuous operating temperature not to exceed 120°F (48°C).")
    assert not quoted("not to exceed 150°F", "not to exceed 120°F")
    assert not quoted(None, "anything") and not quoted("  ", "anything")


def test_quote_normalization_keeps_words_numbers_and_page_evidence_exact():
    from api.pipeline.extract import quoted

    assert quoted(r"Voltage:\n120", "Voltage:\n120")
    assert quoted("Voltage:\n120", r"Voltage:\n120")
    assert quoted("Maker fine sealant", "Maker\u2122 \ufb01ne sealant\u00ae")
    assert not quoted(r"Voltage:\n240", "Voltage:\n120")
    assert not quoted("Meets the test criteria", "Passes the test criteria")
    assert not quoted("rated 120 volts", "rated 120 watts")
    assert not quoted(r"\n\t", "anything")
    assert not quoted("\u2122\u00ae", "anything")
    assert quoted("As of June 30th, 2024, the LX family is discontinued.",
                  "As of **June 30th, 2024**, the LX family is discontinued.")
    assert not quoted("As of June 30th, 2025, the LX family is discontinued.",
                      "As of **June 30th, 2024**, the LX family is discontinued.")
    assert quoted("VOC Content** 26 g/L", "VOC Content**\n26 g/L\n**VOC uses a stated test method.\nVOC Content**")
    assert not quoted("VOC Content 26 g/L", "VOC Content**\n26 g/L")
    assert quoted(r"Reported life 64,000 hours @25\u00b0C", "Reported life 64,000 hours @25°C")
    assert quoted("Reported life 64,000 hours @25°C", r"Reported life 64,000 hours @25\u00b0C")
    assert not quoted(r"Reported life 65,000 hours @25\u00b0C", "Reported life 64,000 hours @25°C")
    assert not quoted(r"Reported life 64,000 hours @25\u00b0F", "Reported life 64,000 hours @25°C")
    assert not quoted(r"\u2122\u00ae", "anything")


@pytest.mark.parametrize("property,quote,value,kept", [
    ("l70_hours", "80% lumen maintenance at 60,000 hours (L80/60,000)", 60000, False),
    ("l70_hours", "70% lumen maintenance at 50,000 hours", 50000, True),
    ("l80_hours", "L80 at 60,000 hours", 60000, True),
    ("t_rating_hr", "Provides up to a four-hour fire rating", 4, False),
    ("t_rating_hr", "T-RATING = 0-HR.", 0, True),
    ("f_rating_hr", "F Rating — 2 Hr", 2, True),
    ("f_rating_hr", "F Ratings — 1 and 2 Hr", 2, True),
    ("cri", "75 – 80 typical LPW", 80, False),
    ("cri", "80 CRI", 80, True),
    ("cri", "82CRI, 3500 K", 82, True),
    ("warranty_years", "© 2016-2024 Maker. All rights reserved.", 5, False),
])
def test_related_metrics_cannot_be_relabelled(property, quote, value, kept, monkeypatch):
    from api.pipeline import extract
    from api.schemas import ClaimsOut, Usage
    async def call(*args, **kwargs):
        return ClaimsOut(product="X", manufacturer="Maker", claims=[{
            "id": "measurement", "product": "X", "manufacturer": "Maker", "property": property,
            "value": value, "page": 1, "quote": quote}]), Usage(task="extract_claims", tier="extract", model="test")
    monkeypatch.setattr(extract.router, "call", call)
    pages = [{"page": 1, "text": quote}]
    result, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), [property]))
    assert bool(result.claims) is kept


@pytest.mark.parametrize("variant,kept", [("Optional driver", True), ("Different driver", False), (None, True)])
def test_option_scope_must_be_in_the_supporting_quote(variant, kept, monkeypatch):
    from api.pipeline import extract
    from api.schemas import ClaimsOut, Usage
    quote = "Optional driver: measurement 10"
    async def call(*args, **kwargs):
        return ClaimsOut(product="X", manufacturer="Maker", claims=[{
            "id": "measurement", "product": "X", "manufacturer": "Maker", "property": "measurement",
            "value": 10, "page": 1, "quote": quote, "variant": variant}]), Usage(task="extract_claims", tier="extract", model="test")
    monkeypatch.setattr(extract.router, "call", call)
    pages = [{"page": 1, "text": quote}]
    result, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["measurement"]))
    assert bool(result.claims) is kept
    if kept:
        assert result.claims[0].variant == "Optional driver"

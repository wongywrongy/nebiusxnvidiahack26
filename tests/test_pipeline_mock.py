"""End-to-end in mock mode: all 8 cases must match the answer key."""

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("SPECCHECK_MODE", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.pipeline.cases import all_cases  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402


def test_all_cases_match_answer_key():
    ids = sorted(all_cases())
    run = asyncio.run(execute(Run(ids, delay_ms=0)))
    for cid in ids:
        res = run.results[cid]
        assert res.decision == all_cases()[cid]["expected"]["decision"], cid
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

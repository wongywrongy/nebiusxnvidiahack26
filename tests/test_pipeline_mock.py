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


def test_ultra_only_called_when_something_is_flagged():
    run = asyncio.run(execute(Run(["c01", "c03"], delay_ms=0)))
    tiers = {cid: {u.tier for u in run.results[cid].usage} for cid in ("c01", "c03")}
    assert "ultra" not in tiers["c01"]
    assert "ultra" in tiers["c03"]

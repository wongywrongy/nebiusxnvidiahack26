"""The wrong-spec set runs as uploads and writes its block next to the existing scores."""

import asyncio
import importlib.util
import json
from pathlib import Path

from api.config import settings

spec = importlib.util.spec_from_file_location("eval_wrong_spec", Path(__file__).resolve().parents[1] / "scripts/eval_wrong_spec.py")
wrong = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrong)


def test_mock_wrong_spec_set_approves_nothing_and_keeps_existing_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    monkeypatch.setattr(settings, "raw_dir", tmp_path / "raw")
    into = tmp_path / "scores.json"
    into.write_text(json.dumps({"right_call": {"n": 6, "of": 8}}))
    assert asyncio.run(wrong.main(into)) == 0
    scores = json.loads(into.read_text())
    block = scores["wrong_spec"]
    assert scores["right_call"] == {"n": 6, "of": 8}
    assert block["approved"] == 0 and block["n"] == block["not_applicable"] + block["other"] >= 9
    assert {r["section"] for r in block["rows"] if r["id"] == "w-c01"} == {"26 51 00"}

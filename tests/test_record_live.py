import asyncio
import json

import pytest

from api.config import settings
from api.pipeline.cases import all_cases, all_samples
from api.schemas import Result


def test_extra_items_run_without_entering_the_scoreboard(monkeypatch, tmp_path):
    from scripts.eval import main

    monkeypatch.setattr(settings, "speccheck_mode", "mock")
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    output = tmp_path / "scores.json"
    assert asyncio.run(main(["c01"], output, extra_ids=["c02", "c01"])) == 0
    scores = json.loads(output.read_text())
    assert [row["id"] for row in scores["rows"]] == ["c01"]
    assert scores["right_call"] == {"n": 1, "of": 1}
    assert (settings.runs_dir / scores["run_id"] / "results/c02.json").is_file()


@pytest.mark.parametrize("omit_sample", [False, True])
def test_record_includes_public_samples_and_rejects_incomplete_runs(monkeypatch, tmp_path, omit_sample):
    from scripts import record_live

    monkeypatch.setenv("SPECCHECK_MODE", "mock")
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    monkeypatch.setattr(settings, "recorded_dir", tmp_path / "recorded")
    monkeypatch.setattr(settings, "scores_file", tmp_path / "scores.json")
    monkeypatch.setattr(record_live, "ROOT", tmp_path)

    async def scoreboard(case_ids, *, extra_ids):
        assert case_ids == sorted(all_cases())
        public = {cid for cid, item in {**all_cases(), **all_samples()}.items()
                  if item.get("tray") or item.get("watch")}
        assert set(extra_ids) == public and {"s3", "s4"} <= public
        assert "s1" not in extra_ids and "s2" not in extra_ids
        folder = settings.runs_dir / "test-recording" / "results"
        folder.mkdir(parents=True)
        for cid in set(case_ids + extra_ids) - ({"s4"} if omit_sample else set()):
            (folder / f"{cid}.json").write_text(Result(case_id=cid, title=cid, decision="approve", summary="",
                                                     findings=[], validity="valid", mode="live").model_dump_json())
        settings.scores_file.write_text(json.dumps({"run_id": "test-recording", "rows": case_ids}))
        return 1  # Honest wrong calls must not prevent recording a complete live run.

    monkeypatch.setattr(record_live, "scoreboard", scoreboard)
    if omit_sample:
        with pytest.raises(SystemExit, match="missing results: s4"):
            record_live.record()
        assert not settings.recorded_dir.exists()
    else:
        assert record_live.record() == 1
        folder = settings.recorded_dir / "test-recording"
        assert {p.stem for p in (folder / "results").glob("*.json")} >= {*all_cases(), "s3", "s4"}
        assert json.loads((folder / "scores.json").read_text())["rows"] == sorted(all_cases())


def test_record_rejects_invalid_public_sample(monkeypatch, tmp_path):
    from scripts import record_live
    monkeypatch.setenv("SPECCHECK_MODE", "mock")
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    monkeypatch.setattr(settings, "scores_file", tmp_path / "scores.json")
    monkeypatch.setattr(settings, "recorded_dir", tmp_path / "recorded")
    async def scoreboard(case_ids, *, extra_ids):
        folder = settings.runs_dir / "invalid-sample" / "results"
        folder.mkdir(parents=True)
        for cid in set(case_ids + extra_ids):
            result = Result(case_id=cid, title=cid, decision="approve", summary="", findings=[], mode="live",
                            validity="invalid" if cid == "s3" else "valid")
            (folder / f"{cid}.json").write_text(result.model_dump_json())
        settings.scores_file.write_text(json.dumps({"run_id": "invalid-sample"}))
        return 0
    monkeypatch.setattr(record_live, "scoreboard", scoreboard)
    with pytest.raises(SystemExit, match="invalid acceptance evidence for s3"):
        record_live.record()
    assert not settings.recorded_dir.exists()

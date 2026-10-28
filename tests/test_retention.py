import asyncio
import json
import logging
import os
from pathlib import Path

import pymupdf
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import main, watch_store
from api.config import settings
from api.pipeline import render, runner


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(settings, "evidence_dir", None)
    monkeypatch.setattr(main, "RUNS", {})
    monkeypatch.setattr(runner, "ACTIVE_RUNS", set())
    monkeypatch.setattr(runner, "REPLAY_READERS", runner.Counter())
    return tmp_path


def test_page_cache_evicts_least_recently_viewed_page(storage, monkeypatch):
    pdf = storage / "pages.pdf"
    with pymupdf.open() as doc:
        for _ in range(3):
            doc.new_page().insert_text((72, 72), "Identical page content for cache testing.")
        doc.save(pdf)
    png = render.render_page(pdf, 1)
    render.render_page(pdf, 2)
    files = sorted((settings.cache_dir / "pages").glob("*.png"))
    assert len(files) == 2
    os.utime(files[0], (1, 1))
    os.utime(files[1], (2, 2))
    monkeypatch.setattr(render, "PAGE_CACHE_MAX_BYTES", 2 * len(png))
    assert render.render_page(pdf, 1) == png  # a cache hit makes page 1 newer than page 2
    render.render_page(pdf, 3)
    kept = list((settings.cache_dir / "pages").glob("*.png"))
    assert sum(p.stat().st_size for p in kept) <= render.PAGE_CACHE_MAX_BYTES
    assert any("_1_" in p.name for p in kept) and any("_3_" in p.name for p in kept)
    assert not any("_2_" in p.name for p in kept)


def test_disk_retention_keeps_500_and_never_touches_recordings_watch_or_foreign_folders(storage):
    folder = settings.runs_dir
    for name in ("watch", "recorded", "notes"):
        (folder / name).mkdir(parents=True)
        (folder / name / "keep").write_text("untouched")
    for i in range(505):
        run = folder / f"20261013-{i:06d}-abcdef"
        run.mkdir()
        (run / "events.jsonl").write_text("")
    runner.prune_runs()
    generated = [p for p in folder.iterdir() if runner.RUN_ID.fullmatch(p.name)]
    assert len(generated) == 500
    assert not (folder / "20261013-000004-abcdef").exists()
    assert (folder / "20261013-000005-abcdef").is_dir()
    assert all((folder / name / "keep").read_text() == "untouched" for name in ("watch", "recorded", "notes"))


def test_active_runs_and_replay_sources_are_not_pruned(storage, monkeypatch):
    monkeypatch.setattr(runner, "MAX_DISK_RUNS", 2)
    first = runner.Run(["c01"], delay_ms=0)
    asyncio.run(runner.execute(first))
    second = runner.Run(["c01"], delay_ms=0)
    asyncio.run(runner.execute(second))
    replay = runner.Run([], replay_of=first.id)
    assert first.dir.exists() and replay.dir.exists()
    assert not second.dir.exists()
    asyncio.run(runner.replay(replay, first.id, speed=1e6))
    assert replay.results["c01"].replayed_from == first.id
    assert not runner.ACTIVE_RUNS and not runner.REPLAY_READERS


def test_memory_retention_falls_back_to_disk_and_rejects_full_active_queue(storage, monkeypatch):
    monkeypatch.setattr(main, "MAX_MEMORY_RUNS", 2)
    first = main._new_run(["c01"], delay_ms=0)
    asyncio.run(runner.execute(first))
    second = main._new_run([], delay_ms=0)
    third = main._new_run([], delay_ms=0)
    assert list(main.RUNS) == [second.id, third.id]
    client = TestClient(main.app)
    assert client.get(f"/api/runs/{first.id}/results/c01").status_code == 200
    assert "event: end" in client.get(f"/api/runs/{first.id}/events").text
    with pytest.raises(HTTPException) as error:
        main._new_run([])
    assert error.value.status_code == 503 and len(main.RUNS) == 2


def test_watch_state_survives_container_replacement_and_reads_bucket_first(storage, monkeypatch):
    monkeypatch.setattr(settings, "evidence_dir", storage / "bucket")
    report = {"checked_at": "2026-10-13T12:00:00Z", "mode": "mock", "runner": "offline test", "items": []}
    watch_store.report(report)
    assert (settings.runs_dir / "watch/latest.json").is_file()
    monkeypatch.setattr(settings, "runs_dir", storage / "replacement/runs")
    assert main.latest_recheck() == report
    local = settings.runs_dir / "watch/latest.json"
    local.parent.mkdir(parents=True)
    local.write_text(json.dumps({"runner": "stale image fallback"}))
    assert main.latest_recheck() == report
    (settings.evidence_dir / "watch/latest.json").write_text("truncated")
    assert main.latest_recheck()["runner"] == "stale image fallback"


def test_startup_logs_spend_caps_and_health_has_resource_metrics(storage, caplog):
    with caplog.at_level(logging.INFO), TestClient(main.app) as client:
        health = client.get("/api/health").json()
    assert health["uptime_s"] >= 0 and health["disk_free_gb"] > 0
    assert "Today's recorded spend:" in caplog.text and "budget_usd_per_day" in caplog.text
    assert "campaign ledger on local disk" in caplog.text and "hosted persistence unverified" in caplog.text

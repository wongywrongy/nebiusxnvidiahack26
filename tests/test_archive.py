import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from api import main
from api.config import settings
from api.pipeline.runner import Run, execute
from api.web import WebClient


def test_archive_keeps_full_sources_and_links_quoted_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "evidence_dir", tmp_path / "evidence")
    monkeypatch.setattr(settings, "evidence_label", "Nebius Object Storage")
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    run = asyncio.run(execute(Run(["c01"], delay_ms=0)))
    result = run.results["c01"]
    assert result.evidence_label == "Nebius Object Storage"
    source = next(e for f in result.findings for e in f.evidence if e.archived_path)
    path = settings.evidence_dir / source.archived_path
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == source.sha256
    client = TestClient(main.app)
    assert client.get("/api/evidence/" + source.archived_path).content == path.read_bytes()
    assert client.get("/api/evidence/../scores.json").status_code == 404
    assert client.get("/api/evidence/watch/jobs.json").status_code == 404
    assert all(p.suffix in (".txt", ".pdf") for p in settings.evidence_dir.rglob("*") if p.is_file())


def test_archive_skips_unset_and_unavailable_storage(tmp_path, monkeypatch):
    from api import archive
    monkeypatch.setattr(settings, "evidence_dir", None)
    assert archive.save("c01", b"text", "txt") is None
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    monkeypatch.setattr(settings, "evidence_dir", blocked)
    assert archive.save("../../c01", b"text", "txt") is None


def test_approved_and_watched_pdfs_are_archived(tmp_path, monkeypatch):
    import pymupdf
    from api.pipeline.cases import all_cases
    monkeypatch.setattr(settings, "evidence_dir", tmp_path / "evidence")
    monkeypatch.setattr(settings, "raw_dir", tmp_path / "raw")
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    for cid in ("c01", "c02", "c07"):
        for entry in all_cases()[cid]["submittal"]:
            path = settings.raw_dir / entry["file"]
            path.parent.mkdir(parents=True, exist_ok=True)
            with pymupdf.open() as doc:
                doc.new_page().insert_text((72, 72), "Synthetic archive test PDF. No product claims.")
                doc.save(path)
    run = asyncio.run(execute(Run(["c01", "c02", "c07"], delay_ms=0)))
    assert run.results["c01"].archived_submittals and run.results["c07"].archived_submittals
    assert not run.results["c02"].archived_submittals
    for cid in ("c01", "c07"):
        for saved in run.results[cid].archived_submittals:
            assert (settings.evidence_dir / saved).read_bytes().startswith(b"%PDF")


def test_scores_prefers_newer_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "evidence_dir", tmp_path)
    monkeypatch.setattr(settings, "scores_file", tmp_path / "local.json")
    settings.scores_file.write_text('{"origin":"local"}')
    archive = tmp_path / "scores.json"
    archive.write_text('{"origin":"archive","job_name":"fixture-eval"}')
    os.utime(archive, (100, 100))
    client = TestClient(main.app)
    assert client.get("/api/scores").json()["origin"] == "local"
    os.utime(settings.scores_file, (50, 50))
    assert client.get("/api/scores").json()["job_name"] == "fixture-eval"


def test_eval_output_aliases_and_job_metadata(tmp_path):
    for flag in ("--out", "--write"):
        dest = tmp_path / f"{flag}.json"
        env = {**os.environ, "SPECCHECK_MODE": "mock", "JOB_NAME": "fixture-eval",
               "RECHECK_RUNNER": "fake CLI", "RUNS_DIR": str(tmp_path / "runs"), "EVIDENCE_DIR": ""}
        proc = subprocess.run([sys.executable, "scripts/eval.py", "--case", "c01", flag, str(dest)],
                              env=env, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        scores = json.loads(dest.read_text())
        assert scores["job_name"] == "fixture-eval" and scores["mode"] == "mock" and scores["runner"] == "fake CLI"

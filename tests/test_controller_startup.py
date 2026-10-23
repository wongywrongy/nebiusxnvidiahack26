import hashlib
import json

import pymupdf
import pytest
from fastapi.testclient import TestClient

from api import authority, controller_startup
from api.config import settings
from api.main import app
from api.providers.budget import BudgetExceeded
from scripts import fetch_docs, serve

pytestmark = pytest.mark.campaign


@pytest.fixture
def storage(tmp_path, monkeypatch):
    mounted = tmp_path / "private"
    mounted.mkdir()
    image = tmp_path / "image-data"
    (image / "raw").mkdir(parents=True)
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 50), "Synthetic manufacturer product. Warranty seven years.")
        data = pdf.tobytes()
    (image / "raw/product.pdf").write_bytes(data)
    (image / "documents.lock.json").write_text(json.dumps({"documents":{"product.pdf":{
        "url":"https://maker.test/product.pdf","sha256":hashlib.sha256(data).hexdigest()}}}))
    monkeypatch.setattr(settings, "controller_state_dir", mounted)
    monkeypatch.setattr(settings, "campaign_budget_file", mounted / "campaign.sqlite3")
    monkeypatch.setattr(settings, "data_dir", image)
    for name in ("raw_dir", "uploads_dir", "cache_dir", "runs_dir", "scores_file", "evidence_dir"):
        monkeypatch.setattr(settings, name, getattr(settings, name))
    monkeypatch.setattr(settings, "evidence_dir", None)
    monkeypatch.setattr(type(mounted), "is_mount", lambda path: path == mounted)
    monkeypatch.setattr(authority, "filesystem_type", lambda _: "virtiofs")
    monkeypatch.setattr(fetch_docs, "targets", lambda: [("https://maker.test/product.pdf", "product.pdf")])
    return mounted, image, data


def test_storage_seed_preserves_cache_uploads_runs_authority_and_immutable_inputs(storage):
    mounted, image, data = storage
    recorded = settings.recorded_dir
    wallet = mounted / "campaign.sqlite3"
    wallet.write_bytes(b"synthetic authority bytes")
    (mounted / "authority.json").write_bytes(b"synthetic marker bytes")
    controller_startup.prepare()
    paths = (settings.cache_dir / "warm.json", settings.uploads_dir / "saved.pdf", settings.runs_dir / "saved.json")
    for path in paths:
        path.write_bytes(b"retained application data")
    target = settings.raw_dir / "product.pdf"
    timestamp = target.stat().st_mtime_ns
    controller_startup.prepare()
    assert target.read_bytes() == data and target.stat().st_mtime_ns == timestamp
    assert wallet.read_bytes() == b"synthetic authority bytes"
    assert (mounted / "authority.json").read_bytes() == b"synthetic marker bytes"
    assert all(path.read_bytes() == b"retained application data" for path in paths)
    assert settings.data_dir == image and settings.recorded_dir == recorded
    assert settings.uploads_dir == settings.raw_dir / "uploads"
    assert settings.scores_file == settings.runs_dir / "scores.json"


def test_existing_changed_document_is_never_overwritten(storage):
    controller_startup.prepare()
    target = settings.raw_dir / "product.pdf"
    target.write_bytes(b"stored source needs review")
    with pytest.raises(FileExistsError):
        controller_startup.prepare()
    assert target.read_bytes() == b"stored source needs review"


@pytest.mark.parametrize("fault", ["image_hash", "path", "text_layer"])
def test_source_preflight_refuses_changed_unsafe_or_unreadable_documents(storage, fault):
    _, image, _ = storage
    if fault == "image_hash":
        (image / "raw/product.pdf").write_bytes(b"changed source")
    else:
        rows = json.loads((image / "documents.lock.json").read_text())
        if fault == "path":
            rows["documents"]["../outside.pdf"] = rows["documents"].pop("product.pdf")
        else:
            with pymupdf.open() as pdf:
                pdf.new_page()
                data = pdf.tobytes()
            (image / "raw/product.pdf").write_bytes(data)
            rows["documents"]["product.pdf"]["sha256"] = hashlib.sha256(data).hexdigest()
        (image / "documents.lock.json").write_text(json.dumps(rows))
    with pytest.raises(ValueError):
        controller_startup.prepare()


@pytest.mark.parametrize("fault", ["mount", "wallet", "symlink"])
def test_bad_mount_wallet_or_escaping_application_path_cannot_start(storage, monkeypatch, tmp_path, fault):
    mounted, _, _ = storage
    if fault == "mount":
        monkeypatch.setattr(type(mounted), "is_mount", lambda _: False)
    elif fault == "wallet":
        monkeypatch.setattr(settings, "campaign_budget_file", tmp_path / "unrelated.sqlite3")
    else:
        outside = tmp_path / "outside"
        outside.mkdir()
        (mounted / "app").symlink_to(outside, target_is_directory=True)
    with pytest.raises(BudgetExceeded):
        controller_startup.prepare()
    assert not (mounted / "campaign.sqlite3").exists()


def test_missing_authority_allows_read_only_health_and_refuses_fresh_scan(storage, monkeypatch):
    mounted, _, _ = storage
    controller_startup.prepare()
    monkeypatch.setattr(settings, "speccheck_mode", "live")
    with TestClient(app) as client:
        health = client.get("/api/health").json()
        assert health["today"]["blocked"] and health["today"]["accounting_available"] is False
        assert health["budget"] == {"usd_left":0.0,"credits_left":0.0}
        assert client.get("/api/project").status_code == 503  # Watch state needs the imported authority.
        assert client.post("/api/scan", json={"ids":["c01"],"refresh_web":True}).status_code == 429
    assert not (mounted / "campaign.sqlite3").exists() and not (mounted / "authority.json").exists()


def test_serve_refuses_storage_error_without_starting_uvicorn(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(settings, "controller_state_dir", tmp_path)
    def refuse():
        raise ValueError("synthetic-secret-canary")
    monkeypatch.setattr(serve, "prepare", refuse)
    monkeypatch.setattr(serve.uvicorn, "run", lambda *a, **kw: pytest.fail("API must not start"))
    assert serve.main() == 2
    assert "synthetic-secret-canary" not in capsys.readouterr().err


def test_noncontroller_keeps_the_existing_api_command(monkeypatch):
    monkeypatch.setattr(settings, "controller_state_dir", None)
    calls = []
    monkeypatch.setattr(serve.uvicorn, "run", lambda *a, **kw: calls.append((a,kw)))
    assert serve.main() == 0 and calls == [(("api.main:app",),{"host":"0.0.0.0","port":8000})]

import json
from pathlib import Path

import pytest

from api import authority
from api.config import settings
from api.providers import campaign
from api.providers.budget import BudgetExceeded

pytestmark = pytest.mark.campaign


@pytest.fixture
def mount(tmp_path, monkeypatch):
    directory = tmp_path / "controller"
    directory.mkdir()
    monkeypatch.setattr(Path, "is_mount", lambda path: path == directory)
    monkeypatch.setattr(authority, "filesystem_type", lambda _: "virtiofs")
    monkeypatch.setattr(settings, "evidence_dir", None)
    return directory


def test_explicit_cold_import_preserves_actual_money_and_unknown_holds(mount, tmp_path, monkeypatch):
    source = tmp_path / "original.sqlite3"
    campaign.initialize(source, campaign.Amount(usd_nano=100000000, credits=12),
        {"2026-10-21": campaign.Amount(usd_nano=100000000, credits=12)},
        campaign.Amount(usd_nano=20000000000, credits=2000), campaign.Amount(usd_nano=10000000000, credits=1000))
    ticket = campaign.reserve(source, campaign.Amount(usd_nano=200000000, credits=3), run="r", item="i",
        run_usd_nano=3000000000, day_usd_nano=8000000000, item_credits=60, day_credits=600, scopes=[])
    campaign.settle(source, ticket, None)
    marker = authority.install(source, mount)
    assert campaign.status(source)["blocked"]
    with campaign.transaction(source) as old:
        assert old.retired_to == str(mount / "campaign.sqlite3") and ticket in old.payments
    monkeypatch.setattr(settings, "controller_state_dir", mount)
    report = campaign.status(mount / "campaign.sqlite3")
    assert report["total_usd"] == 0.3 and report["total_credits"] == 15 and report["blocked"]
    assert report["held_usd"] == 0.2
    with campaign.transaction(mount / "campaign.sqlite3") as state:
        assert ticket in state.payments and state.campaign_id == marker["campaign_id"]
    with pytest.raises(FileExistsError):
        authority.install(source, mount)


@pytest.mark.parametrize("fault", ["missing-marker", "corrupt-marker", "wrong-identity", "object-mount", "ephemeral", "evidence-mount", "other-vm"])
def test_authority_fails_closed_without_a_private_mounted_identity(mount, tmp_path, monkeypatch, fault):
    source = tmp_path / "source.sqlite3"
    campaign.initialize(source, campaign.Amount(), {}, campaign.Amount(usd_nano=100, credits=10), campaign.Amount())
    authority.install(source, mount)
    monkeypatch.setattr(settings, "controller_state_dir", mount)
    marker = mount / "authority.json"
    if fault == "missing-marker":
        marker.unlink()
    elif fault == "corrupt-marker":
        marker.write_text("broken")
    elif fault == "wrong-identity":
        data = json.loads(marker.read_text()); data["campaign_id"] = "different"; marker.write_text(json.dumps(data))
    elif fault == "object-mount":
        monkeypatch.setattr(authority, "filesystem_type", lambda _: "fuse.s3fs")
    elif fault == "ephemeral":
        monkeypatch.setattr(Path, "is_mount", lambda _: False)
    elif fault == "other-vm":
        monkeypatch.setattr(authority, "writer_id", lambda: "another-VM")
    else:
        monkeypatch.setattr(settings, "evidence_dir", mount)
    with pytest.raises(BudgetExceeded):
        campaign.status(mount / "campaign.sqlite3")
    with pytest.raises(BudgetExceeded):
        campaign.status(source)  # A valid old local file is never a hosted fallback.


def test_retired_source_cannot_initialize_another_volume_at_the_same_path(mount, tmp_path):
    source = tmp_path / "source.sqlite3"
    campaign.initialize(source, campaign.Amount(), {}, campaign.Amount(usd_nano=100, credits=10), campaign.Amount())
    authority.install(source, mount)
    mount.rename(tmp_path / "detached-volume")
    mount.mkdir()
    with pytest.raises(BudgetExceeded, match="already retired"):
        authority.install(source, mount)
    assert not list(mount.iterdir())

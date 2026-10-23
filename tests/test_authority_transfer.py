from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import uuid

import pytest

from api import authority, authority_transfer as transfer
from api.config import settings
from api.providers import campaign
from api.providers.budget import BudgetExceeded

pytestmark = pytest.mark.campaign


def reserve(path):
    return campaign.reserve(path, campaign.Amount(usd_nano=200000000, credits=3), run="run", item="item",
        run_usd_nano=3000000000, day_usd_nano=8000000000, item_credits=60, day_credits=600, scopes=[])


@pytest.fixture
def handoff(tmp_path, monkeypatch):
    mount = tmp_path / "private-mount"
    mount.mkdir()
    monkeypatch.setattr(Path, "is_mount", lambda path: path == mount)
    monkeypatch.setattr(authority, "filesystem_type", lambda _: "virtiofs")
    monkeypatch.setattr(settings, "controller_state_dir", None)
    monkeypatch.setattr(settings, "evidence_dir", None)
    boot = {"id": "destination-boot"}
    monkeypatch.setattr(authority, "writer_id", lambda: boot["id"])
    source = tmp_path / "source.sqlite3"
    campaign.initialize(source, campaign.Amount(usd_nano=100000000, credits=12),
        {"2026-10-21": campaign.Amount(usd_nano=100000000, credits=12)},
        campaign.Amount(usd_nano=20000000000, credits=2000), campaign.Amount(usd_nano=10000000000, credits=1000))
    ticket = reserve(source)
    campaign.settle(source, ticket, campaign.Amount(usd_nano=50000000, credits=2))
    request = transfer.prepare(mount, "synthetic-old-endpoint")
    return SimpleNamespace(source=source, mount=mount, boot=boot, request=request,
                           bundle=tmp_path / "private-export.json", target=mount / "campaign.sqlite3")


def send(h):
    return transfer.export(h.source, h.mount / "handoff.json", h.bundle, h.request["sha256"])


def activate(h):
    receipt = send(h)
    return transfer.receive(h.bundle, h.mount, receipt["sha256"])


def approval(h, tmp_path):
    marker = json.loads((h.mount / "authority.json").read_text())
    stamp = datetime.now(timezone.utc).isoformat()
    value = {"version":1, "approved_by":"Kyle", "state":"STOPPED", "campaign_id":marker["campaign_id"],
        "authority_sha256":transfer.digest((h.mount / "authority.json").read_bytes()),
        "previous_resource_id":marker["resource_id"], "resource_id":"synthetic-new-endpoint",
        "previous_writer_id":marker["writer_id"], "writer_id":"replacement-boot", "observed_at":stamp, "approved_at":stamp}
    path = tmp_path / "synthetic-owner-approval.json"
    path.write_bytes(transfer.encoded(value))
    return path, value


def test_handoff_preserves_every_charge_allocation_and_unknown_hold(handoff):
    h = handoff
    unknown = reserve(h.source)
    campaign.settle(h.source, unknown, None)
    before = campaign.status(h.source)
    receipt = send(h)
    assert send(h) == receipt  # Exact retry after source retirement.
    marker = transfer.receive(h.bundle, h.mount, receipt["sha256"])
    after = campaign.status(h.target)
    assert {key:after[key] for key in before} == {**before, "blocked":True}
    assert after["total_usd"] == .35 and after["total_credits"] == 17 and after["held_usd"] == .2
    assert marker["resource_id"] == "synthetic-old-endpoint"
    for path in (h.bundle, h.target, h.mount / "authority.json", h.mount / "handoff.json"):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    for path in (h.source, h.target):
        with pytest.raises(BudgetExceeded):
            reserve(path)
    with pytest.raises(BudgetExceeded, match="read-only"):
        campaign.settle(h.source, unknown, campaign.Amount(usd_nano=100000000, credits=1))
    assert send(h) == receipt  # Late rejected settlement cannot prevent recovering the exact snapshot.
    with campaign.transaction(h.target) as state:
        assert unknown in state.payments and state.payments[unknown].actual is None
        assert state.campaign_id == marker["campaign_id"]


def test_active_request_prevents_export_without_retiring_source(handoff):
    h = handoff
    ticket = reserve(h.source)
    with pytest.raises(BudgetExceeded, match="Quiesce"):
        send(h)
    assert not h.bundle.exists() and not campaign.status(h.source)["blocked"]
    campaign.settle(h.source, ticket, campaign.Amount(usd_nano=1))
    assert send(h)["source_retired"]


@pytest.mark.parametrize("fault", ["wrong-hash", "different-boot", "different-request", "object-mount"])
def test_wrong_destination_or_artifact_cannot_activate(handoff, monkeypatch, fault):
    h = handoff
    receipt = send(h)
    if fault == "wrong-hash":
        receipt["sha256"] = "0" * 64
    elif fault == "different-boot":
        h.boot["id"] = "unapproved-boot"
    elif fault == "different-request":
        request = json.loads((h.mount / "handoff.json").read_text())
        request["nonce"] = "f" * 32
        (h.mount / "handoff.json").write_bytes(transfer.encoded(request))
    else:
        monkeypatch.setattr(authority, "filesystem_type", lambda _: "fuse.s3fs")
    with pytest.raises((ValueError, BudgetExceeded)):
        transfer.receive(h.bundle, h.mount, receipt["sha256"])
    assert not h.target.exists() and not (h.mount / "authority.json").exists()


def test_interrupted_export_recovers_only_its_exact_fenced_snapshot(handoff, monkeypatch):
    h, original = handoff, transfer.publish
    def broken(path, data):
        if path == h.bundle:
            raise OSError("synthetic disk interruption")
        original(path, data)
    monkeypatch.setattr(transfer, "publish", broken)
    with pytest.raises(OSError):
        send(h)
    assert not h.bundle.exists() and campaign.status(h.source)["blocked"]
    monkeypatch.setattr(transfer, "publish", original)
    receipt = send(h)
    other_request = json.loads((h.mount / "handoff.json").read_text())
    other_request["nonce"] = "e" * 32
    other = h.bundle.parent / "another-request.json"
    other.write_bytes(transfer.encoded(other_request))
    with pytest.raises(BudgetExceeded, match="different transfer"):
        transfer.export(h.source, other, h.bundle.parent / "other-export.json", transfer.digest(other.read_bytes()))
    assert transfer.receive(h.bundle, h.mount, receipt["sha256"])["campaign_id"]


@pytest.mark.parametrize("changed", [False, True])
def test_interrupted_receive_resumes_without_overwriting_a_changed_wallet(handoff, monkeypatch, changed):
    h, original = handoff, transfer.publish
    receipt = send(h)
    def broken(path, data):
        if path.name == "authority.json":
            raise OSError("synthetic failure before activation")
        original(path, data)
    monkeypatch.setattr(transfer, "publish", broken)
    with pytest.raises(OSError):
        transfer.receive(h.bundle, h.mount, receipt["sha256"])
    assert h.target.exists() and not (h.mount / "authority.json").exists()
    if changed:
        with campaign.transaction(h.target) as state:
            state.blocked = True
    monkeypatch.setattr(settings, "controller_state_dir", h.mount)
    with pytest.raises(BudgetExceeded):
        campaign.status(h.target)
    monkeypatch.setattr(transfer, "publish", original)
    if changed:
        with pytest.raises(BudgetExceeded, match="Interrupted import differs"):
            transfer.receive(h.bundle, h.mount, receipt["sha256"])
        assert not (h.mount / "authority.json").exists()
        return
    transfer.receive(h.bundle, h.mount, receipt["sha256"])
    ticket = reserve(h.target)
    campaign.settle(h.target, ticket, campaign.Amount(usd_nano=25000000, credits=1))
    assert transfer.receive(h.bundle, h.mount, receipt["sha256"])["campaign_id"]
    assert campaign.status(h.target)["total_usd"] == .175  # Retry never resets later actual spend.


def test_retired_source_is_read_only_even_for_direct_transaction_callers(handoff):
    h = handoff
    send(h)
    with pytest.raises(BudgetExceeded, match="read-only"):
        with campaign.transaction(h.source) as state:
            state.retired_to = None
    assert campaign.status(h.source)["blocked"]


def test_writer_identity_is_rechecked_after_acquiring_the_sqlite_lock(handoff, monkeypatch):
    h = handoff
    activate(h)
    monkeypatch.setattr(settings, "controller_state_dir", h.mount)
    original, calls = authority.verify, []
    def changed(path, directory):
        original(path, directory)
        calls.append(1)
        if len(calls) == 1:
            h.boot["id"] = "unexpected-boot"
    monkeypatch.setattr(authority, "verify", changed)
    with pytest.raises(BudgetExceeded, match="does not own"):
        reserve(h.target)
    assert len(calls) == 1  # The second verification rejects before admitting any payment.


def test_explicit_cutover_preserves_money_fences_old_boot_and_rejects_old_import(handoff, tmp_path, monkeypatch):
    h = handoff
    activate(h)
    proof, _ = approval(h, tmp_path)
    h.boot["id"] = "replacement-boot"
    monkeypatch.setattr(settings, "controller_state_dir", h.mount)
    with pytest.raises(BudgetExceeded):
        campaign.status(h.target)
    marker = transfer.cutover(h.mount, proof, transfer.digest(proof.read_bytes()))
    assert transfer.cutover(h.mount, proof, transfer.digest(proof.read_bytes())) == marker
    assert campaign.status(h.target)["total_usd"] == .15
    assert campaign.status(h.target)["total_credits"] == 14
    h.boot["id"] = "destination-boot"
    with pytest.raises(BudgetExceeded):
        campaign.status(h.target)
    h.boot["id"] = "replacement-boot"
    with pytest.raises(BudgetExceeded):
        transfer.receive(h.bundle, h.mount, transfer.digest(h.bundle.read_bytes()))


@pytest.mark.parametrize("fault", ["unapproved", "running", "wrong-campaign", "wrong-host", "stale", "naive-time"])
def test_cutover_requires_recent_exact_owner_evidence(handoff, tmp_path, fault):
    h = handoff
    activate(h)
    path, value = approval(h, tmp_path)
    h.boot["id"] = "replacement-boot"
    if fault == "unapproved": value["approved_by"] = "agent"
    elif fault == "running": value["state"] = "RUNNING"
    elif fault == "wrong-campaign": value["campaign_id"] = "f" * 32
    elif fault == "wrong-host": value["previous_resource_id"] = "unrelated-endpoint"
    elif fault == "stale": value["observed_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    else: value["observed_at"] = datetime.now().isoformat()
    path.write_bytes(transfer.encoded(value))
    before = (h.mount / "authority.json").read_bytes()
    with pytest.raises((BudgetExceeded, ValueError)):
        transfer.cutover(h.mount, path, transfer.digest(path.read_bytes()))
    assert (h.mount / "authority.json").read_bytes() == before


def test_cli_redacts_invalid_artifact_bodies(handoff, monkeypatch, capsys):
    from scripts.transfer_authority import main
    h = handoff
    canary = "synthetic-private-credential-must-not-print"
    h.bundle.write_text(json.dumps({"unrecognized_secret":canary}))
    monkeypatch.setattr(sys, "argv", ["transfer_authority.py", "receive", str(h.bundle), str(h.mount),
                                      "--sha256", transfer.digest(h.bundle.read_bytes())])
    with pytest.raises(SystemExit) as error:
        main()
    output = capsys.readouterr()
    assert error.value.code == 2 and canary not in output.out + output.err
    assert not h.target.exists()


def job_receipt(h, *, settled=True):
    body, identifier = b'{"synthetic_private_receipt":true}', uuid.uuid4().hex
    relative = f"reports/{identifier}/{'a' * 64}.json"
    path = h.source.parent / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(body)
    with campaign.transaction(h.source) as state:
        payment = campaign._reserve(state, campaign.Amount(usd_nano=100000000, credits=3), run="job", item="allowance",
            run_usd_nano=3000000000, day_usd_nano=8000000000, item_credits=60, day_credits=600, scopes=[])
        state.payments[payment].kind = "job"
        if settled:
            state.payments[payment].actual = campaign.Amount(usd_nano=30000000, credits=1)
        state.jobs[identifier] = campaign.JobLease(lease_id=identifier, request_id="synthetic", name="job",
            created_at=datetime.now(timezone.utc).isoformat(), payment_id=payment, phase=state.phase,
            allowance=campaign.Amount(usd_nano=100000000, credits=3), ids=["c01"], image="synthetic", manifest={},
            settled=settled, report_path=relative, report_hash="a" * 64, report_digest=transfer.digest(body))
    return relative, body


def test_private_job_receipts_and_full_history_survive_transfer(handoff):
    h = handoff
    relative, body = job_receipt(h)
    activate(h)
    assert (h.mount / relative).read_bytes() == body
    assert campaign.status(h.target)["total_usd"] == .18
    with campaign.transaction(h.target) as state:
        assert len(state.jobs) == 1 and len(state.payments) == 2


@pytest.mark.parametrize("fault", ["unsettled-job", "missing-receipt", "corrupt-receipt"])
def test_unsettled_or_unverifiable_job_blocks_export_before_retirement(handoff, fault):
    h = handoff
    relative, _ = job_receipt(h, settled=fault != "unsettled-job")
    if fault == "missing-receipt": (h.source.parent / relative).unlink()
    elif fault == "corrupt-receipt": (h.source.parent / relative).write_bytes(b'corrupt')
    with pytest.raises((BudgetExceeded, ValueError, OSError)):
        send(h)
    with campaign.transaction(h.source) as state:
        assert state.retired_to is None
    assert not h.bundle.exists()


@pytest.mark.parametrize("wrong_transfer", [False, True])
def test_destination_reboot_before_import_needs_bound_approval_and_retains_original_snapshot(handoff, tmp_path, wrong_transfer):
    h = handoff
    receipt = send(h)
    original_bundle = h.bundle.read_bytes()
    original_request = (h.mount / "handoff.json").read_bytes()
    stamp = datetime.now(timezone.utc).isoformat()
    value = {"version":1, "approved_by":"Kyle", "state":"STOPPED", "campaign_id":receipt["campaign_id"],
        "authority_sha256":transfer.digest(original_request), "transfer_sha256":receipt["sha256"],
        "previous_resource_id":"synthetic-old-endpoint", "resource_id":"synthetic-recovery-endpoint",
        "previous_writer_id":"destination-boot", "writer_id":"recovery-boot", "observed_at":stamp, "approved_at":stamp}
    if wrong_transfer:
        value["transfer_sha256"] = "f" * 64
    proof = tmp_path / "synthetic-recovery.json"
    proof.write_bytes(transfer.encoded(value))
    h.boot["id"] = "recovery-boot"
    with pytest.raises(BudgetExceeded, match="reboot"):
        transfer.receive(h.bundle, h.mount, receipt["sha256"])
    if wrong_transfer:
        with pytest.raises(BudgetExceeded, match="exact prepared transfer"):
            transfer.receive(h.bundle, h.mount, receipt["sha256"], proof_file=proof,
                              proof_sha256=transfer.digest(proof.read_bytes()))
        assert not h.target.exists()
        return
    marker = transfer.receive(h.bundle, h.mount, receipt["sha256"], proof_file=proof,
                              proof_sha256=transfer.digest(proof.read_bytes()))
    assert marker["writer_id"] == "recovery-boot" and campaign.status(h.target)["total_usd"] == .15
    assert h.bundle.read_bytes() == original_bundle and (h.mount / "handoff.json").read_bytes() == original_request
    assert (h.mount / f"cutovers/{marker['cutover_sha256']}.json").read_bytes() == proof.read_bytes()


@pytest.mark.parametrize("stage", ["receive", "cutover"])
def test_activation_fsync_failure_can_retry_without_reset(handoff, tmp_path, monkeypatch, stage):
    h = handoff
    receipt = send(h)
    original = authority.sync_directory
    if stage == "cutover":
        transfer.receive(h.bundle, h.mount, receipt["sha256"])
        proof, _ = approval(h, tmp_path)
        h.boot["id"] = "replacement-boot"
    def broken(directory):
        marker = h.mount / "authority.json"
        if directory == h.mount and marker.exists() and (stage == "receive" or json.loads(marker.read_text()).get("cutover_sha256")):
            raise OSError("synthetic sync failure after activation")
        original(directory)
    monkeypatch.setattr(authority, "sync_directory", broken)
    def apply():
        return (transfer.receive(h.bundle, h.mount, receipt["sha256"]) if stage == "receive" else
                transfer.cutover(h.mount, proof, transfer.digest(proof.read_bytes())))
    with pytest.raises(OSError): apply()
    monkeypatch.setattr(authority, "sync_directory", original)
    apply()
    assert campaign.status(h.target)["total_usd"] == .15


def test_fenced_export_can_be_recovered_read_only_after_source_boot_loss(handoff, monkeypatch):
    h = handoff
    receipt = send(h)
    monkeypatch.setattr(settings, "controller_state_dir", h.source.parent)
    monkeypatch.setattr(authority, "verify", lambda *args: pytest.fail("Fenced read-only recovery must not reactivate a source"))
    assert send(h) == receipt

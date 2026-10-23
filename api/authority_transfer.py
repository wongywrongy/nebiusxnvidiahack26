"""Explicit private-wallet handoff. No transport, cloud mutations, reseeding or automatic cutover."""

import base64
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from . import authority
from .config import settings
from .providers import campaign
from .providers.budget import BudgetExceeded


class Destination(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    version: Literal[1] = 1
    nonce: str = Field(pattern=r"^[0-9a-f]{32}$")
    directory: str
    writer_id: str = Field(min_length=1, max_length=128)
    resource_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")


class Transfer(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    version: Literal[1] = 1
    destination: Destination
    wallet: campaign.State
    reports: dict[str, str] = {}


class CutoverApproval(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    version: Literal[1] = 1
    approved_by: Literal["Kyle"]
    state: Literal["STOPPED"]
    campaign_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    authority_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    transfer_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    previous_resource_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    resource_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    previous_writer_id: str = Field(min_length=1, max_length=128)
    writer_id: str = Field(min_length=1, max_length=128)
    observed_at: str
    approved_at: str


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def checked(path: Path, sha256: str) -> bytes:
    data = path.read_bytes()
    if len(sha256) != 64 or digest(data) != sha256:
        raise ValueError("Private artifact differs from the explicitly pinned hash")
    return data


def publish(path: Path, data: bytes) -> None:
    """Atomic, durable, no-overwrite publication; retries may reuse identical bytes only."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".handoff-", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise FileExistsError("Existing private artifact differs; no overwrite allowed")
        authority.sync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def locked(directory: Path):
    with (directory / "handoff.json").open("rb") as request:
        fcntl.flock(request, fcntl.LOCK_EX)
        yield Destination.model_validate_json(request.read())


def prepare(directory: Path, resource_id: str) -> dict:
    authority.location(directory)
    if (directory / "campaign.sqlite3").exists() or (directory / "authority.json").exists():
        raise FileExistsError("Prepare requires an empty authority; never replace an existing wallet")
    path = directory / "handoff.json"
    request = Destination(version=1, nonce=uuid.uuid4().hex, directory=str(directory.resolve()),
                          writer_id=authority.writer_id(), resource_id=resource_id)
    if path.exists():
        request = Destination.model_validate_json(path.read_bytes())
    if (request.directory, request.writer_id, request.resource_id) != (str(directory.resolve()), authority.writer_id(), resource_id):
        raise BudgetExceeded("Prepared destination belongs to another boot, mount or resource")
    publish(path, encoded(request.model_dump()))
    return {"sha256": digest(path.read_bytes()), "resource_id": resource_id, "writer_id": request.writer_id}


def export(source: Path, request_file: Path, output: Path, sha256: str) -> dict:
    request = Destination.model_validate_json(checked(request_file, sha256))
    if not Path(request.directory).is_absolute() or not request.writer_id:
        raise ValueError("Destination must identify its absolute mount and VM boot")
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=rw", uri=True)) as connection, connection:
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        state = campaign.State.model_validate_json(connection.execute("SELECT data FROM campaign WHERE id=1").fetchone()[0])
        campaign._validate(state)
        if any(not job.settled for job in state.jobs.values()) or any(p.actual is None and not p.unknown for p in state.payments.values()):
            raise BudgetExceeded("Quiesce active requests and settle jobs before handoff")
        if not state.retired_to and any(path == str(source.resolve()) for path, _ in campaign.FAILED_SETTLEMENTS):
            raise BudgetExceeded("Failed settlement requires reconciliation before handoff")
        retired_to = state.retired_to
        state.retired_to = None
        state.blocked |= any(p.actual is None for p in state.payments.values())
        reports = {}
        for job in state.jobs.values():
            if job.report_path:
                path = (source.parent / job.report_path).resolve()
                if not path.is_relative_to(source.parent.resolve()):
                    raise ValueError("Worker receipt escapes its private authority")
                reports[job.report_path] = base64.b64encode(checked(path, job.report_digest)).decode()
        data = encoded(Transfer(destination=request, wallet=state, reports=reports).model_dump())
        identifier = digest(data)
        if retired_to not in (None, "handoff:" + identifier):
            raise BudgetExceeded("Source was retired by a different transfer; reconcile before proceeding")
        if retired_to is None and (settings.controller_state_dir or (source.parent / "authority.json").exists()):
            authority.verify(source, settings.controller_state_dir or source.parent)
        if output.exists() and output.read_bytes() != data:
            raise FileExistsError("Export path already contains a different artifact")
        state.retired_to = "handoff:" + identifier
        connection.execute("UPDATE campaign SET data=? WHERE id=1", (state.model_dump_json(),))
    # The source is durably fenced before a transferable snapshot becomes available.
    publish(output, data)
    return {"sha256": identifier, "campaign_id": state.campaign_id, "source_retired": True}


def approved(proof_file: Path, sha256: str) -> dict:
    proof = CutoverApproval.model_validate_json(checked(proof_file, sha256)).model_dump()
    now = datetime.now(timezone.utc)
    observed, approval = (datetime.fromisoformat(proof[key]) for key in ("observed_at", "approved_at"))
    if (observed.tzinfo is None or approval.tzinfo is None or not observed <= approval <= now
            or (now - observed).total_seconds() > 3600 or proof["writer_id"] != authority.writer_id()):
        raise BudgetExceeded("Cutover needs recent explicit owner approval of the stopped previous controller")
    return proof


def receive(bundle: Path, directory: Path, sha256: str, *, proof_file: Path | None = None,
            proof_sha256: str | None = None) -> dict:
    authority.location(directory)
    transfer = Transfer.model_validate_json(checked(bundle, sha256))
    campaign._validate(transfer.wallet)
    if (transfer.wallet.retired_to or any(not job.settled for job in transfer.wallet.jobs.values())
            or any(p.actual is None and not p.unknown for p in transfer.wallet.payments.values())):
        raise ValueError("Transfer is not a quiescent authority snapshot")
    if any(p.actual is None for p in transfer.wallet.payments.values()) and not transfer.wallet.blocked:
        raise ValueError("Unknown transferred usage must retain an accounting block")
    expected_reports = {job.report_path: job.report_digest for job in transfer.wallet.jobs.values() if job.report_path}
    if set(expected_reports) != set(transfer.reports):
        raise ValueError("Transfer must preserve every private worker receipt")
    receipts = {name: base64.b64decode(body, validate=True) for name, body in transfer.reports.items()}
    if any(digest(body) != expected_reports[name] for name, body in receipts.items()):
        raise ValueError("Transferred worker receipt is corrupt")
    with locked(directory) as request:
        if transfer.destination != request or request.directory != str(directory.resolve()):
            raise BudgetExceeded("Transfer targets another prepared mount or VM boot")
        marker = {"version": 1, "campaign_id": transfer.wallet.campaign_id, "writer_id": request.writer_id,
                  "source_sha256": digest(encoded(transfer.wallet.model_dump())), "transfer_sha256": sha256,
                  "resource_id": request.resource_id}
        if request.writer_id != authority.writer_id():
            if not proof_file or not proof_sha256:
                raise BudgetExceeded("Destination reboot requires explicit stopped-host approval")
            proof = approved(proof_file, proof_sha256)
            if (proof["campaign_id"] != marker["campaign_id"] or proof["transfer_sha256"] != sha256
                    or proof["authority_sha256"] != digest((directory / "handoff.json").read_bytes())
                    or proof["previous_resource_id"] != request.resource_id or proof["previous_writer_id"] != request.writer_id):
                raise BudgetExceeded("Recovery approval does not bind this exact prepared transfer")
            marker.update(writer_id=proof["writer_id"], resource_id=proof["resource_id"], cutover_sha256=proof_sha256)
            publish(directory / f"cutovers/{proof_sha256}.json", checked(proof_file, proof_sha256))
        target = directory / "campaign.sqlite3"
        if (directory / "authority.json").exists():
            if json.loads((directory / "authority.json").read_text()) != marker:
                raise BudgetExceeded("Existing authority differs; import cannot replace or reactivate it")
            authority.verify(target, directory)
            with campaign.transaction(target) as current:
                if current.campaign_id != marker["campaign_id"] or current.retired_to:
                    raise BudgetExceeded("Imported authority was changed or retired")
            authority.sync_directory(directory)
            return marker
        for name, body in receipts.items():
            publish(directory / name, body)
        if target.exists():
            with closing(sqlite3.connect(target.resolve().as_uri() + "?mode=rw", uri=True)) as connection, connection:
                current = campaign.State.model_validate_json(connection.execute("SELECT data FROM campaign WHERE id=1").fetchone()[0])
            if current != transfer.wallet:
                raise BudgetExceeded("Interrupted import differs; no reset or overwrite allowed")
        else:
            fd, name = tempfile.mkstemp(prefix=".wallet-", dir=directory)
            os.close(fd)
            temp = Path(name)
            try:
                with closing(sqlite3.connect(temp)) as connection, connection:
                    connection.execute("PRAGMA synchronous=FULL")
                    connection.execute("CREATE TABLE campaign (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
                    connection.execute("INSERT INTO campaign VALUES (1, ?)", (transfer.wallet.model_dump_json(),))
                publish(target, temp.read_bytes())
            finally:
                temp.unlink(missing_ok=True)
        publish(directory / "authority.json", encoded(marker))
        return marker


def cutover(directory: Path, proof_file: Path, sha256: str) -> dict:
    """Operator-approved boot replacement; the operator must authenticate the stopped-host observation."""
    authority.location(directory)
    proof = approved(proof_file, sha256)
    with locked(directory):
        target, marker_file = directory / "campaign.sqlite3", directory / "authority.json"
        marker = json.loads(marker_file.read_text())
        if (marker.get("cutover_sha256") == sha256 and marker["writer_id"] == proof["writer_id"]
                and marker["resource_id"] == proof["resource_id"] and marker["campaign_id"] == proof["campaign_id"]):
            authority.verify(target, directory)
            with campaign.transaction(target) as state:
                if state.campaign_id != marker["campaign_id"] or state.retired_to:
                    raise BudgetExceeded("Cutover authority was changed or retired")
            authority.sync_directory(directory)
            return marker
        with closing(sqlite3.connect(target.resolve().as_uri() + "?mode=rw", uri=True)) as connection, connection:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            marker = json.loads(checked(marker_file, proof["authority_sha256"]))
            if (marker.get("resource_id") != proof["previous_resource_id"] or marker["writer_id"] != proof["previous_writer_id"]
                    or marker["writer_id"] == proof["writer_id"] or marker["campaign_id"] != proof["campaign_id"]):
                raise BudgetExceeded("Cutover proof does not bind the previous authority")
            state = campaign.State.model_validate_json(connection.execute("SELECT data FROM campaign WHERE id=1").fetchone()[0])
            campaign._validate(state)
            if state.campaign_id != marker["campaign_id"] or state.retired_to or any(not j.settled for j in state.jobs.values()):
                raise BudgetExceeded("Retired authority or unsettled job requires reconciliation before cutover")
            state.blocked |= any(p.actual is None for p in state.payments.values())
            connection.execute("UPDATE campaign SET data=? WHERE id=1", (state.model_dump_json(),))
            marker.update(writer_id=proof["writer_id"], resource_id=proof["resource_id"], cutover_sha256=sha256)
        publish(directory / f"cutovers/{sha256}.json", checked(proof_file, sha256))
        fd, name = tempfile.mkstemp(prefix=".authority-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(encoded(marker)); output.flush(); os.fsync(output.fileno())
            os.replace(name, marker_file)
            authority.sync_directory(directory)
        finally:
            Path(name).unlink(missing_ok=True)
        return marker

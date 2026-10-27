"""Controller-only POSIX accounting storage. Object mounts and silent fallback are forbidden."""

import hashlib
import json
import os
from pathlib import Path
import sqlite3

from .config import settings
from .providers.budget import BudgetExceeded


def writer_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def filesystem_type(directory: Path) -> str:
    mounts = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        mount = Path(left.split()[4].replace(r"\040", " "))
        if directory.resolve().is_relative_to(mount):
            mounts.append((len(mount.parts), right.split()[0]))
    return max(mounts)[1] if mounts else "unknown"


def location(directory: Path) -> None:
    if (not directory.is_mount() or filesystem_type(directory) not in ("virtiofs", "ext4", "xfs")
            or settings.evidence_dir and directory.resolve().is_relative_to(settings.evidence_dir.resolve())):
        raise BudgetExceeded("Controller accounting requires its own mounted POSIX filesystem; no object/evidence mount")


def verify(path: Path, directory: Path) -> None:
    location(directory)
    if path.resolve() != directory.resolve() / "campaign.sqlite3":
        raise BudgetExceeded("Controller accounting path must match its private persistent mount")
    marker = json.loads((directory / "authority.json").read_text())
    if marker.get("version") != 1 or not marker.get("campaign_id") or not marker.get("source_sha256"):
        raise BudgetExceeded("Controller authority identity is missing or invalid")
    if marker.get("writer_id") != writer_id():
        raise BudgetExceeded("This VM does not own the controller authority; approved writer cutover required")


def verify_identity(campaign_id: str, directory: Path) -> None:
    if json.loads((directory / "authority.json").read_text())["campaign_id"] != campaign_id:
        raise BudgetExceeded("Controller campaign identity does not match the imported authority")


def install(source: Path, directory: Path) -> dict:
    """Explicit cold import preserves all actual charges/holds; never reseeds a wallet."""
    from .providers import campaign

    location(directory)
    target = directory / "campaign.sqlite3"
    marker = directory / "authority.json"
    if target.exists() or marker.exists():
        raise FileExistsError("Controller authority already exists; it cannot be reset or overwritten")
    with sqlite3.connect(source.resolve().as_uri() + "?mode=rw", uri=True) as connection:
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        raw = connection.execute("SELECT data FROM campaign WHERE id=1").fetchone()[0]
        state = campaign.State.model_validate_json(raw)
        campaign._validate(state)
        if state.retired_to:
            raise BudgetExceeded("Source authority is already retired; explicit reconciliation required")
        # Fence the old writer before activating a new copy, including across a crash.
        state.retired_to = str(target.resolve())
        connection.execute("UPDATE campaign SET data=? WHERE id=1", (state.model_dump_json(),))
    state.retired_to = None
    state.blocked |= any(payment.actual is None and payment.kind == "request" for payment in state.payments.values())
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with sqlite3.connect(target) as connection:
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("CREATE TABLE campaign (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
        connection.execute("INSERT INTO campaign VALUES (1, ?)", (state.model_dump_json(),))
    data = {"version": 1, "campaign_id": state.campaign_id, "writer_id": writer_id(),
            "source_sha256": hashlib.sha256(raw.encode()).hexdigest()}
    fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(data, output)
        output.flush()
        os.fsync(output.fileno())
    sync_directory(directory)
    return data


def sync_directory(directory: Path) -> None:
    directory_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)

"""Prepare persistent application paths without creating or importing an accounting authority."""

import json

from . import authority
from .authority_transfer import digest, publish
from .config import settings
from .providers.budget import BudgetExceeded
from scripts.check_pdfs import required_documents


def prepare() -> None:
    directory = settings.controller_state_dir
    if directory is None:
        raise BudgetExceeded("Controller state needs its private mounted filesystem")
    authority.location(directory)
    if settings.campaign_budget_file.resolve() != directory.resolve() / "campaign.sqlite3":
        raise BudgetExceeded("Controller wallet must remain at the private mount root")
    source = settings.data_dir / "raw"
    paths = {"raw_dir": directory / "app/raw", "uploads_dir": directory / "app/raw/uploads",
             "cache_dir": directory / "app/cache", "runs_dir": directory / "app/runs",
             "scores_file": directory / "app/runs/scores.json", "evidence_dir": directory / "app/evidence"}
    if any(not path.resolve().is_relative_to(directory.resolve()) for path in paths.values()):
        raise BudgetExceeded("Controller application paths must stay on the private mount")
    for name, path in paths.items():
        setattr(settings, name, path)
        if name != "scores_file":
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
    locked = json.loads((settings.data_dir / "documents.lock.json").read_text())["documents"]
    for relative, expected in locked.items():
        original, target = source / relative, settings.raw_dir / relative
        if (not original.resolve().is_relative_to(source.resolve())
                or not target.resolve().is_relative_to(settings.raw_dir.resolve())):
            raise ValueError("Locked document path leaves its data directory")
        data = original.read_bytes()
        if digest(data) != expected["sha256"]:
            raise ValueError("Bundled document differs from its reviewed lock")
        publish(target, data)
    manifest = settings.raw_dir / "manifest.json"
    if manifest.exists():
        existing = json.loads(manifest.read_text())
        if any(existing.get(name, {}).get("sha256") != row["sha256"] for name, row in locked.items()):
            raise ValueError("Stored document manifest differs; no replacement or reset allowed")
    else:
        publish(manifest, json.dumps(locked, sort_keys=True).encode())
    if not required_documents()["passed"]:
        raise ValueError("Persistent required documents failed their release checks")

"""One drafting path for the public preview and the owner's review script."""

from datetime import datetime, timedelta, timezone
import json
import re
import uuid

from fastapi import HTTPException

from ..config import settings
from ..llm import load_spec_fixture
from ..schemas import Checklist, UploadChecklist
from .cases import all_specs
from .extract import checklist_path, extract_requirements


def save_upload(checklist: UploadChecklist) -> dict:
    identifier = f"ck-{uuid.uuid4().hex}"
    folder = settings.uploads_dir / "checklists"
    folder.mkdir(parents=True, exist_ok=True)
    # Public checklists never acquire reviewed status or write the project's requirements.
    checklist.reviewed_at = None
    path = folder / f"{identifier}.json"
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(),
                                "checklist": checklist.model_dump(mode="json")}))
    temp.replace(path)
    return {"id": identifier, "section": checklist.section, "title": checklist.title,
            "n": len(checklist.requirements)}


def load_upload(identifier: str) -> UploadChecklist:
    if re.fullmatch(r"ck-[0-9a-f]{32}", identifier):
        path = settings.uploads_dir / "checklists" / f"{identifier}.json"
        if path.is_file():
            data = json.loads(path.read_text())
            if datetime.fromisoformat(data["created_at"]) > datetime.now(timezone.utc) - timedelta(days=14):
                return UploadChecklist.model_validate(data["checklist"])
    raise HTTPException(404, "This draft checklist has expired or is missing. Draft and save it again in Specs.")


def prune_uploads():
    for path in (settings.uploads_dir / "checklists").glob("ck-*.json"):
        data = json.loads(path.read_text())
        if datetime.fromisoformat(data["created_at"]) <= datetime.now(timezone.utc) - timedelta(days=14):
            path.unlink()


async def draft(section: str, text: str, source_name: str, source_url: str | None = None,
                source_sha256: str | None = None, title: str = ""):
    out, usage = await extract_requirements(section, text, title=title)
    return Checklist(**out.model_dump(), section=section, title=title, drafted_by=usage.model, source_name=source_name, source_url=source_url,
                     source_sha256=source_sha256, drafted_at=datetime.now(timezone.utc)), usage


def sections() -> list[dict]:
    out = []
    for section, spec in all_specs().items():
        path = checklist_path(section)
        reviewed = path.exists()
        data = json.loads(path.read_text()) if reviewed else load_spec_fixture(section)
        checklist = Checklist.model_validate(data)
        out.append({"section": section, "title": spec["title"], "owner": spec["owner"],
                    "control_version": spec["version"], "source_url": spec["url"],
                    "checklist": checklist.model_dump(mode="json"),
                    "status": ("reviewed" if checklist.reviewed_at else "saved") if reviewed else "fixture",
                    "note": data.get("_note", ""),
                    "used_by_scans": "live" if reviewed else "mock"})
    return out

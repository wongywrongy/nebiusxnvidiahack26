"""One drafting path for the public preview and the owner's review script."""

from datetime import datetime, timezone
import json

from ..llm import load_spec_fixture
from ..schemas import Checklist
from .cases import all_specs
from .extract import checklist_path, extract_requirements


async def draft(section: str, text: str, source_name: str, source_url: str | None = None,
                source_sha256: str | None = None):
    out, usage = await extract_requirements(section, text)
    return Checklist(**out.model_dump(), drafted_by=usage.model, source_name=source_name, source_url=source_url,
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

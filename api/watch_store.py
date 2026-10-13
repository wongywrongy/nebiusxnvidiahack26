"""Watch state survives container replacement when an evidence bucket is mounted."""

import json
import tempfile
from pathlib import Path

from .config import settings


def folders():
    return ([settings.evidence_dir / "watch"] if settings.evidence_dir else []) + [settings.runs_dir / "watch"]


def read(name: str, default=None):
    for folder in folders():
        try:
            return json.loads((folder / name).read_text())
        except (OSError, ValueError):
            continue
    return default


def write(name: str, data) -> None:
    text = json.dumps(data, indent=2)
    for folder in folders():
        folder.mkdir(parents=True, exist_ok=True)
        # Unique temporary names avoid collisions between the reporting job and endpoint.
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=folder, suffix=".tmp", delete=False) as f:
                temp = Path(f.name)
                f.write(text)
            temp.replace(folder / name)
        finally:
            if temp:
                temp.unlink(missing_ok=True)


def report(data: dict) -> None:
    write("latest.json", data)
    write(f"{data['checked_at'][:10]}.json", data)

"""Optional evidence storage. The bucket mount uses the same file interface as local disk."""

import hashlib
import logging
import re
from datetime import datetime, timezone

from .config import settings

log = logging.getLogger("speccheck.archive")


def save(case_id: str, content: bytes, suffix: str, retrieved_at: str | None = None) -> str | None:
    if settings.evidence_dir is None:
        return None
    case = re.sub(r"[^A-Za-z0-9_-]", "_", case_id)[:120] or "unknown"
    stamp = retrieved_at or datetime.now(timezone.utc).isoformat(timespec="microseconds")
    stamp = re.sub(r"[^0-9TZ+-]", "_", stamp)
    relative = f"{case}/{stamp}/{hashlib.sha256(content).hexdigest()}.{suffix}"
    try:
        path = settings.evidence_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    except OSError:
        log.warning("Evidence archive unavailable; keeping the checked result")
        return None
    return relative

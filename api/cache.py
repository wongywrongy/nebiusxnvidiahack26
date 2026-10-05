"""Tiny disk cache so live calls are paid for once."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from .config import settings


def _path(namespace: str, key: Any):
    digest = hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:24]
    folder = settings.cache_dir / namespace
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}.json"


def get(namespace: str, key: Any) -> Optional[Any]:
    p = _path(namespace, key)
    if p.exists():
        return json.loads(p.read_text())
    return None


def put(namespace: str, key: Any, value: Any) -> None:
    _path(namespace, key).write_text(json.dumps(value, indent=2, default=str))

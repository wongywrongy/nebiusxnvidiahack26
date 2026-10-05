"""Load the test cases and spec sources."""

from __future__ import annotations

import json
from functools import lru_cache

from ..config import settings


@lru_cache
def all_cases() -> dict[str, dict]:
    data = json.loads(settings.cases_file.read_text())
    return {c["id"]: c for c in data["cases"]}


@lru_cache
def all_specs() -> dict[str, dict]:
    data = json.loads(settings.specs_file.read_text())
    return {s["section"]: s for s in data["specs"]}


def get_case(case_id: str) -> dict:
    cases = all_cases()
    if case_id not in cases:
        raise KeyError(f"Unknown case {case_id}")
    return cases[case_id]

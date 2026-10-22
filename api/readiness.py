"""Non-secret configuration and code identity attached to measured runs."""

import hashlib
import json
import os

from .config import PRICES, ROOT, settings

CONFIG_FIELDS = (
    "thinking", "thinking_tasks", "max_output_tokens", "max_page_chars", "web_source_chars",
    "search_depth", "extract_depth", "search_max_results", "investigate_credit_cap",
    "investigate_max_steps", "map_limit", "map_max_depth", "fix_credit_cap", "fix_max_candidates",
    "budget_usd_per_run", "budget_usd_per_day", "budget_tavily_credits_per_item",
    "budget_tavily_credits_per_day", "max_concurrency", "public_uploads_live",
    "nebius_base_url", "tavily_credit_usd",
)


def manifest() -> dict:
    config = {key: getattr(settings, key) for key in CONFIG_FIELDS}
    config.update(models=settings.models, prices=PRICES)
    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    sources = {}
    for folder in (ROOT / "api", ROOT / "scripts"):
        for path in sorted(folder.rglob("*.py")):
            sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    checklists = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((settings.data_dir / "requirements").glob("*.json"))
                  if not p.name.endswith(".draft.json")}
    inputs = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in {
        "cases": settings.cases_file, "specs": settings.specs_file,
        "samples": settings.samples_file,
        "documents": settings.data_dir / "cases" / "documents.json",
    }.items()}
    return {"version": 1, "commit": os.environ.get("SPECCHECK_COMMIT"), "config": config,
            "config_hash": digest(config), "code_hash": digest(sources), "checklists": checklists, "inputs": inputs}


def invalid_reasons(result) -> list[dict]:
    reasons = [d.model_dump() for d in result.diagnostics]
    if result.warnings:
        reasons.append({"stage": "unknown", "kind": "provider", "message": "; ".join(result.warnings)})
    if result.investigation and result.investigation.outcome == "capped":
        reasons.append({"stage": "investigate", "kind": "budget", "message": "Investigation capped"})
    if result.replayed_from:
        reasons.append({"stage": "replay", "kind": "replay", "message": "Playback is not a new evaluation"})
    if result.validity != "valid" and not reasons:
        reasons.append({"stage": "unknown", "kind": result.validity, "message": "Validity was not established"})
    return reasons


def release_checks(score: dict, *, minimum_fixes: int = 1, minimum_resolved: int = 1) -> list[str]:
    """A successful eval is necessary but does not establish the promised complete workflow."""
    issues = []
    if score.get("mode") != "live":
        issues.append("Live evidence required")
    if score.get("validity", {}).get("invalid_items", 1):
        issues.append("Incomplete or invalid items")
    if score["right_call"]["n"] != score["right_call"]["of"]:
        issues.append("Wrong calls")
    if score["caught"]["n"] != score["caught"]["of"]:
        issues.append("Missed problems")
    if score["false_alarms"]["n"] or score.get("unnecessary_notes", {}).get("n", 0):
        issues.append("False alarms or unnecessary notes")
    if score["fixes_passing"]["n"] < minimum_fixes:
        issues.append("No evidenced passing replacement")
    if score.get("investigations", {}).get("resolved", 0) < minimum_resolved:
        issues.append("No demonstrated Investigator rescue")
    return issues

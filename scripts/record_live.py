"""Record the scoring cases and every tray/watched item for the public demo.

  python scripts/record_live.py

Runs every item live (needs NEBIUS_API_KEY and TAVILY_API_KEY), prints the cases-only scoreboard, then copies the run
(events.jsonl, results/) and its scores.json to runs/recorded/<run_id>/. Commit that folder: GET /api/scores falls
back to it and POST /api/runs/replay can play it. Nothing in it holds a key (events are redacted).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

os.environ["SPECCHECK_MODE"] = "live"  # before api.config is imported: fails fast, naming any missing key
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from api.config import settings  # noqa: E402
from api.pipeline.cases import all_cases, all_samples  # noqa: E402
from api.readiness import invalid_reasons  # noqa: E402
from api.schemas import Result  # noqa: E402
from eval import main as scoreboard  # noqa: E402


def record() -> int:
    cases = sorted(all_cases())
    public = sorted(cid for cid, item in {**all_cases(), **all_samples()}.items()
                    if item.get("tray") or item.get("watch"))
    rc = asyncio.run(scoreboard(cases, extra_ids=public))
    if rc == 2:
        raise SystemExit("Cannot record invalid acceptance evidence; inspect the run diagnostics")
    run_id = json.loads(settings.scores_file.read_text())["run_id"]  # a full eval run writes it
    missing = [cid for cid in set(cases + public)
               if not (settings.runs_dir / run_id / "results" / f"{cid}.json").is_file()]
    if missing:
        raise SystemExit(f"Cannot record an incomplete run; missing results: {', '.join(sorted(missing))}")
    for cid in sorted(set(cases + public)):
        result = Result.model_validate_json((settings.runs_dir / run_id / "results" / f"{cid}.json").read_text())
        if result.mode != "live" or invalid_reasons(result):
            raise SystemExit(f"Cannot record invalid acceptance evidence for {cid}; inspect the run diagnostics")
    dest = settings.recorded_dir / run_id
    shutil.copytree(settings.runs_dir / run_id, dest)
    shutil.copy(settings.scores_file, dest / "scores.json")
    print(f"recorded {dest.relative_to(ROOT)}  (commit it)")
    return rc


if __name__ == "__main__":
    sys.exit(record())

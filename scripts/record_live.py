"""Record a live run of all cases for the public demo.

  python scripts/record_live.py

Runs every case live (needs NEBIUS_API_KEY and TAVILY_API_KEY), prints the eval scoreboard, then copies the run
(events.jsonl, results/) and its scores.json to runs/recorded/<run_id>/. Commit that folder: the app replays the
newest recording on open, labeled "Recorded live run <date>". Nothing in it holds a key (events are redacted).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

os.environ["SPECCHECK_MODE"] = "live"  # before api.config is imported: fails fast, naming any missing key
# The public daily Tavily cap (150) is below one full run of 8 items; this is a deliberate local run.
os.environ.setdefault("BUDGET_TAVILY_CREDITS_PER_DAY", "400")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from api.config import settings  # noqa: E402
from api.pipeline.cases import all_cases  # noqa: E402
from eval import main as scoreboard  # noqa: E402


def record() -> int:
    rc = asyncio.run(scoreboard(sorted(all_cases())))
    run_id = json.loads(settings.scores_file.read_text())["run_id"]  # a full eval run writes it
    dest = settings.recorded_dir / run_id
    shutil.copytree(settings.runs_dir / run_id, dest)
    shutil.copy(settings.scores_file, dest / "scores.json")
    print(f"recorded {dest.relative_to(ROOT)}  (commit it; the app replays the newest recording)")
    return rc


if __name__ == "__main__":
    sys.exit(record())

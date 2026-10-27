"""Serve the single-container app with optional persistent judging storage."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from api.config import settings
from api.controller_startup import prepare
from api.providers.budget import BudgetExceeded
from api.providers import campaign
from scripts.campaign_budget import initialize_judging


def prepare_judging() -> None:
    if (settings.judging_usd is None) != (settings.judging_credits is None):
        raise ValueError("Set both JUDGING_USD and JUDGING_CREDITS")
    if settings.app_state_dir:
        if settings.controller_state_dir or not settings.app_state_dir.is_dir():
            raise ValueError("APP_STATE_DIR must be the existing plain-container storage mount")
        image_raw = settings.raw_dir
        root = settings.app_state_dir.resolve()
        for name, relative in (("raw_dir", "raw"), ("uploads_dir", "raw/uploads"), ("cache_dir", "cache"), ("runs_dir", "runs")):
            path = root / relative
            path.mkdir(parents=True, exist_ok=True)
            setattr(settings, name, path)
        settings.campaign_budget_file = root / 'campaign.sqlite3'
        settings.scores_file = settings.runs_dir / 'scores.json'
        for relative, document in json.loads((settings.data_dir / 'documents.lock.json').read_text())['documents'].items():
            target = settings.raw_dir / relative
            source = target if target.exists() else image_raw / relative
            if hashlib.sha256(source.read_bytes()).hexdigest() != document['sha256']:
                raise ValueError("Persistent public document differs from the image lock")
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_suffix('.seed.tmp')
                shutil.copyfile(source, temp)
                temp.replace(target)
        manifest = settings.raw_dir / 'manifest.json'
        if not manifest.exists() and (image_raw / 'manifest.json').exists():
            shutil.copyfile(image_raw / 'manifest.json', manifest)
    if settings.judging_usd is not None:
        if settings.campaign_budget_file.exists():
            campaign.status(settings.campaign_budget_file)
        else:
            initialize_judging(usd=settings.judging_usd, credits=settings.judging_credits)


def main() -> int:
    try:
        prepare_judging()
        if settings.controller_state_dir:
            prepare()
    except (OSError, ValueError, KeyError, TypeError, BudgetExceeded):
        print("Storage preparation refused; preserve the mounted state and inspect the deployment configuration.", file=sys.stderr)
        return 2
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Serve the API, preparing private persistent application storage for a configured controller."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from api.config import settings
from api.controller_startup import prepare
from api.providers.budget import BudgetExceeded


def main() -> int:
    try:
        if settings.controller_state_dir:
            prepare()
    except (OSError, ValueError, KeyError, TypeError, BudgetExceeded):
        print("Controller storage preparation refused; preserve its mounted state and inspect the deployment configuration.", file=sys.stderr)
        return 2
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000)
    return 0


if __name__ == "__main__":
    sys.exit(main())

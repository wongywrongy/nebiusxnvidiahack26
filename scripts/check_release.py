"""Check a final cases/samples/blind/recording bundle without running providers or approving it.

  python scripts/check_release.py path/to/bundle.json --out /tmp/release-check.json
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.release import check
from api.config import redact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check(args.bundle)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError, IndexError):
        result = {"passed": False, "issues": ["Release bundle is missing or invalid"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    safe = redact(json.dumps(result, indent=2))
    args.out.write_text(safe + "\n")
    print(safe)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

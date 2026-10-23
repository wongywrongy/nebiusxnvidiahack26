"""Private POSIX-wallet transfer preparation. Never run against the real wallet before rollout approval.

prepare writes a destination request; export fences the source before releasing a portable snapshot;
receive activates only the pinned snapshot at its prepared destination; cutover requires explicit proof.
Transport is an operator-owned private SSH/SCP step. No keys or wallet contents are printed.
"""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import authority_transfer as transfer
from api.providers.budget import BudgetExceeded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    prepare = actions.add_parser("prepare")
    prepare.add_argument("directory", type=Path)
    prepare.add_argument("--resource-id", required=True)
    export = actions.add_parser("export")
    export.add_argument("source", type=Path)
    export.add_argument("request", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument("--sha256", required=True, help="request hash printed by prepare on the destination")
    for action, artifact in (("receive", "bundle"), ("cutover", "proof")):
        command = actions.add_parser(action)
        command.add_argument(artifact, type=Path)
        command.add_argument("directory", type=Path)
        command.add_argument("--sha256", required=True, help="explicitly pinned artifact hash from its trusted origin")
        if action == "receive":
            command.add_argument("--proof", type=Path, help="owner-approved recovery after destination reboot")
            command.add_argument("--proof-sha256", help="pinned hash of that recovery approval")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = transfer.prepare(args.directory, args.resource_id)
        elif args.action == "export":
            result = transfer.export(args.source, args.request, args.output, args.sha256)
        elif args.action == "receive":
            if bool(args.proof) != bool(args.proof_sha256):
                parser.error("--proof and --proof-sha256 must be supplied together")
            result = transfer.receive(args.bundle, args.directory, args.sha256,
                                      proof_file=args.proof, proof_sha256=args.proof_sha256)
        else:
            result = transfer.cutover(args.directory, args.proof, args.sha256)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, BudgetExceeded):
        parser.exit(2, "Authority transfer refused; preserve the source, destination and private artifacts for reconciliation.\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

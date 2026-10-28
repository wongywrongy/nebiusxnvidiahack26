"""False-approval check: documents checked against a spec section they don't belong to.

For a reviewer, approving something that doesn't belong is the dangerous error, so none of these may end as
approve or approve_with_note. Each runs as an upload, the path a judge takes, so the off-topic guard applies
exactly as it does live. The set is fixed:
  - the off-topic PDF in tests/data against 07 84 00
  - every firestop test case against 26 51 00, every lighting test case against 07 84 00
  - the "Try one" product sheets against the section they don't fit
  - the Schlage door-hardware sheet against both sections

  python scripts/eval_wrong_spec.py                         # mock by default
  SPECCHECK_MODE=live python scripts/eval_wrong_spec.py --into runs/recorded/<run>/scores.json

Writes {"wrong_spec": {n, approved, not_applicable, other, run_id, mode, rows}} into the scores file (default
runs/scores.json), which the Scoreboard reads. Exit 1 if anything was approved; the trace is printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api.pipeline.cases import all_cases, try_documents  # noqa: E402
from api.pipeline.runner import Run, execute  # noqa: E402
from api.providers.tavily import BROWSER_HEADERS  # noqa: E402

SECTIONS = ("07 84 00", "26 51 00")
APPROVED = ("approve", "approve_with_note")
FOLDER = "wrong-spec"  # under data/raw, never committed


def _upload(id_: str, title: str, file: str, section: str, fixture: str | None = None) -> dict:
    return {"id": id_, "title": title, "section": section, "upload": True, "fixture": fixture,
            "submittal": [{"role": "product_data", "file": file}], "conditions": [], "not_applicable": []}


def _fetch(url: str, name: str) -> str | None:
    """A Try-one sheet, downloaded once into data/raw/wrong-spec/. None when it can't be had (mock never fetches)."""
    path = settings.raw_dir / FOLDER / name
    if not path.is_file() and settings.live:
        r = httpx.get(url, headers=BROWSER_HEADERS, follow_redirects=True, timeout=60)
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
    return f"{FOLDER}/{name}" if path.is_file() else None


def items() -> dict[str, dict]:
    out = {}
    for cid, case in sorted(all_cases().items()):
        section = next(s for s in SECTIONS if s != case["section"])
        out[f"w-{cid}"] = _upload(f"w-{cid}", case["title"], case["submittal"][0]["file"], section, case.get("fixture", cid))
    off = settings.raw_dir / FOLDER / "off-topic.pdf"
    off.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "tests/data/off-topic.pdf", off)
    out["w-off-topic"] = _upload("w-off-topic", "Off-topic PDF", f"{FOLDER}/off-topic.pdf", "07 84 00")
    for n, doc in enumerate(d for d in try_documents() if d["kind"] == "product"):
        file = _fetch(doc["url"], f"try-{n}.pdf")
        if not file:
            print(f"skipped (not downloaded): {doc['title']}")
            continue
        wrong = [s for s in SECTIONS if s != doc["fits"]]  # "pair with …" fits neither section
        for section in wrong:
            key = f"w-try{n}-{section.replace(' ', '')}"
            out[key] = _upload(key, doc["title"], file, section)
    return out


async def main(into: Path) -> int:
    catalog = items()
    run = Run(list(catalog), delay_ms=0, catalog=catalog)
    await execute(run)
    rows = []
    for key, case in catalog.items():
        res = run.results.get(key)
        decision = res.decision if res else "error"
        rows.append({"id": key, "document": case["title"], "section": case["section"], "decision": decision})
        if decision in APPROVED:
            print(f"\nAPPROVED {key}: {case['title']} vs {case['section']}")
            for f in res.findings:
                print(f"  {f.check:<9} {f.verdict:<14} {f.title}  claims={f.claim_ids or f.claim_id}")
    block = {"n": len(rows), "approved": sum(r["decision"] in APPROVED for r in rows),
             "not_applicable": sum(r["decision"] == "not_applicable" for r in rows),
             "other": sum(r["decision"] not in (*APPROVED, "not_applicable") for r in rows),
             "run_id": run.id, "mode": settings.mode, "rows": rows}
    for r in rows:
        print(f"{r['id']:<22} {r['section']}  {r['decision']:<18} {r['document']}")
    print(f"\nwrong spec: {block['n']} documents · {block['approved']} approved · "
          f"{block['not_applicable']} not applicable · {block['other']} other   (run {run.id}, {settings.mode})")
    scores = json.loads(into.read_text()) if into.is_file() else {}
    into.parent.mkdir(parents=True, exist_ok=True)
    into.write_text(json.dumps({**scores, "wrong_spec": block}, indent=2))
    print(f"wrote wrong_spec into {into}")
    return 1 if block["approved"] else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--into", type=Path, default=settings.scores_file, help="scores file to add the block to")
    sys.exit(asyncio.run(main(p.parse_args().into)))

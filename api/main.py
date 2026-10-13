"""HTTP API.

  GET  /api/health                     mode, which keys are set (true/false), model IDs, today's spend,
                                       newest recorded live run
  GET  /api/project                    project, specs, the sample tray (grouped by sender) and the watched item
  POST /api/inbox                      add one item, no run: {"id": "c03"} for a tray item, or a raw PDF body
                                       with ?name=x.pdf for an upload
  POST /api/scan                       one run over inbox items {"ids": [...], "delay_ms": 600}. Tray and watched
                                       items and uploads run live by default, within public rate and day caps
  POST /api/runs                       start a run       {"case_ids": [...], "delay_ms": 600}   [admin when live]
  POST /api/runs/replay                replay a recording {"source_run_id": "...", "speed": 1.0}
  GET  /api/scores                     the answer-key scores written by scripts/eval.py (else the newest recording's)
  GET  /api/specs                      project spec sources, checklists and recorded provenance
  POST /api/specs/draft                raw PDF -> a public draft, never saved as a checklist    [live only]
  POST /api/specs/{section}            save a checklist with a review date                     [admin]
  POST /api/scores/run                 run all cases now and rewrite the scores               [admin when live]
  GET  /api/runs                       recorded runs, newest first
  GET  /api/runs/{id}/events           server-sent events: history, then live
  GET  /api/runs/{id}/results          all results of a run
  GET  /api/runs/{id}/results/{case}   one result
  GET  /api/docs/{case}/{file}/pages            page count and sizes of a downloaded submittal PDF
  GET  /api/docs/{case}/{file}/pages/{n}.png     one page as PNG
  GET  /api/cases/{case}/text                    fixture page text (fallback when the PDF is missing)

Admin = header X-Admin-Token equal to ADMIN_TOKEN.
The built web app (web/dist) is served at / from the same container.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .pipeline.cases import add_upload, all_cases, all_samples, all_specs, get_case, get_upload, mock_ready, senders
from .llm import load_fixture
from .pipeline.ingest import pdf_pages
from .pipeline import checklists
from .pipeline.extract import checklist_path
from .pipeline.render import page_count, page_sizes, render_page
from .pipeline.runner import Run, execute, list_runs, load_result, recorded_runs, replay, run_dir
from .pipeline.scores import run_scoring_set
from .providers import ProviderError, budget, failure_reason
from .schemas import Event, ReviewedChecklist

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
app = FastAPI(title="SpecCheck")
RUNS: dict[str, Run] = {}
_tasks: set[asyncio.Task] = set()


class StartRun(BaseModel):
    case_ids: Optional[list[str]] = None
    delay_ms: Optional[int] = None


class Scan(BaseModel):
    ids: list[str]
    delay_ms: Optional[int] = None


class StartReplay(BaseModel):
    source_run_id: str
    speed: float = Field(default=1.0, gt=0, le=1000)


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _is_admin(request: Request) -> bool:
    token = settings.secret("admin_token")
    return bool(token) and hmac.compare_digest(request.headers.get("x-admin-token", "").encode(), token.encode())


def _live_needs_admin(request: Request) -> None:
    if settings.live and not _is_admin(request):
        raise HTTPException(403, "Live runs need the admin token (X-Admin-Token header). The public demo plays recorded runs.")


# ponytail: in-memory per process and keyed on the socket address; behind a proxy read X-Forwarded-For from it.
_uploads_by_ip: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request) -> None:
    now, q = time.time(), _uploads_by_ip[request.client.host if request.client else "?"]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= settings.uploads_per_ip_per_hour:
        raise HTTPException(429, "Too many uploads from this address; try again in an hour.")
    q.append(now)


@app.get("/api/health")
def health():
    rec = recorded_runs()
    return {"mode": settings.mode, "keys": settings.keys_present, "models": settings.models, "today": budget.today(),
            "budget": budget.remaining(), "recorded": rec[0] if rec else None}


@app.get("/api/project")
def project():
    data = json.loads(settings.cases_file.read_text())
    groups: dict[str, list[dict]] = {}
    for c in {**all_cases(), **all_samples()}.values():
        if c.get("tray"):
            groups.setdefault(c["from"], []).append(_public(c))
    return {
        "name": data["project"],
        "specs": list(all_specs().values()),
        "tray": [{"from": name, **senders().get(name, {}), "items": items} for name, items in groups.items()],
        "watched": [_public(c) for c in all_cases().values() if c.get("watch")],
        "mode": settings.mode,
        "recheck": latest_recheck(),
    }


def latest_recheck() -> Optional[dict]:
    """The newest nightly re-check report (scripts/recheck.py writes runs/watch/latest.json), or None."""
    p = settings.runs_dir / "watch" / "latest.json"
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except (OSError, ValueError):
        return None


@app.post("/api/runs")
async def start_run(body: StartRun, request: Request):
    _live_needs_admin(request)
    ids = body.case_ids or sorted(all_cases())
    unknown = [i for i in ids if i not in all_cases()]
    if unknown:
        raise HTTPException(400, f"Unknown cases: {unknown}")
    run = Run(ids, delay_ms=body.delay_ms)
    RUNS[run.id] = run
    _spawn(execute(run))
    return {"run_id": run.id, "mode": settings.mode, "case_ids": ids}


def _scannable(case_id: str) -> Optional[dict]:
    """A tray item, a watched item or an upload: what the app may run without the admin token."""
    case = {**all_cases(), **all_samples()}.get(case_id)
    return case if case and (case.get("tray") or case.get("watch")) else get_upload(case_id)


async def _read_pdf(request: Request) -> tuple[bytes, str]:
    limit = settings.max_upload_mb * 1024 * 1024
    if int(request.headers.get("content-length") or 0) > limit:
        raise HTTPException(413, f"PDF is larger than {settings.max_upload_mb} MB")
    pdf = await request.body()
    if len(pdf) > limit:
        raise HTTPException(413, f"PDF is larger than {settings.max_upload_mb} MB")
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(400, "Not a PDF")
    try:
        return pdf, "\n".join(p["text"] for p in pdf_pages(pdf))
    except Exception:
        raise HTTPException(400, "Could not read this PDF")


@app.post("/api/inbox")
async def inbox(request: Request, name: str = "upload.pdf"):
    """Add one item to the inbox. Nothing runs until /api/scan."""
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
        case = {**all_cases(), **all_samples()}.get(body.get("id", "") if isinstance(body, dict) else "")
        if not case or not case.get("tray"):
            raise HTTPException(404, "No such tray item")
        if not (settings.live or mock_ready(case)):
            raise HTTPException(409, "Available in live mode")
        return _public(case)

    if settings.live and budget.day_spent():
        raise HTTPException(429, "Today's live budget is spent. Uploads can be checked again tomorrow (UTC).")
    if not _is_admin(request):
        _rate_limit(request)
    pdf, text = await _read_pdf(request)
    return _public(add_upload(name, pdf, text))


@app.get("/api/specs")
def specs():
    return {"mode": settings.mode, "sections": checklists.sections()}


@app.post("/api/specs/draft")
async def draft_spec(request: Request, section: str, name: str = "spec.pdf"):
    if not settings.live:
        raise HTTPException(409, "Live only: checklist drafting uses Nemotron 3 Super on Token Factory.")
    if section not in all_specs():
        raise HTTPException(404, "Unknown spec section")
    if not _is_admin(request):
        _rate_limit(request)
    if budget.day_spent():
        raise HTTPException(429, "Today's live budget is spent. Try again tomorrow (UTC).")
    pdf, text = await _read_pdf(request)
    if not text.strip():
        raise HTTPException(400, "No readable text in this spec PDF")
    token = budget.LEDGER.set(budget.Ledger())
    try:
        draft, usage = await checklists.draft(section, text, name.rsplit("/", 1)[-1][:160],
                                              source_sha256=hashlib.sha256(pdf).hexdigest())
        return {"draft": draft, "usage": usage}
    except budget.BudgetExceeded as e:
        raise HTTPException(429, failure_reason(e)) from e
    except ProviderError as e:
        raise HTTPException(503, failure_reason(e)) from e
    finally:
        budget.LEDGER.reset(token)


@app.post("/api/specs/{section}")
def save_spec(section: str, body: ReviewedChecklist, request: Request):
    if not _is_admin(request):
        raise HTTPException(403, "Saving a reviewed checklist needs the admin token (X-Admin-Token header).")
    if section not in all_specs():
        raise HTTPException(404, "Unknown spec section")
    if not body.requirements or any(r.section != section for r in body.requirements):
        raise HTTPException(422, "Every requirement must belong to this section, and the checklist cannot be empty.")
    if len({r.id for r in body.requirements}) != len(body.requirements):
        raise HTTPException(422, "Requirement IDs must be unique within the checklist.")
    path = checklist_path(section)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(body.model_dump_json(indent=2))
    temp.replace(path)
    return {"section": section, "checklist": body, "status": "reviewed"}


@app.post("/api/scan")
async def scan(body: Scan, request: Request):
    """Public scans share the rate and day caps; an exhausted day can replay recorded tray items."""
    ids = list(dict.fromkeys(body.ids))
    cases = {i: _scannable(i) for i in ids}
    unknown = [i for i, c in cases.items() if c is None]
    if not ids or unknown:
        raise HTTPException(400, f"Unknown items: {unknown}" if unknown else "Nothing to scan")
    if not settings.live and any(not (c.get("upload") or mock_ready(c)) for c in cases.values()):
        raise HTTPException(409, "Available in live mode")
    admin = _is_admin(request)
    if settings.live and not admin:  # only live runs spend; a mock scan is free
        _rate_limit(request)
    if settings.live and budget.day_spent():
        rec = recorded_runs()
        source = rec[0] if rec else None
        if any(c.get("upload") for c in cases.values()) or not source or any(
            not (settings.recorded_dir / source / "results" / f"{i}.json").is_file() for i in ids
        ):
            raise HTTPException(429, "Today's live budget is spent and these items have no complete recording. Try again tomorrow (UTC).")
        run = Run(ids, delay_ms=0)
        RUNS[run.id] = run
        _spawn(replay(run, source, ids=ids))
        date = f"{source[:4]}-{source[4:6]}-{source[6:8]}"
        return {"run_id": run.id, "mode": "live", "mock": [], "replay_of": source,
                "note": f"Replayed from the live run recorded on {date}: today's live budget is spent."}
    mock = ([i for i, c in cases.items() if c.get("upload")]
            if settings.live and not admin and not settings.public_uploads_live else [])
    run = Run(ids, delay_ms=body.delay_ms, mock=mock)
    RUNS[run.id] = run
    _spawn(execute(run))
    note = "Uploads ran in mock mode: public live uploads are disabled; live checks need the admin token." if mock else None
    return {"run_id": run.id, "mode": settings.mode, "mock": mock, "note": note}


@app.post("/api/scores/run")
async def run_scores(request: Request):
    _live_needs_admin(request)
    return await run_scoring_set()


class WatchReport(BaseModel):
    """What scripts/recheck.py posts after a nightly run (the Serverless Job has no disk the app can read)."""
    checked_at: str
    runner: str
    mode: str
    run_id: Optional[str] = None
    items: list[dict]


@app.get("/api/watch")
def watch():
    rep = latest_recheck()
    if rep is None:
        raise HTTPException(404, "No nightly re-check has reported yet (scripts/recheck.py)")
    return rep


@app.post("/api/watch/report")
def watch_report(body: WatchReport, request: Request):
    """The nightly job reports here with the admin token; the app shows the latest report on the Outcome step."""
    if not _is_admin(request):
        raise HTTPException(403, "Reporting a re-check needs the admin token (X-Admin-Token header)")
    folder = settings.runs_dir / "watch"
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body.model_dump(), indent=2)
    (folder / "latest.json").write_text(text)
    (folder / f"{body.checked_at[:10]}.json").write_text(text)
    return {"ok": True, "items": len(body.items)}


@app.get("/api/scores")
def scores():
    rec = recorded_runs()
    path = settings.scores_file if settings.scores_file.exists() or not rec else settings.recorded_dir / rec[0] / "scores.json"
    if not path.exists():
        raise HTTPException(404, "No scores yet: run python scripts/eval.py")
    return json.loads(path.read_text())


def _public(case: dict) -> dict:
    """What the app shows of an item: no answer key."""
    return {**{k: case[k] for k in ("id", "number", "title", "product", "from", "section", "received", "watch") if k in case},
            **senders().get(case.get("from", ""), {}),
            "submittal": [{k: d[k] for k in ("role", "file", "url") if k in d} for d in case["submittal"]],
            "pages": _pages(case), "upload": bool(case.get("upload")), "mock_fixture": case.get("fixture"),
            "ready": settings.live or bool(case.get("upload")) or mock_ready(case)}


def _pages(case: dict) -> int:
    """Page count of the downloaded PDFs, else of the recorded page text, else 0."""
    paths = [settings.raw_dir / d["file"] for d in case["submittal"]]
    if all(p.is_file() for p in paths):
        return sum(page_count(p) for p in paths)
    return len(load_fixture(case.get("fixture", case["id"])).get("pages", [])) if mock_ready(case) else 0


@app.post("/api/runs/replay")
async def start_replay(body: StartReplay):
    if not run_dir(body.source_run_id):
        raise HTTPException(404, "No such recorded run")
    run = Run([])
    RUNS[run.id] = run
    _spawn(replay(run, body.source_run_id, body.speed))
    return {"run_id": run.id, "replay_of": body.source_run_id}


@app.get("/api/runs")
def runs():
    return {"runs": list_runs()}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str):
    async def from_memory(run: Run):
        async for ev in run.stream():
            yield _sse(ev)
        yield "event: end\ndata: {}\n\n"

    async def from_disk(folder):
        for line in (folder / "events.jsonl").read_text().splitlines():
            if line:
                yield _sse(Event.model_validate_json(line))
        yield "event: end\ndata: {}\n\n"

    if run_id in RUNS:
        gen = from_memory(RUNS[run_id])
    elif folder := run_dir(run_id):
        gen = from_disk(folder)
    else:
        raise HTTPException(404, "No such run")
    return StreamingResponse(gen, media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/runs/{run_id}/results")
def results(run_id: str):
    folder = run_dir(run_id)
    if not folder:
        raise HTTPException(404, "No such run")
    return {"results": [json.loads(p.read_text()) for p in sorted((folder / "results").glob("*.json"))]}


@app.get("/api/runs/{run_id}/results/{case_id}")
def result(run_id: str, case_id: str):
    res = load_result(run_id, case_id)
    if res is None:
        raise HTTPException(404, "No result yet")
    return res


def _submittal_pdf(case_id: str, file: str):
    """Path of a downloaded submittal PDF, by file name. Only files the case lists, only under data/raw/."""
    try:
        case = get_case(case_id)
    except KeyError:
        case = None
    rels = [d["file"] for d in (case or {}).get("submittal", []) if d["file"].rsplit("/", 1)[-1] == file]
    path = (settings.raw_dir / rels[0]).resolve() if rels else None
    if path is None or not path.is_relative_to(settings.raw_dir.resolve()) or not path.is_file():
        raise HTTPException(404, "No such document in data/raw/")
    return path


@app.get("/api/docs/{case_id}/{file}/pages")
def doc_pages(case_id: str, file: str):
    sizes = page_sizes(_submittal_pdf(case_id, file))
    return {"count": len(sizes), "pages": sizes}


@app.get("/api/docs/{case_id}/{file}/pages/{n}.png")
def doc_page_png(case_id: str, file: str, n: int):
    path = _submittal_pdf(case_id, file)
    if not 1 <= n <= len(page_sizes(path)):
        raise HTTPException(404, "No such page")
    return Response(render_page(path, n), media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/cases/{case_id}/text")
def case_text(case_id: str):
    try:
        case = get_case(case_id)
    except KeyError:
        raise HTTPException(404, "Unknown case")
    return {"pages": load_fixture(case.get("fixture", case_id)).get("pages", [])}


def _sse(ev: Event) -> str:
    return f"data: {ev.model_dump_json()}\n\n"


if settings.web_dist.exists():
    app.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="web")

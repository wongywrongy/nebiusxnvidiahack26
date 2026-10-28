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
  GET  /api/scores                     saved answer-key scores, else compute the mock set without provider calls
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
import re
import shutil
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .config import settings, redact
from . import daily_recheck, watch_store
from .pipeline.cases import add_upload, all_cases, all_samples, all_specs, get_case, get_upload, mock_ready, save_upload, senders, try_documents
from .llm import load_fixture
from .pipeline.ingest import pdf_pages
from .pipeline import checklists, package
from .pipeline.extract import checklist_path
from .pipeline.render import page_count, page_sizes, prune_page_cache, render_page
from .pipeline.runner import Run, execute, list_runs, load_result, prune_runs, recorded_runs, replay, run_dir
from .pipeline.scores import run_scoring_set
from .providers import ProviderError, budget, failure_reason
from .schemas import Event, ReviewedChecklist, UploadChecklist

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
STARTED = time.monotonic()
MAX_MEMORY_RUNS = 200
@asynccontextmanager
async def lifespan(app):
    global STARTED
    STARTED = time.monotonic()
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    prune_page_cache()
    prune_runs()
    checklists.prune_uploads()
    if settings.live:
        try:
            budget.recover_unknown_usage()
        except (OSError, ValueError, budget.BudgetExceeded):
            logging.getLogger("speccheck.startup").warning("Campaign ledger unavailable; paid calls remain blocked")
    logging.getLogger("speccheck.startup").info("Today's recorded spend: %s; caps: %s (campaign ledger on %s; hosted persistence unverified)",
                                               budget.today(), budget.caps(),
                                               "private controller mount" if settings.controller_state_dir else "local disk")
    daily = asyncio.create_task(daily_recheck.loop()) if daily_recheck.configured() else None
    try:
        yield
    finally:
        if daily:
            daily.cancel()


app = FastAPI(title="SpecCheck", lifespan=lifespan)


@app.exception_handler(budget.BudgetExceeded)
async def accounting_unavailable(request: Request, error: budget.BudgetExceeded):
    return JSONResponse(status_code=503, content={"detail": redact(str(error))[:400]})
RUNS: dict[str, Run] = {}
_tasks: set[asyncio.Task] = set()


class StartRun(BaseModel):
    case_ids: Optional[list[str]] = None
    delay_ms: Optional[int] = None


class Scan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str]
    delay_ms: Optional[int] = None
    shared_item_budget: bool = False
    refresh_web: bool = False


class StartReplay(BaseModel):
    source_run_id: str
    speed: float = Field(default=1.0, gt=0, le=1000)


class UploadSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec: str = Field(min_length=1, max_length=80)


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _new_run(*args, **kwargs) -> Run:
    while len(RUNS) >= MAX_MEMORY_RUNS:
        oldest = next((key for key, run in RUNS.items() if run.done.is_set()), None)
        if oldest is None:
            raise HTTPException(503, "The scan queue is full. Try again when a scan finishes.")
        del RUNS[oldest]
    run = Run(*args, **kwargs)
    RUNS[run.id] = run
    return run


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
    disk_path = next(p for p in (settings.runs_dir, *settings.runs_dir.parents) if p.exists())
    return {"mode": settings.mode, "keys": settings.keys_present, "models": settings.models, "today": budget.today(),
            "budget": budget.remaining(), "recorded": rec[0] if rec else None,
            "caps": budget.caps(), "scan_shared_item_budget": True,
            "uptime_s": round(time.monotonic() - STARTED, 1),
            "disk_free_gb": round(shutil.disk_usage(disk_path).free / 1024**3, 2)}


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
        "try": try_documents(),
        "tray": [{"from": name, **senders().get(name, {}), "items": items} for name, items in groups.items()],
        "watched": [_public(c) for c in all_cases().values() if c.get("watch")],
        "mode": settings.mode,
        "recheck": latest_recheck(),
    }


def latest_recheck() -> Optional[dict]:
    """The newest nightly re-check report (scripts/recheck.py writes runs/watch/latest.json), or None."""
    return watch_store.read("latest.json")


@app.post("/api/runs")
async def start_run(body: StartRun, request: Request):
    _live_needs_admin(request)
    ids = body.case_ids or sorted(all_cases())
    unknown = [i for i in ids if i not in all_cases()]
    if unknown:
        raise HTTPException(400, f"Unknown cases: {unknown}")
    run = _new_run(ids, delay_ms=body.delay_ms)
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
        pages = await pdf_pages(pdf)
        return pdf, "\n".join(p["text"] for p in pages)
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
        if "checklist_id" in body or "spec" in body:
            raise HTTPException(422, "Only uploaded PDFs can use a different spec or draft checklist")
        if not (settings.live or mock_ready(case)):
            raise HTTPException(409, "Available in live mode")
        return _public(case)

    if settings.live and budget.day_spent():
        raise HTTPException(429, budget.unavailable_reason())
    if not _is_admin(request):
        _rate_limit(request)
    pdf, text = await _read_pdf(request)
    return _public(add_upload(name, pdf, text))


@app.patch("/api/inbox/{case_id}")
async def set_upload_spec(case_id: str, body: UploadSpec):
    case = get_upload(case_id)
    if case is None:
        raise HTTPException(422, "Only uploaded PDFs can use a different spec or draft checklist")
    if case.get("scanned_at"):
        raise HTTPException(409, "This upload has already been scanned. Upload it again to choose a different spec.")
    if body.spec in all_specs():
        case["section"] = body.spec
        case.pop("checklist_id", None)
    else:
        if not body.spec.startswith("ck-"):
            raise HTTPException(422, "Choose a known spec section or a saved draft checklist")
        checklist = checklists.load_upload(body.spec)
        case.update(section=checklist.section, checklist_id=body.spec)
    case.update(conditions=[], not_applicable=[])
    save_upload(case)
    return _public(case)


@app.post("/api/checklists")
async def save_upload_checklist(body: UploadChecklist, request: Request):
    if not _is_admin(request):
        _rate_limit(request)
    return checklists.save_upload(body)


@app.get("/api/specs")
def specs():
    return {"mode": settings.mode, "sections": checklists.sections(), "try": try_documents()}


@app.post("/api/specs/draft")
async def draft_spec(request: Request, section: str = Query(pattern=r"^\d{2} \d{2} \d{2}$"),
                     title: str = Query(default="", max_length=160), name: str = "spec.pdf"):
    if not settings.live:
        raise HTTPException(409, "Live only: checklist drafting uses Nemotron 3 Super on Token Factory.")
    title = title.strip() or all_specs().get(section, {}).get("title", "")
    if not title or any(ord(c) < 32 for c in title):
        raise HTTPException(422, "A new section needs a title (1–160 characters, no control characters).")
    if not _is_admin(request):
        _rate_limit(request)
    if budget.day_spent():
        raise HTTPException(429, budget.unavailable_reason())
    pdf, text = await _read_pdf(request)
    if not text.strip():
        raise HTTPException(400, "No readable text in this spec PDF")
    token = budget.LEDGER.set(budget.Ledger())
    item_token = budget.ITEM.set(f"spec-draft-{section}")
    try:
        draft, usage = await checklists.draft(section, text, name.rsplit("/", 1)[-1][:160],
                                              source_sha256=hashlib.sha256(pdf).hexdigest(), title=title)
        return {"draft": draft, "usage": usage}
    except budget.BudgetExceeded as e:
        raise HTTPException(429, failure_reason(e)) from e
    except ProviderError as e:
        raise HTTPException(503, failure_reason(e)) from e
    finally:
        budget.LEDGER.reset(token)
        budget.ITEM.reset(item_token)


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
    for case in cases.values():
        if case.get("checklist_id"):
            if not case.get("upload"):
                raise HTTPException(422, "Draft checklists can only be used for uploaded PDFs")
            checklists.load_upload(case["checklist_id"])
    if not settings.live and any(not (c.get("upload") or mock_ready(c)) for c in cases.values()):
        raise HTTPException(409, "Available in live mode")
    admin = _is_admin(request)
    if settings.live and not admin:  # only live runs spend; a mock scan is free
        _rate_limit(request)
    if settings.live and budget.day_spent():
        reason = budget.unavailable_reason()
        if body.refresh_web:
            raise HTTPException(429, reason + " A fresh re-check cannot use replay.")
        rec = recorded_runs()
        source = rec[0] if rec else None
        if any(c.get("upload") for c in cases.values()) or not source or any(
            not (settings.recorded_dir / source / "results" / f"{i}.json").is_file() for i in ids
        ):
            raise HTTPException(429, reason + " These items have no complete recording.")
        run = _new_run(ids, delay_ms=0, replay_of=source)
        _spawn(replay(run, source, ids=ids))
        date = f"{source[:4]}-{source[4:6]}-{source[6:8]}"
        return {"run_id": run.id, "mode": "live", "mock": [], "replay_of": source,
                "note": f"Replayed from the live run recorded on {date}: {reason.lower()}"}
    mock = ([i for i, c in cases.items() if c.get("upload")]
            if settings.live and not admin and not settings.public_uploads_live else [])
    run = _new_run(ids, delay_ms=body.delay_ms, mock=mock, shared_item_budget=body.shared_item_budget,
                   refresh_web=body.refresh_web)
    for case in cases.values():
        if case.get("upload"):
            case["scanned_at"] = datetime.now().isoformat()
            save_upload(case)
    _spawn(execute(run))
    note = "Uploads ran in mock mode: public live uploads are disabled; live checks need the admin token." if mock else None
    return {"run_id": run.id, "mode": settings.mode, "mock": mock, "note": note,
            "shared_item_budget": body.shared_item_budget}


@app.post("/api/scores/run")
async def run_scores(request: Request):
    _live_needs_admin(request)
    return await run_scoring_set()


class WatchReport(BaseModel):
    """What scripts/recheck.py posts after a nightly run (the Serverless Job has no disk the app can read)."""
    checked_at: datetime
    runner: str
    mode: Literal["mock", "live"]
    run_id: Optional[str] = None
    job_name: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,160}$")
    duration_ms: Optional[int] = Field(default=None, ge=0)
    items: list[dict]


@app.get("/api/watch")
def watch():
    rep = latest_recheck()
    if rep is None:
        raise HTTPException(404, "No nightly re-check has reported yet (scripts/recheck.py)")
    return rep


@app.post("/api/watch/report")
async def watch_report(body: WatchReport, request: Request):
    """The nightly job reports here with the admin token; the app shows the latest report on the Outcome step."""
    if not _is_admin(request):
        raise HTTPException(403, "Reporting a re-check needs the admin token (X-Admin-Token header)")
    if body.job_name:
        raise HTTPException(409, "Name a job in runner; only jobs this server launched are accepted")
    # Only a job this server launched may sign a report as a Nebius Serverless Job.
    if "nebius" in body.runner.lower() and body.runner not in {daily_recheck.PREFIX + n for n in daily_recheck.launched_names()}:
        raise HTTPException(422, "No job with that name was launched by this server")
    report = body.model_dump(mode="json")
    watch_store.report(report)
    return {"ok": True, "items": len(body.items)}


@app.get("/api/evidence/{path:path}")
def archived_evidence(path: str):
    if not settings.evidence_dir or not re.fullmatch(r"[A-Za-z0-9_-]+/[0-9TZ+_-]+/[0-9a-f]{64}\.(txt|pdf)", path):
        raise HTTPException(404, "No archived copy")
    local = (settings.evidence_dir / path).resolve()
    if not local.is_relative_to(settings.evidence_dir.resolve()) or not local.is_file():
        raise HTTPException(404, "No archived copy")
    return FileResponse(local, media_type="application/pdf" if local.suffix == ".pdf" else "text/plain; charset=utf-8")


@app.get("/api/scores")
async def scores():
    rec = recorded_runs()
    path = settings.scores_file if settings.scores_file.exists() or not rec else settings.recorded_dir / rec[0] / "scores.json"
    archived = settings.evidence_dir / "scores.json" if settings.evidence_dir else None
    if archived and archived.is_file() and (not path.exists() or archived.stat().st_mtime > path.stat().st_mtime):
        path = archived
    if not path.exists():
        return await run_scoring_set(mock=True)
    return json.loads(path.read_text())


def _public(case: dict) -> dict:
    """What the app shows of an item: no answer key."""
    return {**{k: case[k] for k in ("id", "number", "title", "product", "from", "section", "received", "watch", "checklist_id", "scanned_at") if k in case},
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
    run = _new_run([], replay_of=body.source_run_id)
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
    return {"results": [json.loads(p.read_text()) for p in sorted((folder / "results").glob("*.json"))],
            "done": RUNS[run_id].done.is_set() if run_id in RUNS else True}


@app.get("/api/runs/{run_id}/package")
def package_view(run_id: str):
    """The whole package as one compliance matrix (rows derived in code from each result's findings)."""
    folder = run_dir(run_id)
    if not folder:
        raise HTTPException(404, "No such run")
    items = []
    for p in sorted((folder / "results").glob("*.json")):
        res = load_result(run_id, p.stem)
        if res is None:
            continue
        case = {**all_cases(), **all_samples()}.get(res.case_id) or get_upload(res.case_id) or {}
        items.append((_public(case) if case else {}, res))
    return package.summarize(run_id, items)


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

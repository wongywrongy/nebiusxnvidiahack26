"""HTTP API.

  GET  /api/health                     mode and model IDs
  GET  /api/project                    sample project, specs and cases
  POST /api/runs                       start a run       {"case_ids": [...], "delay_ms": 600}
  POST /api/runs/replay                replay a recording {"source_run_id": "...", "speed": 1.0}
  POST /api/uploads?name=x.pdf         body: the PDF. Starts a run of it against the project specs
  GET  /api/scores                     the answer-key scores written by scripts/eval.py
  GET  /api/runs                       recorded runs, newest first
  GET  /api/runs/{id}/events           server-sent events: history, then live
  GET  /api/runs/{id}/results          all results of a run
  GET  /api/runs/{id}/results/{case}   one result
  GET  /api/docs/{case}/{file}/pages            page count and sizes of a downloaded submittal PDF
  GET  /api/docs/{case}/{file}/pages/{n}.png     one page as PNG
  GET  /api/cases/{case}/text                    fixture page text (fallback when the PDF is missing)

The built web app (web/dist) is served at / from the same container.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .pipeline.cases import add_upload, all_cases, all_specs, get_case
from .llm import load_fixture
from .pipeline.ingest import pdf_pages
from .pipeline.render import page_sizes, render_page
from .pipeline.runner import Run, execute, list_runs, load_result, replay
from .schemas import Event

app = FastAPI(title="SpecCheck")
RUNS: dict[str, Run] = {}
_tasks: set[asyncio.Task] = set()


class StartRun(BaseModel):
    case_ids: Optional[list[str]] = None
    delay_ms: Optional[int] = None


class StartReplay(BaseModel):
    source_run_id: str
    speed: float = 1.0


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


@app.get("/api/health")
def health():
    return {"mode": settings.mode, "models": settings.models}


@app.get("/api/project")
def project():
    data = json.loads(settings.cases_file.read_text())
    return {
        "name": data["project"],
        "specs": list(all_specs().values()),
        "cases": [
            {"id": c["id"], "title": c["title"], "section": c["section"], "submittal": c["submittal"]}
            for c in all_cases().values()
        ],
    }


@app.post("/api/runs")
async def start_run(body: StartRun):
    ids = body.case_ids or sorted(all_cases())
    unknown = [i for i in ids if i not in all_cases()]
    if unknown:
        raise HTTPException(400, f"Unknown cases: {unknown}")
    run = Run(ids, delay_ms=body.delay_ms)
    RUNS[run.id] = run
    _spawn(execute(run))
    return {"run_id": run.id, "mode": settings.mode, "case_ids": ids}


@app.post("/api/uploads")
async def upload(request: Request, name: str = "upload.pdf", delay_ms: Optional[int] = None):
    """Raw PDF body (no multipart dependency). The new item streams on its own run like any other row."""
    pdf = await request.body()
    if len(pdf) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"PDF is larger than {settings.max_upload_mb} MB")
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(400, "Not a PDF")
    try:
        text = "\n".join(p["text"] for p in pdf_pages(pdf))
    except Exception:
        raise HTTPException(400, "Could not read this PDF")
    case = add_upload(name, pdf, text)
    run = Run([case["id"]], delay_ms=delay_ms)
    RUNS[run.id] = run
    _spawn(execute(run))
    return {"run_id": run.id, "mode": settings.mode, "case": _public(case)}


@app.get("/api/scores")
def scores():
    if not settings.scores_file.exists():
        raise HTTPException(404, "No scores yet: run python scripts/eval.py")
    return json.loads(settings.scores_file.read_text())


def _public(case: dict) -> dict:
    return {"id": case["id"], "title": case["title"], "section": case["section"], "submittal": case["submittal"],
            "upload": bool(case.get("upload")), "mock_fixture": case.get("fixture")}


@app.post("/api/runs/replay")
async def start_replay(body: StartReplay):
    if not (settings.runs_dir / body.source_run_id / "events.jsonl").exists():
        raise HTTPException(404, "No such recorded run")
    run = Run([], replay_of=body.source_run_id)
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

    async def from_disk():
        path = settings.runs_dir / run_id / "events.jsonl"
        for line in path.read_text().splitlines():
            if line:
                yield _sse(Event.model_validate_json(line))
        yield "event: end\ndata: {}\n\n"

    if run_id in RUNS:
        gen = from_memory(RUNS[run_id])
    elif (settings.runs_dir / run_id / "events.jsonl").exists():
        gen = from_disk()
    else:
        raise HTTPException(404, "No such run")
    return StreamingResponse(gen, media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/runs/{run_id}/results")
def results(run_id: str):
    folder = settings.runs_dir / run_id / "results"
    if not folder.exists():
        raise HTTPException(404, "No such run")
    return {"results": [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]}


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

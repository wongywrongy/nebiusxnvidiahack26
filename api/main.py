"""HTTP API.

  GET  /api/health                     mode and model IDs
  GET  /api/project                    sample project, specs and cases
  POST /api/runs                       start a run       {"case_ids": [...], "delay_ms": 600}
  POST /api/runs/replay                replay a recording {"source_run_id": "...", "speed": 1.0}
  GET  /api/runs                       recorded runs, newest first
  GET  /api/runs/{id}/events           server-sent events: history, then live
  GET  /api/runs/{id}/results          all results of a run
  GET  /api/runs/{id}/results/{case}   one result
  GET  /api/runs/{id}/results/{case}/highlights   pages + where each finding sits on them
  GET  /api/cases/{case}/pages/{n}.png  submittal page image (needs the PDF in data/raw/)

The built web app (web/dist) is served at / from the same container.
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .pipeline.cases import all_cases, all_specs
from .pipeline.ingest import highlights, page_png
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


@app.get("/api/runs/{run_id}/results/{case_id}/highlights")
def result_highlights(run_id: str, case_id: str):
    res = load_result(run_id, case_id)
    if res is None or case_id not in all_cases():
        raise HTTPException(404, "No result yet")
    return highlights(all_cases()[case_id], res)


@app.get("/api/cases/{case_id}/pages/{n}.png")
def page_image(case_id: str, n: int):
    if case_id not in all_cases():
        raise HTTPException(404, "Unknown case")
    png = page_png(all_cases()[case_id], n)
    if png is None:
        raise HTTPException(404, "No PDF for this page in data/raw/")
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


def _sse(ev: Event) -> str:
    return f"data: {ev.model_dump_json()}\n\n"


if settings.web_dist.exists():
    app.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="web")

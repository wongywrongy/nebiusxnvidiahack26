"""Runs cases through the pipeline, streams events, and records everything for replay.

A run writes to runs/<run_id>/:
  events.jsonl         every event, in order, with timing (this is the replay recording)
  results/<case>.json  the final result for each case
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import AsyncIterator, Optional

from ..config import settings
from ..schemas import Event, Requirement, Result, Usage
from . import decide, extract, spec_check, verify
from .cases import all_specs, get_case
from .ingest import load_spec_text, load_submittal_pages, submittal_pdfs


class Run:
    def __init__(self, case_ids: list[str], replay_of: Optional[str] = None, delay_ms: Optional[int] = None):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.case_ids = case_ids
        self.replay_of = replay_of
        self.delay_ms = settings.mock_stage_delay_ms if delay_ms is None else delay_ms
        self.events: list[Event] = []
        self.results: dict[str, Result] = {}
        self.done = asyncio.Event()
        self._subscribers: list[asyncio.Queue] = []
        self._t0 = time.perf_counter()
        self.dir = settings.runs_dir / self.id
        (self.dir / "results").mkdir(parents=True, exist_ok=True)

    def emit(self, stage: str, message: str, case_id: Optional[str] = None, model: Optional[str] = None,
             data: Optional[dict] = None, t_ms: Optional[int] = None) -> Event:
        ev = Event(run_id=self.id, case_id=case_id, stage=stage, message=message, model=model, data=data,
                   t_ms=int((time.perf_counter() - self._t0) * 1000) if t_ms is None else t_ms)
        self.events.append(ev)
        with (self.dir / "events.jsonl").open("a") as f:
            f.write(ev.model_dump_json() + "\n")
        for q in self._subscribers:
            q.put_nowait(ev)
        return ev

    async def stream(self) -> AsyncIterator[Event]:
        """All events so far, then live ones until the run finishes."""
        q: asyncio.Queue = asyncio.Queue()
        # Subscribe and snapshot with no await in between, so no event is missed or sent twice.
        self._subscribers.append(q)
        history = list(self.events)
        try:
            for ev in history:
                yield ev
            while not (self.done.is_set() and q.empty()):
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                yield ev
        finally:
            self._subscribers.remove(q)

    async def pause(self) -> None:
        if not settings.live and self.delay_ms:
            await asyncio.sleep(self.delay_ms / 1000)


async def run_case(run: Run, case_id: str, sem: asyncio.Semaphore) -> Result:
    case = get_case(case_id)
    usage: list[Usage] = []
    async with sem:
        t0 = time.perf_counter()
        spec = all_specs()[case["section"]]
        try:
            run.emit("ingest", "Reading the pages", case_id)
            pages = load_submittal_pages(case)
            await run.pause()

            run.emit("triage", "Sorting pages", case_id, settings.models["nano"])
            labels, u = await extract.triage(case_id, pages)
            usage.append(u)
            await run.pause()

            run.emit("extract", "Comparing to the spec", case_id, settings.models["super"])
            reqs, u = await extract.extract_requirements(case["section"], load_spec_text(case["section"], spec))
            usage.append(u)
            # Project-specific conditions (e.g. "penetrant is steel pipe") come from the case cover sheet.
            requirements = reqs.requirements + [Requirement(**c) for c in case.get("conditions", [])]
            skip = set(case.get("not_applicable", []))
            requirements = [r for r in requirements if r.property not in skip]
            props = sorted({r.property for r in requirements})
            claims, u = await extract.extract_claims(case_id, pages, labels, props)
            usage.append(u)

            run.emit("spec_check", "Checking each requirement", case_id, "code")
            findings = spec_check.check(requirements, claims.claims)
            await run.pause()

            run.emit("verify", "Checking the manufacturer online", case_id, f"tavily + {settings.models['super']}")
            vf, rows, u, credits = await verify.verify(case, claims)
            findings += vf
            usage += u
            await run.pause()

            run.emit("reconcile", "Making the call", case_id, settings.models["ultra"])
            findings, u = await decide.reconcile(case_id, findings)
            usage += u
            decision = decide.decide(findings)

            run.emit("report", "Writing the result", case_id, settings.models["super"])
            rep, u = await decide.report(case_id, case["title"], decision, findings)
            usage += u
            await run.pause()

            result = Result(
                case_id=case_id, title=case["title"], decision=decision, summary=rep.summary, findings=findings,
                comparison=rows, claims=claims.claims, document_revision=claims.document_revision,
                document_source="pdf" if settings.live and submittal_pdfs(case) else "fixture",
                note_to_subcontractor=rep.note_to_subcontractor, usage=usage, web_credits=credits,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            (run.dir / "results" / f"{case_id}.json").write_text(result.model_dump_json(indent=2))
            run.results[case_id] = result
            run.emit("done", decision, case_id, data={"decision": decision, "summary": rep.summary})
            return result
        except Exception as e:  # keep the other cases running
            run.emit("error", f"{type(e).__name__}: {e}", case_id)
            raise


async def execute(run: Run) -> Run:
    sem = asyncio.Semaphore(settings.max_concurrency)
    for cid in run.case_ids:
        run.emit("queued", "Waiting", cid)
    await asyncio.gather(*(run_case(run, cid, sem) for cid in run.case_ids), return_exceptions=True)
    run.done.set()
    return run


async def replay(run: Run, source_run_id: str, speed: float = 1.0) -> Run:
    """Re-emit a recorded run's events with their original timing."""
    src = settings.runs_dir / source_run_id
    events = [Event.model_validate_json(line) for line in (src / "events.jsonl").read_text().splitlines() if line]
    start = time.perf_counter()
    for ev in events:
        wait = ev.t_ms / 1000 / speed - (time.perf_counter() - start)
        if wait > 0:
            await asyncio.sleep(wait)
        run.emit(ev.stage, ev.message, ev.case_id, ev.model, ev.data)
    for p in (src / "results").glob("*.json"):
        res = Result.model_validate_json(p.read_text())
        run.results[res.case_id] = res
        (run.dir / "results" / p.name).write_text(p.read_text())
    run.done.set()
    return run


def load_result(run_id: str, case_id: str) -> Optional[Result]:
    p = settings.runs_dir / run_id / "results" / f"{case_id}.json"
    return Result.model_validate_json(p.read_text()) if p.exists() else None


def list_runs() -> list[str]:
    if not settings.runs_dir.exists():
        return []
    return sorted((p.name for p in settings.runs_dir.iterdir() if (p / "events.jsonl").exists()), reverse=True)

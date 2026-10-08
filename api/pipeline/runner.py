"""Runs cases through the pipeline, streams events, and records everything for replay.

A run writes to runs/<run_id>/:
  events.jsonl         every event, in order, with timing (this is the replay recording)
  results/<case>.json  the final result for each case
Live runs recorded for the public demo (scripts/record_live.py) are committed under runs/recorded/<run_id>/.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, Iterable, Optional

from ..config import FORCE_MOCK, redact, settings
from ..providers import budget
from ..providers.budget import BudgetExceeded
from ..schemas import Event, ReportOut, Requirement, Result, Usage
from . import decide, extract, fix, spec_check, verify
from .cases import all_specs, get_case
from .ingest import load_spec_text, load_submittal_pages
from .render import attach_highlights


class Run:
    def __init__(self, case_ids: list[str], delay_ms: Optional[int] = None, mock: Iterable[str] = ()):
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self.case_ids = case_ids
        self.mock = set(mock)  # items forced to mock mode even when the server is live (public uploads)
        self.ledger = budget.Ledger()
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
        ev = Event(run_id=self.id, case_id=case_id, stage=stage, message=redact(message), model=model, data=data,
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
    budget.ITEM.set(case_id)  # this task's own context: credit caps are per item
    FORCE_MOCK.set(case_id in run.mock)
    async with sem:
        t0 = time.perf_counter()
        spec = all_specs()[case["section"]]
        fx = case.get("fixture", case_id)  # which recorded answers mock mode uses; None for an unknown upload
        try:
            run.emit("ingest", "Reading the pages", case_id)
            pages = load_submittal_pages(case)
            if settings.live and not any(p["text"].strip() for p in pages):
                raise RuntimeError("No text in the submittal: the PDF is missing from data/raw/ or is a scan")
            await run.pause()

            run.emit("triage", "Sorting pages", case_id, settings.models["triage"])
            labels, u = await extract.triage(fx, pages)
            usage.append(u)
            await run.pause()

            run.emit("extract", "Comparing to the spec", case_id, settings.models["extract"])
            reqs, u = await extract.requirements_for(case["section"], load_spec_text(case["section"], spec))
            if u:
                usage.append(u)
            # Project-specific conditions (e.g. "penetrant is steel pipe") come from the case cover sheet.
            requirements = reqs.requirements + [Requirement(**c) for c in case.get("conditions", [])]
            skip = set(case.get("not_applicable", []))
            requirements = [r for r in requirements if r.property not in skip]
            props = sorted({r.property for r in requirements})
            claims, u = await extract.extract_claims(fx, pages, labels, props)
            usage.append(u)

            run.emit("spec_check", "Checking each requirement", case_id, "code")
            findings = spec_check.check(requirements, claims.claims, {d["role"] for d in case["submittal"]})
            await run.pause()

            tally = {v: sum(f.verdict == v for f in findings) for v in ("pass", "fail", "unverified")}
            run.emit("verify", "Checking the manufacturer online", case_id, f"tavily + {settings.models['verify']}",
                     data={"spec": tally})
            try:
                vf, rows, u, credits = await verify.verify(case, claims)
                usage += u
            except BudgetExceeded as e:  # this step can't confirm; the rest of the item and the run go on
                vf, rows, credits = [verify.unconfirmed(str(e))], [], run.ledger.credits.get(case_id, 0.0)
            findings += vf
            await run.pause()

            decision = decide.decide(findings)
            ev = next((f.evidence for f in vf if f.evidence), [])
            web = {"sheet": next((f.title for f in vf), ""), "verdict": next((f.verdict for f in vf), ""),
                   "sources": [{"url": e.url, "tier": e.tier} for e in ev]}
            if decision == "send_back":
                run.emit("fix", "Finding a fix", case_id, f"tavily + {settings.models['verify']}", data={"web": web})
                try:
                    u, fix_credits = await fix.find_fixes(case, requirements, claims, findings,
                                                          settings.fix_max_candidates, settings.fix_credit_cap)
                    usage += u
                    credits += fix_credits
                except BudgetExceeded as e:
                    run.emit("fix", f"Couldn't confirm a fix: {e}", case_id)
                    credits = run.ledger.credits.get(case_id, credits)
                await run.pause()

            fixed = next((f.fix for f in findings if f.fix), None)
            run.emit("report", "Writing the result", case_id, settings.models["write"],
                     data={"web": web, **({"fix": fixed.head} if fixed else {})})
            try:
                rep, u = await decide.report(fx, case["title"], decision, findings)
                usage += u
            except BudgetExceeded as e:
                rep = ReportOut(summary=f"Couldn't write the summary: {e}. The decision and findings above stand.",
                                note_to_subcontractor="")
            attach_highlights(case, claims.claims, findings)
            await run.pause()

            result = Result(
                case_id=case_id, title=case["title"], decision=decision, summary=rep.summary, findings=findings,
                comparison=rows, claims=claims.claims, document_revision=claims.document_revision,
                note_to_subcontractor=rep.note_to_subcontractor, usage=usage, web_credits=credits,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )
            (run.dir / "results" / f"{case_id}.json").write_text(result.model_dump_json(indent=2))
            run.results[case_id] = result
            # The run log keeps tokens, cost and credits for every call.
            run.emit("done", decision, case_id, data={"decision": decision, "summary": rep.summary,
                                                      "usage": [u.model_dump() for u in usage], "web_credits": credits})
            return result
        except Exception as e:  # keep the other cases running
            run.emit("error", f"{type(e).__name__}: {e}", case_id)
            raise


async def execute(run: Run) -> Run:
    budget.LEDGER.set(run.ledger)  # inherited by every item task below
    sem = asyncio.Semaphore(settings.max_concurrency)
    for cid in run.case_ids:
        run.emit("queued", "Waiting", cid)
    await asyncio.gather(*(run_case(run, cid, sem) for cid in run.case_ids), return_exceptions=True)
    run.done.set()
    return run


async def replay(run: Run, source_run_id: str, speed: float = 1.0) -> Run:
    """Re-emit a recorded run's events with their original timing."""
    src = run_dir(source_run_id)
    events = [Event.model_validate_json(line) for line in (src / "events.jsonl").read_text().splitlines() if line]
    # Results first: the app fetches each one as soon as its "done" event arrives.
    for p in (src / "results").glob("*.json"):
        res = Result.model_validate_json(p.read_text())
        run.results[res.case_id] = res
        shutil.copy(p, run.dir / "results" / p.name)
    start = time.perf_counter()
    for ev in events:
        wait = ev.t_ms / 1000 / speed - (time.perf_counter() - start)
        if wait > 0:
            await asyncio.sleep(wait)
        run.emit(ev.stage, ev.message, ev.case_id, ev.model, ev.data)
    run.done.set()
    return run


RUN_ID = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")


def run_dir(run_id: str) -> Optional[Path]:
    """A run's folder (runs/<id>, else runs/recorded/<id>), or None. Only well-formed ids: they come from URLs."""
    if not RUN_ID.fullmatch(run_id):
        return None
    return next((d for d in (settings.runs_dir / run_id, settings.recorded_dir / run_id)
                 if (d / "events.jsonl").exists()), None)


def load_result(run_id: str, case_id: str) -> Optional[Result]:
    d = run_dir(run_id)
    p = d / "results" / f"{case_id}.json" if d else None
    return Result.model_validate_json(p.read_text()) if p and p.exists() else None


def _runs_in(folder: Path) -> list[str]:
    return [p.name for p in folder.iterdir() if (p / "events.jsonl").exists()] if folder.exists() else []


def recorded_runs() -> list[str]:
    """Committed live recordings, newest first."""
    return sorted(_runs_in(settings.recorded_dir), reverse=True)


def list_runs() -> list[str]:
    return sorted(_runs_in(settings.runs_dir) + _runs_in(settings.recorded_dir), reverse=True)

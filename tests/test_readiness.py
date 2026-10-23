import asyncio

import httpx
import pytest
import respx
from pydantic import BaseModel

from api.config import settings
from api.pipeline.runner import Run
from api.pipeline.scores import scores
from api.providers import budget, tavily, tokenfactory
from api.readiness import manifest, release_checks
from api.schemas import Diagnostic, Investigation, Result


def test_failed_and_warned_items_remain_in_panel_time_and_spend(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    run = Run(["c01", "c02"])
    run.results["c01"] = Result(case_id="c01", title="test", decision="approve", summary="", findings=[],
                                  validity="invalid", duration_ms=100,
                                  diagnostics=[Diagnostic(stage="verify", kind="provider", message="unavailable")])
    run.attempts["c02"] = {"duration_ms": 1900, "fresh_model_cost_usd": 0.25, "fresh_web_credits": 3}
    run.ledger.fresh_usd = {"c02": 0.25, "extra": 0.5}
    run.ledger.fresh_credits = {"c02": 3, "extra": 5}
    s = scores(run, run.case_ids)
    assert s["right_call"] == {"n": 1, "of": 2}
    assert s["validity"] == {"invalid_items": 2, "requested_items": 2}
    assert s["time_ms_per_item"] == 1000
    assert s["fresh_model_cost_usd"] == 0.25 and s["fresh_web_credits"] == 3
    assert s["run_fresh_spend"] == {"usd": 0.75, "credits": 8}
    assert s["rows"][0]["diagnostics"][0]["stage"] == "verify"
    assert not s["release_gate"]["passed"]


def test_cap_and_replay_cannot_be_used_as_valid_acceptance(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    run = Run(["c01"])
    result = Result(case_id="c01", title="x", decision="approve", summary="", findings=[], validity="valid")
    run.results["c01"] = result
    assert scores(run, ["c01"])["validity"]["invalid_items"] == 0
    assert "No evidenced passing replacement" in release_checks(scores(run, ["c01"]))
    assert "Full scoring set required" in release_checks(scores(run, ["c01"]), minimum_fixes=0, minimum_resolved=0)
    result.investigation = Investigation(outcome="capped")
    assert scores(run, ["c01"])["validity"]["invalid_items"] == 1
    result.investigation = None
    result.replayed_from = "historical"
    assert not scores(run, ["c01"])["rows"][0]["valid"]


def test_manifest_has_no_credentials_and_covers_fix_and_output_limits():
    m = manifest()
    assert m["config"]["max_output_tokens"] == settings.max_output_tokens
    assert m["config"]["fix_credit_cap"] == settings.fix_credit_cap
    assert not any("key" in k or "token" in k and k != "max_output_tokens" for k in m["config"])
    assert len(m["config_hash"]) == len(m["code_hash"]) == 64
    assert set(m["inputs"]) == {"cases", "samples", "specs", "documents", "document_lock"}


class Answer(BaseModel):
    ok: bool


def test_invalid_model_retry_is_charged_even_when_only_success_usage_returns(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    ledger = budget.Ledger()
    lt, it = budget.LEDGER.set(ledger), budget.ITEM.set("retry")
    def reply(text):
        return httpx.Response(200, json={"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                                       "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    try:
        with respx.mock as http:
            route = http.post(settings.nebius_base_url + "chat/completions").mock(
                side_effect=[reply('not JSON'), reply('{"ok":true}')])
            _, usage = asyncio.run(tokenfactory.chat("triage", [], Answer))
            assert len(route.calls) == 2
            assert ledger.fresh_usd["retry"] == 2 * usage.cost_usd
            asyncio.run(tokenfactory.chat("triage", [], Answer))
            assert ledger.fresh_usd["retry"] == 2 * usage.cost_usd
    finally:
        budget.LEDGER.reset(lt)
        budget.ITEM.reset(it)


def test_paid_tavily_response_is_charged_before_result_parsing(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    ledger = budget.Ledger()
    lt, it = budget.LEDGER.set(ledger), budget.ITEM.set("broken")
    try:
        with respx.mock as http:
            http.post(tavily.API + "/search").respond(200, json={"usage": {"credits": 3}, "results": [{}]})
            with pytest.raises(KeyError):
                asyncio.run(tavily.search("x"))
        assert ledger.fresh_credits["broken"] == 3
    finally:
        budget.LEDGER.reset(lt)
        budget.ITEM.reset(it)


@pytest.mark.parametrize("endpoint", ["extract", "map"])
def test_null_tavily_results_still_charge_reported_usage(monkeypatch, tmp_path, endpoint):
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    ledger = budget.Ledger()
    lt, it = budget.LEDGER.set(ledger), budget.ITEM.set("null")
    try:
        with respx.mock as http:
            http.post(tavily.API + "/" + endpoint).respond(200, json={"usage": {"credits": 3}, "results": None})
            call = tavily.extract(["https://manufacturer.example/sheet.pdf"]) if endpoint == "extract" else tavily.map("https://manufacturer.example")
            with pytest.raises(TypeError):
                asyncio.run(call)
        assert ledger.fresh_credits["null"] == 3
    finally:
        budget.LEDGER.reset(lt)
        budget.ITEM.reset(it)


@pytest.mark.parametrize("tools", [False, True])
def test_malformed_reasoning_metadata_does_not_erase_known_spend(monkeypatch, tmp_path, tools):
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    ledger = budget.Ledger()
    lt, it = budget.LEDGER.set(ledger), budget.ITEM.set("malformed")
    try:
        with respx.mock as http:
            http.post(settings.nebius_base_url + "chat/completions").respond(200, json={
                "usage": {"prompt_tokens": 100, "completion_tokens": 20,
                          "completion_tokens_details": {"reasoning_tokens": "unreadable"}}})
            call = tokenfactory.chat_tools("investigate", [], []) if tools else tokenfactory.chat("triage", [], Answer)
            with pytest.raises(ValueError):
                asyncio.run(call)
        assert ledger.fresh_usd["malformed"] > 0
    finally:
        budget.LEDGER.reset(lt)
        budget.ITEM.reset(it)


@pytest.mark.unreported_usage
def test_missing_usage_is_incomplete_not_confirmed_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cache_dir", tmp_path)
    ledger = budget.Ledger()
    lt, it = budget.LEDGER.set(ledger), budget.ITEM.set("unknown")
    try:
        with respx.mock as http:
            http.post(settings.nebius_base_url + "chat/completions").respond(
                200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})
            asyncio.run(tokenfactory.chat("triage", [], Answer))
        assert ledger.accounting_issues["unknown"]
    finally:
        budget.LEDGER.reset(lt)
        budget.ITEM.reset(it)


def test_pending_assembly_cannot_become_all_requirements_passed(monkeypatch):
    from api.pipeline import decide, spec_check
    from api.schemas import Requirement
    req = Requirement(id="a", section="07 84 00", paragraph="x", property="t_rating_hr", operator="eq_ref",
                      value="f_rating_hr", text="T equals F")
    findings = spec_check.check([req], [], {"product_data"})
    report, _ = asyncio.run(decide.report("c01", "test", "approve", findings))
    assert "Assembly proof remains pending" in report.summary
    assert "all requirements" not in report.summary.lower()
    from api.pipeline.fix import _row
    assert _row(findings[0], {"a": req}).ok is None


def test_runner_uses_observed_assembly_kind_for_uploaded_product_data(monkeypatch, tmp_path):
    from api.pipeline import runner
    from api.schemas import ClaimsOut, Requirement, RequirementsOut, TriageOut, Usage
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    case = {"id": "upload", "title": "Uploaded assembly", "section": "07 84 00", "fixture": None,
            "submittal": [{"role": "product_data", "file": "missing-upload.pdf"}]}
    monkeypatch.setattr(runner, "get_case", lambda _: case)
    async def pages(_):
        return [{"page": 1, "text": "Listed system drawing"}]
    async def triage(*_):
        return TriageOut(pages=[{"page": 1, "kind": "system_drawing"}]), Usage(task="triage", tier="triage", model="test")
    async def requirements(*_):
        return RequirementsOut(requirements=[Requirement(id="a", section="07 84 00", paragraph="x", property="t_rating_hr",
            operator="eq_ref", value="f_rating_hr", text="T equals F")]), None
    async def claims(*_):
        return ClaimsOut(product="assembly", manufacturer="maker", claims=[]), [Usage(task="extract_claims", tier="extract", model="test")]
    monkeypatch.setattr(runner, "load_submittal_pages", pages)
    monkeypatch.setattr(runner.extract, "triage", triage)
    monkeypatch.setattr(runner.extract, "requirements_for", requirements)
    monkeypatch.setattr(runner.extract, "extract_claims", claims)
    run = asyncio.run(runner.execute(Run(["upload"], delay_ms=0)))
    assert run.results["upload"].decision == "approve_with_note"
    assert run.results["upload"].findings[0].verdict == "unverified"


def test_scorer_does_not_count_inconsistent_passing_fix(monkeypatch, tmp_path):
    from api.schemas import Finding, Fix, FixCandidate, FixCheck
    monkeypatch.setattr(settings, "runs_dir", tmp_path)
    run = Run(["c02"])
    run.results["c02"] = Result(case_id="c02", title="x", decision="send_back", summary="", validity="valid",
        findings=[Finding(id="x", check="spec", severity="major", verdict="fail", title="x", detail="x", fix=Fix(
            head="x", query="x", candidates=[FixCandidate(name="unsupported", source_url="https://example.com", passes=True,
                checks=[FixCheck(label="unknown", ok=None)])]))])
    assert scores(run, ["c02"])["fixes_passing"]["n"] == 0


def test_failed_attempt_keeps_accounting_reason_and_spend(monkeypatch, tmp_path):
    from api.pipeline import runner
    from api.providers import ProviderError
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    monkeypatch.setattr(settings, "cache_dir", tmp_path / "cache")
    async def failed(*_):
        budget.charge_usd(0.01, real=True)
        budget.unknown_usage("Provider omitted part of the usage")
        raise ProviderError("Invalid response")
    monkeypatch.setattr(runner.extract, "triage", failed)
    run = asyncio.run(runner.execute(Run(["c01"], delay_ms=0)))
    attempt = run.attempts["c01"]
    assert attempt["fresh_model_cost_usd"] == 0.01
    assert {d["stage"] for d in attempt["diagnostics"]} == {"triage", "accounting"}
    score = scores(run, ["c01"])
    assert score["validity"]["invalid_items"] == 1 and score["fresh_model_cost_usd"] == 0.01

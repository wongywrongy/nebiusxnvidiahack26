"""Customer-feedback scaffolding: ordering options that meet spec, ranked alternates, and the package view.

All code-decided and offline: no model or web call is made here.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from api import main
from api.config import settings
from api.pipeline import alternates, package, spec_check
from api.pipeline.cases import all_cases
from api.pipeline.runner import Run, execute
from api.schemas import (Claim, Compare, ConfigOption, Evidence, Finding, Fix, FixCandidate, FixCheck, Requirement,
                         Result)

DIM = Requirement(id="dim", section="26 51 00", paragraph="2.05.C.1", property="dim_min_percent", operator="lte",
                  value=5, unit="%", text="Continuous dimming from 100 to 5 percent")
VOC = Requirement(id="voc", section="07 84 00", paragraph="2.02.B", property="voc_g_per_l", operator="lte",
                  value=250, unit="g/L", text="VOC at most 250 g/L")
WARRANTY = Requirement(id="war", section="26 51 00", paragraph="1.10.B.1", property="warranty_years", operator="gte",
                       value=5, unit="yr", text="Five year warranty")


def claim(cid, prop, value, unit=None, variant=None, quote=None, page=2):
    return Claim(id=cid, product="BLT", manufacturer="Lithonia", property=prop, value=value, unit=unit,
                 variant=variant, scope="option" if variant else "product_wide",
                 quote=quote or f"{variant or ''} {value}".strip(), page=page)


# ---------- configuration to meet spec ----------

def test_word_numbers_compare_like_digits():
    assert spec_check.to_number("zero") == 0 and spec_check.to_number("Two") == 2
    assert spec_check.numeric_compare("zero", None, 0, None, "eq") is True


def test_an_option_that_meets_the_rule_names_what_to_order():
    claims = [claim("k1", "dim_min_percent", 1, "%", variant="EZ1", quote="EZ1 eldoLED dims to 1%"),
              claim("k2", "dim_min_percent", 10, "%", variant="GZ10", quote="GZ10 dims to 10%")]
    [f] = spec_check.check([DIM], claims)
    assert f.verdict == "unverified" and f.title == "Specify option: Dims down to"
    assert [o.option for o in f.configure] == ["EZ1"] and f.configure[0].quote == "EZ1 eldoLED dims to 1%"
    assert f.claim_ids == []  # an option is not evidence that the submitted product meets the rule


def test_no_option_meets_the_rule_keeps_option_not_confirmed():
    claims = [claim("k2", "dim_min_percent", 10, "%", variant="GZ10")]
    [f] = spec_check.check([DIM], claims)
    assert f.title == "Option not confirmed: Dims down to" and f.configure == []


def test_a_selected_option_is_checked_as_the_product_not_as_a_configuration():
    selected = claim("k1", "dim_min_percent", 1, "%", variant="EZ1")
    selected.selection_quote = "Ordered: BLT 2x4 EZ1"
    [f] = spec_check.check([DIM], [selected])
    assert f.verdict == "pass" and f.configure == []


# ---------- ranked alternates ----------

def ev(url="https://maker.test/a.pdf"):
    return [Evidence(url=url, tier="manufacturer", title=url, excerpt="quoted")]


def candidate(name, checks, claims=(), passes=None):
    passes = all(k.ok is True and k.evidence for k in checks) if passes is None else passes
    return FixCandidate(name=name, source_url=f"https://maker.test/{name}.pdf", checks=checks, claims=list(claims),
                        passes=bool(checks) and passes)


def test_alternates_rank_meets_spec_then_possible_then_failed_with_reasons():
    meets = candidate("A", [FixCheck(label="VOC", ok=True, evidence=ev()), FixCheck(label="Still made", ok=True, evidence=ev())])
    possible = candidate("B", [FixCheck(label="VOC", ok=True, evidence=ev()), FixCheck(label="Still made", ok=None)])
    failed = candidate("C", [FixCheck(label="VOC", ok=False, evidence=ev())])
    ranked = alternates.rank([failed, possible, meets], [VOC], [])
    assert [(a.name, a.rank) for a in ranked] == [("A", "meets_spec"), ("B", "possible"), ("C", "failed")]
    assert ranked[1].confirm == ["Still made"] and ranked[2].failed == ["VOC"]


def test_a_check_without_evidence_is_never_meets_spec():
    unsupported = candidate("D", [FixCheck(label="VOC", ok=True, evidence=[])], passes=False)
    [a] = alternates.rank([unsupported], [VOC], [])
    assert a.rank == "possible" and a.confirm == ["VOC"]


def test_better_marks_follow_the_requirement_direction():
    submitted = [claim("s1", "voc_g_per_l", 120, "g/L"), claim("s2", "warranty_years", 5, "yr")]
    alt_claims = [claim("a1", "voc_g_per_l", 40, "g/L"), claim("a2", "warranty_years", 10, "yr")]
    c = candidate("E", [FixCheck(label="VOC", ok=True, evidence=ev())], alt_claims)
    marks = {m.requirement_id: m.mark for m in alternates.better_marks(c, [VOC, WARRANTY], submitted)}
    assert marks == {"voc": "better", "war": "better"}
    weaker = candidate("F", [], [claim("a1", "voc_g_per_l", 200, "g/L")])
    assert [m.mark for m in alternates.better_marks(weaker, [VOC], submitted)] == ["worse"]
    failing = candidate("G", [], [claim("a1", "voc_g_per_l", 300, "g/L")])
    assert [m.mark for m in alternates.better_marks(failing, [VOC], submitted)] == ["worse"]


# ---------- package view ----------

def result(decision, findings):
    return Result(case_id="x", title="Item", decision=decision, summary="", findings=findings)


def finding(fid, check, verdict, severity="major", left=None, title="t", requirement_id="r", configure=()):
    return Finding(id=fid, check=check, verdict=verdict, severity=severity, title=title,
                   requirement_id=requirement_id if check in ("spec", "validity") else None,
                   compare=Compare(left_label="Spec requires", left_value=left, right_label="Submitted",
                                   verdict="fail" if verdict == "fail" else "pass") if left else None,
                   configure=list(configure))


def test_package_row_cells_and_actions_are_derived_in_code():
    discontinued = result("send_back", [
        finding("status-discontinued", "status", "fail"),
        finding("spec-dim", "spec", "unverified", "minor", requirement_id="dim",
                configure=[ConfigOption(option="EZ1", value="1 %", claim_id="k1")]),
    ])
    row = package.row({"title": "LED troffer", "from": "Northgate"}, discontinued)
    assert (row.stamp, row.spec, row.still_made) == ("Revise and resubmit", "configure", "discontinued")
    assert row.what_to_send == ["A current product that meets the spec (this one is discontinued)"]  # option is moot

    t_rating = result("send_back", [finding("spec-t", "spec", "fail", left="T = F (2 hr)")])
    assert package.row({}, t_rating).what_to_send == ["A listed system with T = F (2 hr)"]

    outdated = result("send_back", [finding("currency-outdated", "currency", "outdated")])
    r = package.row({}, outdated)
    assert r.current_sheet == "outdated" and r.what_to_send == ["The manufacturer's current data sheet"]

    unsure = result("approve_with_note", [finding("a", "spec", "unverified", "minor", requirement_id="a"),
                                          finding("b", "spec", "pending", "info", requirement_id="b"),
                                          finding("c", "spec", "pass", "info", requirement_id="c")])
    r = package.row({}, unsure)
    assert (r.meets, r.doesnt_meet, r.couldnt_confirm, r.manual_review_suggested) == (1, 0, 2, True)
    assert package.row({}, result("not_applicable", [])).spec == "not_checked"


def test_a_meets_spec_alternate_leads_the_actions():
    fixed = result("send_back", [finding("currency-outdated", "currency", "outdated")])
    fixed.findings[0].fix = Fix(head="Current sheet found and re-checked", alternates=[
        alternates.Alternate(name="3M IC 15WB+ Rev B", source_url="https://3m.test/b.pdf", rank="meets_spec")])
    assert package.row({}, fixed).what_to_send[0] == "Send 3M IC 15WB+ Rev B (meets the spec)"


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    for name, suffix in (("runs_dir", "runs"), ("recorded_dir", "recorded"), ("cache_dir", "cache"),
                         ("uploads_dir", "uploads")):
        monkeypatch.setattr(settings, name, tmp_path / suffix)
    monkeypatch.setattr(main, "RUNS", {})
    return TestClient(main.app)


def test_package_endpoint_summarizes_a_mock_run(isolated):
    run = asyncio.run(execute(Run(["c01", "c02", "c07"], delay_ms=0)))
    body = isolated.get(f"/api/runs/{run.id}/package").json()
    rows = {r["case_id"]: r for r in body["rows"]}
    assert set(rows) == {"c01", "c02", "c07"} and body["need_changes"] == 2 and body["ready"] == 1
    assert rows["c07"]["still_made"] == "discontinued" and rows["c02"]["spec"] == "fails"
    assert rows["c02"]["title"] == all_cases()["c02"]["title"]
    assert isolated.get("/api/runs/nope/package").status_code == 404


def test_drafts_are_code_templates_with_options_and_alternates():
    configured = result("approve_with_note", [
        finding("spec-dim", "spec", "unverified", "minor", requirement_id="dim", title="Specify option: Dims down to",
                left="≤ 5 %", configure=[ConfigOption(option="EZ1", value="1 %", claim_id="k1")]),
        finding("spec-voc", "spec", "unverified", "minor", requirement_id="voc", title="Couldn't confirm: VOC (air quality)"),
    ])
    r = package.row({"number": "26 51 00-01", "title": "LED troffer"}, configured)
    assert r.what_to_send == ["Specify EZ1 → dims down to 1 % (spec ≤ 5 %)"]
    assert r.approval_note.splitlines() == ["Please review 26 51 00-01 LED troffer for approval: exceptions noted.",
                                            "Specify EZ1 → dims down to 1 % (spec ≤ 5 %)", "Not confirmed: VOC (air quality)."]

    sent = result("send_back", [finding("currency-outdated", "currency", "outdated")])
    sent.findings[0].fix = Fix(head="h", alternates=[
        alternates.Alternate(name="Rev B", source_url="u", rank="possible", confirm=["Still made"])])
    note = package.row({"number": "07 84 00-03"}, sent).return_note
    assert note.splitlines()[-2:] == ["1. The manufacturer's current data sheet",
                                      "Possible alternate to confirm: Rev B (still made)."]
    assert "Acceptable alternate" not in note  # only a meets_spec alternate is called acceptable
    sent.findings[0].fix.alternates[0] = alternates.Alternate(name="Rev B", source_url="u", rank="meets_spec")
    assert package.row({}, sent).return_note.endswith("Acceptable alternate: Rev B.")
    assert package.row({}, result("not_applicable", [])).return_note == ""


def test_a_proposed_configuration_is_named_in_the_draft():
    from api.schemas import Selection
    sent = result("send_back", [finding("status-discontinued", "status", "fail")])
    sent.findings[0].fix = Fix(head="h", candidates=[FixCandidate(
        name="Catalog", source_url="u", passes=True, checks=[],
        selection=Selection(model="ZX-12-D1", page=1, quote="ZX-12-D1", origin="agent_proposal"))],
        alternates=[alternates.Alternate(name="Catalog", source_url="u", rank="meets_spec")])
    assert package.row({}, sent).return_note.endswith(
        "Acceptable alternate: Catalog, configured as ZX-12-D1; confirm before ordering.")


def test_memo_route_serves_the_app(isolated, monkeypatch, tmp_path):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<div id=root></div>")
    monkeypatch.setattr(settings, "web_dist", tmp_path / "dist")
    response = isolated.get("/memo/20261028-000000-abcdef")
    assert response.status_code == 200 and "root" in response.text


def test_still_made_is_not_checked_unless_a_web_check_ran():
    assert package.row({}, result("approve", [finding("a", "spec", "pass", requirement_id="a")])).still_made == "not_checked"
    ran = result("approve_with_note", [finding("currency-newer", "currency", "note")])
    assert package.row({}, ran).still_made == "unknown"
    assert package.row({}, result("not_applicable", [finding("currency-newer", "currency", "note")])).still_made == "not_checked"

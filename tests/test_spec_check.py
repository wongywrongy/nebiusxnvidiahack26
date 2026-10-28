import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.pipeline.spec_check import check, properties_for, to_number  # noqa: E402
from api.pipeline.decide import decide  # noqa: E402
from api.schemas import Claim, Requirement  # noqa: E402


def req(**kw):
    base = {"id": "r", "section": "07 84 00", "paragraph": "", "text": "t"}
    return Requirement(**{**base, **kw})


def claim(prop, value, unit=None, cid="k"):
    return Claim(id=cid, product="p", manufacturer="m", property=prop, value=value, unit=unit)


def test_to_number():
    assert to_number("3/4") == 0.75
    assert to_number("1-1/8") == 1.125
    assert to_number("<2") == 2
    assert to_number("4,312") == 4312
    assert to_number("n/a") is None


def test_extraction_properties_include_references_and_currency_metrics():
    props = properties_for([req(property="measured", operator="eq_ref", value="reference")])
    assert {"measured", "reference", "watts", "lumens", "input_watts_120v", "input_watts_277v"} <= set(props)


def test_gte_pass_and_fail():
    r = req(property="cri", operator="gte", value=80)
    assert check([r], [claim("cri", 82)])[0].verdict == "pass"
    assert check([r], [claim("cri", 70)])[0].verdict == "fail"


def test_eq_ref_t_must_equal_f():
    r = req(property="t_rating_hr", operator="eq_ref", value="f_rating_hr", severity="critical")
    f = check([r], [claim("t_rating_hr", "1/2", "hr", "a"), claim("f_rating_hr", 2, "hr", "b")])[0]
    assert f.verdict == "fail" and f.severity == "critical"


def test_eq_ref_missing_evidence_is_explicit_and_role_scoped():
    r = req(property="t_rating_hr", operator="eq_ref", value="f_rating_hr")
    assert check([r], [claim("f_rating_hr", 4)])[0].verdict == "unverified"
    pending = check([r], [], {"product_data"})
    assert pending[0].verdict == "pending" and decide(pending) == "approve"
    missing = check([r], [], {"system_drawing"})
    assert missing[0].verdict == "unverified" and decide(missing) == "approve_with_note"
    r = req(property="t_rating_hr", operator="eq_ref", value="f_rating_hr", applies_to=["system_drawing"])
    assert check([r], [claim("f_rating_hr", 4)], {"product_data"})[0].verdict == "not_applicable"


def test_contains_listing_coverage():
    r = req(property="penetrant_types", operator="contains", value="steel pipe", check="validity")
    f = check([r], [claim("penetrant_types", ["PVC pipe", "CPVC pipe"])])[0]
    assert f.verdict == "fail" and f.check == "validity"


@pytest.mark.parametrize("operator,submitted,wanted,verdict", [
    ("any_of", ["ASTM E 814"], ["astm e814"], "pass"),
    ("any_of", "UL-1479", ["ul 1479"], "pass"),
    ("any_of", "ul 1479", ["UL\u20111479."], "pass"),
    ("any_of", "DLC-PREMIUM", ["DLC Premium"], "pass"),
    ("any_of", "DesignLights Consortium® (DLC) Premium qualified product", ["dlc premium"], "pass"),
    ("any_of", "UL 1479.1", ["UL 1479"], "fail"),
    ("any_of", ["ASTM E 814 (UL 1479)"], ["astm e814"], "pass"),
    ("any_of", ["ASTM E 814 (UL 1479)"], ["ul 1479"], "pass"),
    ("any_of", ["ASTM E 8145 (UL 14790)"], ["ul 1479"], "fail"),
    ("any_of", "ASTM E 814", ["ASTM E119"], "fail"),
    ("any_of", "UL 14790", ["UL 1479"], "fail"),
    ("any_of", "---", ["..."], "fail"),
    ("contains", ["ASTM E 814 (UL-1479)"], "ul 1479", "pass"),
    ("contains", ["steel-pipe"], " Steel pipe. ", "pass"),
    ("contains", ["PVC pipe"], "steel-pipe", "fail"),
    ("contains", "steel pipe", "---", "fail"),
    ("contains", "UL 14790", "UL 1479", "fail"),
])
def test_text_comparisons_ignore_formatting_without_equating_different_values(operator, submitted, wanted, verdict):
    r = req(property="test_value", operator=operator, value=wanted)
    assert check([r], [claim("test_value", submitted)])[0].verdict == verdict


def test_missing_claim_is_unverified_minor():
    r = req(property="warranty_years", operator="gte", value=5)
    f = check([r], [])[0]
    assert f.verdict == "unverified" and f.severity == "minor"


@pytest.mark.parametrize("property,operator,value", [
    ("astm_g21_rating", "eq", 0), ("l70_hours", "gte", 50000), ("macadam_steps", "lte", 3),
])
def test_missing_reviewed_property_is_a_note_not_a_spec_failure(property, operator, value):
    findings = check([req(property=property, operator=operator, value=value)], [])
    assert len(findings) == 1 and findings[0].verdict == "unverified"
    assert findings[0].title.startswith("Couldn't confirm:")
    assert findings[0].compare.right_value == "Not confirmed" and findings[0].compare.verdict == "unverified"
    assert decide(findings) == "approve_with_note"
    assert decide(findings, {"upload": True}) == "not_applicable"


def test_exists_without_a_claim_cannot_send_back_the_submittal():
    r = req(property="input_watts", operator="exists", severity="critical")
    findings = check([r], [])
    assert findings[0].verdict == "unverified" and findings[0].severity == "minor"
    assert decide(findings) == "approve_with_note"
    assert decide(findings, {"upload": True}) == "not_applicable"
    assert check([r], [claim("input_watts", 30)])[0].verdict == "pass"


def test_a_warranty_match_alone_does_not_put_an_upload_in_scope():
    # A door lock checked against a lighting spec: only its warranty matched (measured live, 2026-10-28).
    rules = [req(id="w", property="warranty_years", operator="gte", value=5, unit="yr"),
             req(id="l70", property="l70_hours", operator="gte", value=50000, unit="hr")]
    findings = check(rules, [claim("warranty_years", 7, "yr", cid="warranty_years-1")])
    assert [f.verdict for f in findings] == ["pass", "unverified"]
    assert decide(findings, {"upload": True}, rules) == "not_applicable"
    assert decide(findings, None, rules) == "approve_with_note"  # the test set and tray keep their decisions
    in_scope = check(rules, [claim("warranty_years", 7, "yr", cid="a"), claim("l70_hours", 60000, "hr", cid="b")])
    assert decide(in_scope, {"upload": True}, rules) == "approve"
    only_warranty = [rules[0]]
    assert decide(check(only_warranty, [claim("warranty_years", 7, "yr")]), {"upload": True}, only_warranty) == "approve"

def test_unit_conversion_mm_to_in():
    r = req(property="max_annular_space_in", operator="lte", value=1, unit="in")
    assert check([r], [claim("max_annular_space_in", 20, "mm")])[0].verdict == "pass"


@pytest.mark.parametrize("values,verdict", [([1, 10], "unverified"), ([1, 2], "pass"), ([10, 20], "fail")])
def test_numeric_alternatives_do_not_choose_a_variant(values, verdict):
    r = req(property="measurement", operator="lte", value=5)
    claims = [claim("measurement", v, cid=str(i)) for i, v in enumerate(values)]
    finding = check([r], claims)[0]
    assert finding.verdict == verdict
    if verdict == "unverified":
        assert finding.severity == "minor" and "configuration" in finding.detail


def test_rating_alternatives_are_not_their_first_number():
    r = req(property="t_rating_hr", operator="eq_ref", value="f_rating_hr")
    f = check([r], [claim("t_rating_hr", "0-HR., 1-HR., OR 2-HR."), claim("f_rating_hr", "1-HR. OR 2-HR.")])[0]
    assert f.verdict == "unverified"


def test_categorical_prefix_can_be_grounded_by_its_exact_quote():
    r = req(property="classification", operator="any_of", value=["group premium"])
    c = claim("classification", "Premium")
    c.quote = "Group Premium qualified product"
    assert check([r], [c])[0].verdict == "pass"
    c.quote = "Other Premium qualified product"
    c.value = "Other Premium"
    assert check([r], [c])[0].verdict == "fail"


@pytest.mark.parametrize("value,quote,verdict", [
    ("A12 Series", "A12 Series", "pass"),
    ("A12 Series", "Maker A12 Series", "pass"),
    ("Other B20", "Other B20", "fail"),
])
def test_incomplete_named_identifier_is_unknown_not_a_definite_mismatch(value, quote, verdict):
    r = req(property="lock_series", operator="any_of", value=["Maker A12 Series"])
    c = claim("lock_series", value)
    c.quote = quote
    assert check([r], [c])[0].verdict == verdict


@pytest.mark.parametrize("submitted,allowed,verdict", [
    ("ND Series", "Schlage ND series", "pass"),
    ("ND Series", "Corbin CL3300", "fail"),
    ("NDX", "ND", "fail"),
    ("SCHLAGE ND model", "nd", "pass"),
    ("series model line", "ND", "fail"),
])
def test_named_series_match_distinguishing_tokens_without_prefix_matches(submitted, allowed, verdict):
    r = req(property="lock_series", operator="any_of", value=[allowed])
    c = claim("lock_series", submitted)
    c.quote = submitted
    assert check([r], [c])[0].verdict == verdict


def test_product_type_scope_is_optional_and_preserves_shared_rules():
    rules = [req(id="lock", property="grade", operator="eq", value=1, product_type="cylindrical lockset"),
             req(id="closer", property="grade", operator="eq", value=2, product_type="door closer"),
             req(id="shared", property="grade", operator="eq", value=1)]
    fs = check(rules, [claim("grade", 1)], product_type="Cylindrical Lockset")
    assert [f.verdict for f in fs] == ["pass", "not_applicable", "pass"]
    assert not fs[1].claim_ids and fs[1].product_type == "door closer"
    assert [f.verdict for f in check(rules, [claim("grade", 1)])] == ["pass", "fail", "pass"]


def test_option_value_does_not_fail_an_unspecified_configuration():
    r = req(property="measurement", operator="lte", value=5, severity="major")
    c = claim("measurement", 10)
    c.variant = "Optional driver"
    c.scope = "option"
    c.quote = "Optional driver: measurement 10"
    f = check([r], [c])[0]
    assert f.verdict == "unverified" and f.severity == "minor"
    assert "Optional driver" in f.detail

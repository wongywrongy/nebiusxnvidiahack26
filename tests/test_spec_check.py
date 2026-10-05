import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.pipeline.spec_check import check, to_number  # noqa: E402
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


def test_gte_pass_and_fail():
    r = req(property="cri", operator="gte", value=80)
    assert check([r], [claim("cri", 82)])[0].verdict == "pass"
    assert check([r], [claim("cri", 70)])[0].verdict == "fail"


def test_eq_ref_t_must_equal_f():
    r = req(property="t_rating_hr", operator="eq_ref", value="f_rating_hr", severity="critical")
    f = check([r], [claim("t_rating_hr", "1/2", "hr", "a"), claim("f_rating_hr", 2, "hr", "b")])[0]
    assert f.verdict == "fail" and f.severity == "critical"


def test_eq_ref_skipped_when_not_applicable():
    r = req(property="t_rating_hr", operator="eq_ref", value="f_rating_hr")
    assert check([r], [claim("f_rating_hr", 4)]) == []


def test_contains_listing_coverage():
    r = req(property="penetrant_types", operator="contains", value="steel pipe", check="validity")
    f = check([r], [claim("penetrant_types", ["PVC pipe", "CPVC pipe"])])[0]
    assert f.verdict == "fail" and f.check == "validity"


def test_missing_claim_is_unverified_minor():
    r = req(property="warranty_years", operator="gte", value=5)
    f = check([r], [])[0]
    assert f.verdict == "unverified" and f.severity == "minor"


def test_unit_conversion_mm_to_in():
    r = req(property="max_annular_space_in", operator="lte", value=1, unit="in")
    assert check([r], [claim("max_annular_space_in", 20, "mm")])[0].verdict == "pass"

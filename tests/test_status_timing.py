from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from api import release
from api.pipeline import verify
from api.pipeline.decide import decide
from api.schemas import ClaimsOut, Evidence, VerifyOut


URL = "https://maker.test/notice"


def submitted():
    return ClaimsOut(product="ZX-7", manufacturer="Synthetic maker", model="ZX-7", family="ZX", claims=[])


@pytest.mark.parametrize("quote,expected,date", [
    ("As of May 1, 2035, the ZX family will be discontinued.", "unknown", None),
    ("The ZX family will be discontinued on 2035-05-01.", "unknown", None),
    ("The ZX family will be discontinued effective 1 May 2035.", "unknown", None),
    ("The ZX family is discontinued as of May 1, 2035.", "unknown", None),
    ("As of 2035, the ZX family is discontinued.", "unknown", None),
    ("The ZX family is discontinued in 2035.", "unknown", None),
    ("The ZX family is discontinued on 05/01/2035.", "unknown", None),
    ("As of May 1, 2001, the ZX family will be discontinued. Replacement documentation follows.", "discontinued", "2001-05-01"),
    ("As of May 1st, 2001, the ZX family will be discontinued.", "discontinued", "2001-05-01"),
    ("The ZX family will be discontinued on 2001-05-01.", "discontinued", "2001-05-01"),
    ("The ZX family will be discontinued May 1, 2001.", "discontinued", "2001-05-01"),
    ("Notice: As of May 1, 2001, the ZX family will be discontinued.", "discontinued", "2001-05-01"),
    ("The ZX family will be discontinued.", "unknown", None),
    ("Published on May 1, 2001, the ZX family will be discontinued.", "unknown", None),
    ("As of May 1, 2035, the ZX family will be discontinued on May 1, 2001.", "unknown", None),
    ("As of February 30, 2001, the ZX family will be discontinued.", "unknown", None),
])
def test_planned_discontinuation_needs_a_grounded_effective_date(monkeypatch, quote, expected, date):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2030, 6, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(verify, "datetime", Clock, raising=False)
    out = VerifyOut(status="discontinued", status_date="1999-01-01", status_family="ZX", status_quote=quote)
    pages = [{"url": URL, "raw_content": quote}]
    product = submitted()
    confirmed = verify.gate(out, pages, submitted=product)
    findings, _ = verify.compare(product, out, confirmed, [], pages)
    assert out.status == expected and out.status_date == date
    assert (decide(findings) == "send_back") is (expected == "discontinued")
    if expected == "unknown":
        assert out.status_quote is None and not any(f.check == "status" and f.verdict == "fail" for f in findings)


def test_undated_present_statement_does_not_borrow_an_invented_date():
    quote = "The ZX family is discontinued."
    out = VerifyOut(status="discontinued", status_date="2035-05-01", status_family="ZX", status_quote=quote)
    verify.gate(out, [{"url": URL, "raw_content": quote}], submitted=submitted())
    assert out.status == "discontinued" and out.status_date is None


@pytest.mark.parametrize("status,quote", [
    ("discontinued", "As of May 1, 2095, the ZX family will be discontinued."),
    ("active", "The ZX family is available until Q4 2001."),
    ("active", "The ZX family is available through FY2001."),
    ("active", "The ZX family is available until end of 2001."),
])
def test_release_replays_the_temporal_gate(monkeypatch, status, quote):
    product = submitted()
    output = VerifyOut(status=status, status_family="ZX",
                       status_date="2095-05-01" if status == "discontinued" else None, status_quote=quote)
    proof = SimpleNamespace(submitted=product, output=output, sources=[Evidence(url=URL, title="Synthetic notice", tier="manufacturer")])
    monkeypatch.setattr(release, "_archived", lambda *args: [quote])
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="Saved verification values do not survive"):
        release._verification(proof, product, now, now)


@pytest.mark.parametrize("quote,replacement,expected", [
    ("The ZX family is discontinued.", "XR-9", None),
    ("The ZX family is discontinued. Replaced by XR-9.", "XR-9", "XR-9"),
])
def test_replacement_metadata_needs_its_actual_status_quote(quote, replacement, expected):
    out = VerifyOut(status="discontinued", status_family="ZX", status_quote=quote, replacement=replacement)
    verify.gate(out, [{"url": URL, "raw_content": quote + " Other product XR-9."}], submitted=submitted())
    assert out.status == "discontinued" and out.replacement == expected


@pytest.mark.parametrize("quote,expected", [
    ("The ZX family is available from May 1, 2035.", "unknown"),
    ("As of May 1, 2035, the ZX family is available.", "unknown"),
    ("The ZX family is available in 2035.", "unknown"),
    ("The ZX family is available tomorrow.", "unknown"),
    ("The ZX family is available until May 1, 2001.", "unknown"),
    ("The ZX family is available until Q4 2001.", "unknown"),
    ("The ZX family is available through FY2001.", "unknown"),
    ("The ZX family is available until end of 2001.", "unknown"),
    ("The ZX family is available until May 1, 2095.", "active"),
    ("The ZX family is available through 2095-05-01.", "active"),
    ("The ZX family is available from May 1, 2001.", "active"),
    ("As of May 1, 2001, the ZX family is available until May 1, 2095.", "active"),
    ("As of May 1, 2095, the ZX family is available until May 1, 2001.", "unknown"),
    ("The ZX family is available in all sizes.", "active"),
    ("The ZX family is available from stock.", "active"),
    ("The ZX family is available through distributors.", "active"),
    ("The ZX family is available until further notice.", "active"),
])
def test_availability_dates_do_not_become_an_early_or_expired_pass(quote, expected):
    out = VerifyOut(status="active", status_date="2035-05-01", status_family="ZX", status_quote=quote)
    verify.gate(out, [{"url": URL, "raw_content": quote}], submitted=submitted())
    assert out.status == expected and out.status_date is None

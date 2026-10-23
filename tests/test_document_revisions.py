import pytest

from api.pipeline import verify
from api.schemas import Claim, ClaimsOut, Evidence, PropertyValue, VerifyOut


PRODUCT = ClaimsOut(product="Product X", model="X", manufacturer="Maker", document_revision="Rev A", claims=[])
SDS = "Model X. Safety Data Sheet. Version Rev B. SECTION 1: Identification. VOC content 10 g/L."
TDS = "Model X. Technical Data Sheet. Rev A. Refer to the Safety Data Sheet for precautions."


@pytest.mark.parametrize("document", [SDS, SDS.replace("Safety Data Sheet", "MATERIAL SAFETY DATA SHEET")])
def test_safety_revision_cannot_replace_a_technical_sheet_revision(document):
    out = VerifyOut(status="unknown",current_revision="Rev B")
    pages = [{"url":"https://maker.test/safety.pdf", "raw_content":document},
             {"url":"https://maker.test/technical.pdf", "raw_content":TDS}]
    confirmed = verify.gate(out, pages, submitted=PRODUCT)
    findings, rows = verify.compare(PRODUCT, out, confirmed, [], pages)
    assert out.current_revision is None and not rows
    assert findings[0].verdict == "unverified"


def test_safety_sheet_reference_does_not_erase_an_actual_technical_revision():
    technical, safety = "https://maker.test/data.pdf", "https://maker.test/safety.pdf"
    pages = [{"url":technical,"raw_content":TDS},{"url":safety,"raw_content":SDS}]
    out = VerifyOut(status="unknown",current_revision="Rev A")
    evidence = [Evidence(url=p["url"], tier="manufacturer", title="Source") for p in pages]
    confirmed = verify.gate(out, pages, submitted=PRODUCT)
    findings, _ = verify.compare(PRODUCT, out, confirmed, evidence, pages)
    assert out.current_revision == "Rev A"
    assert findings[0].title == "Source revision matches the submitted revision"
    assert [(e.url,e.excerpt) for e in findings[0].evidence] == [(technical,"Rev A")]


@pytest.mark.parametrize("current", [10,15])
def test_rejecting_a_safety_revision_preserves_its_valid_property_quote(current):
    url = "https://maker.test/safety.pdf"
    quote = f"VOC content {current} g/L"
    product = PRODUCT.model_copy(update={"claims":[Claim(id="v",product="X",manufacturer="Maker",
        property="voc_g_per_l",value=10,unit="g/L",quote=quote)]})
    out = VerifyOut(status="unknown",current_revision="Rev B",current_values=[PropertyValue(property="voc_g_per_l",value=current,
        unit="g/L",quote=quote,source_url=url,model="X",identity_quote="Model X",
        scope="product_wide",scope_quote=quote)])
    pages=[{"url":url,"raw_content":SDS.replace("VOC content 10",f"VOC content {current}")}]
    confirmed = verify.gate(out,pages,submitted=product)
    findings, rows = verify.compare(product,out,confirmed,[Evidence(url=url,tier="manufacturer",title="Safety")],pages)
    assert out.current_revision is None and len(out.current_values)==len(rows)==1
    if current == 10:
        assert findings[0].title == "Compared values match current sources"
        assert findings[0].evidence[0].excerpt == quote
    else:
        assert findings[0].verdict == "outdated" and rows[0].changed
        assert "None" not in findings[0].detail and "unknown" in findings[0].detail


def test_revision_only_source_does_not_claim_to_match_an_undated_submission():
    out=VerifyOut(status="unknown",current_revision="Rev A")
    product=PRODUCT.model_copy(update={"document_revision":None})
    pages=[{"url":"https://maker.test/data.pdf","raw_content":TDS}]
    confirmed=verify.gate(out,pages,submitted=product)
    findings, rows=verify.compare(product,out,confirmed,[],pages)
    assert not rows and findings[0].title == "Current-source revision found"

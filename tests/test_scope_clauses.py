import asyncio

import pytest

from api.pipeline import extract, spec_check, verify
from api.release import _claims
from api.schemas import Claim, ClaimsOut, Requirement, Usage, VerifyOut

LIFE = "L60 > 64,000 hours."
OTHER = "L95 > 96,000 hours with GF option."
MACADAM = "All CCTs are within 2 MacAdam ellipses."


@pytest.mark.parametrize("property,quote", [("l60_hours",LIFE),("macadam_steps",MACADAM),
                                           ("warranty_years","Warranty 7 years.")])
def test_separate_lifetime_condition_does_not_limit_an_unqualified_metric(property, quote):
    passage = quote + " " + OTHER
    assert extract.scope_is_product_wide("product_wide",passage,quote,property)
    assert not extract.scope_is_product_wide("product_wide",passage,quote)  # Unknown metric stays conservative.


@pytest.mark.parametrize("condition", [
    "L60 > 64,000 hours with GF option.", "All values apply only to selected models.",
    "Not all versions are qualified.", "GF option only.", "Optional: " + OTHER,
    OTHER + " Some models only.", "DRB7 2 % Driver with external dimming wires",
    "L95 > 96,000 hours with GF option that applies to all metrics.",
])
def test_own_shared_or_ambiguous_conditions_remain_unconfirmed(condition):
    assert not extract.scope_is_product_wide("product_wide",LIFE+" "+condition,LIFE,"l60_hours")


def test_a_value_quote_spanning_the_conditional_metric_cannot_become_product_wide():
    passage = LIFE + " " + OTHER
    assert not extract.scope_is_product_wide("product_wide",passage,passage,"l60_hours")
    assert not extract.scope_is_product_wide("option",passage,LIFE,"l60_hours")


def test_clause_binding_survives_extraction_web_and_release_claim_gates(monkeypatch):
    passage = LIFE + " " + OTHER + " " + MACADAM
    driver = "DRB7 2 % Driver with external dimming wires"
    text = "Model ZX-1. " + passage + " " + driver
    claims = [Claim(id=str(n),product="ZX-1",manufacturer="Synthetic maker",model="ZX-1",property=prop,
        value=value,unit=unit,page=1,quote=quote,scope="product_wide",scope_quote=scope)
        for n,(prop,value,unit,quote,scope) in enumerate([
            ("l60_hours",">64000","hr",LIFE,passage), ("macadam_steps",2,None,MACADAM,passage),
            ("dim_min_percent",2,"%",driver,driver)])]
    async def read(*args):
        return ClaimsOut(product="ZX-1",manufacturer="Synthetic maker",model="ZX-1",claims=claims), Usage(
            task="extract_claims",tier="extract",model="synthetic")
    monkeypatch.setattr(extract,"_read_claims",read)
    pages = [{"page":1,"text":text}]
    extracted,_ = asyncio.run(extract.extract_claims(None,pages,extract.all_product_data(pages),[c.property for c in claims]))
    requirements = [Requirement(id=c.id,section="test",paragraph="",property=c.property,operator=op,value=value,
                               unit=c.unit,text="Synthetic limit") for c,op,value in zip(claims,("gte","lte","lte"),(60000,4,4))]
    assert [f.verdict for f in spec_check.check(requirements,extracted.claims,{"product_data"})] == ["pass","pass","unverified"]
    assert extracted.selection is None and extracted.claims[-1].variant == "DRB7"
    _claims(extracted,extracted.claims,None,{1:text})
    url = "https://maker.test/ZX-1.pdf"
    out = VerifyOut(status="unknown",current_values=[dict(property=c.property,value=c.value,unit=c.unit,quote=c.quote,
        scope=c.scope,scope_quote=c.scope_quote,variant=c.variant,source_url=url,model="ZX-1",identity_quote="Model ZX-1")
        for c in extracted.claims])
    sources = [{"url":url,"raw_content":text}]
    confirmed = verify.gate(out,sources,submitted=extracted)
    _,rows = verify.compare(extracted,out,confirmed,[],sources)
    assert {row.property for row in rows} == {"l60_hours","macadam_steps"}
    assert not any(row.changed for row in rows)

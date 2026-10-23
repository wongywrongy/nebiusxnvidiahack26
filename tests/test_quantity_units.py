import asyncio

import pytest

from api.pipeline import extract, spec_check, verify
from api.release import _claims
from api.schemas import Claim, ClaimsOut, Requirement, Usage, VerifyOut


@pytest.mark.parametrize("property,value,quote,required_unit", [
    ("dim_min_percent",0,"Dimming control interface: 0-12 V.","%"),
    ("l60_hours",64000,"L60 lifetime 64,000 cycles.","hr"),
    ("warranty_years",8,"Warranty 8 days.","yr"),
    ("voc_g_per_l",8,"VOC content 8%.","g/L"),
    ("t_rating_hr",8,"T Rating 8 min.","hr"),
])
def test_missing_quantity_unit_cannot_pass_extraction_web_spec_or_release(monkeypatch,property,value,quote,required_unit):
    text="Model ZX-9. "+quote
    claim=Claim(id="q",product="ZX-9",manufacturer="Synthetic maker",model="ZX-9",property=property,
        value=value,unit=None,page=1,quote=quote,scope="product_wide",scope_quote=quote)
    forged=ClaimsOut(product="ZX-9",manufacturer="Synthetic maker",model="ZX-9",claims=[claim])
    async def read(*args):
        return forged.model_copy(deep=True),Usage(task="extract_claims",tier="extract",model="synthetic")
    monkeypatch.setattr(extract,"_read_claims",read)
    pages=[{"page":1,"text":text}]
    result,_=asyncio.run(extract.extract_claims(None,pages,extract.all_product_data(pages),[property]))
    assert result.claims==[]
    req=Requirement(id="q",section="synthetic",paragraph="",property=property,operator="lte",value=value,
        unit=required_unit,text="Synthetic quantity limit")
    assert spec_check.check([req],result.claims,{"product_data"})[0].verdict=="unverified"
    url="https://maker.test/ZX-9.pdf"
    out=VerifyOut(status="unknown",current_values=[dict(property=property,value=value,unit=None,quote=quote,
        model="ZX-9",identity_quote="Model ZX-9",scope="product_wide",scope_quote=quote,source_url=url)])
    verify.gate(out,[{"url":url,"raw_content":text}],submitted=result)
    assert out.current_values==[]
    with pytest.raises(ValueError,match="identity, value and quote"):
        _claims(forged,forged.claims,None,{1:text})


@pytest.mark.parametrize("property,quote", [
    ("cri","CRI 82"), ("macadam_steps","2 MacAdam ellipses"),
    ("astm_g21_rating","ASTM G21 Rating 2"), ("standards","Tested to synthetic standard"),
])
def test_dimensionless_and_categorical_claims_still_allow_no_unit(property,quote):
    assert extract.unit_quoted(None,quote,property)


def test_explicit_convertible_units_remain_valid():
    assert extract.unit_quoted("min","T Rating 8 min.","t_rating_hr")
    claim=Claim(id="t",product="ZX-9",manufacturer="Synthetic maker",property="t_rating_hr",value=8,unit="min")
    req=Requirement(id="t",section="synthetic",paragraph="",property="t_rating_hr",operator="gte",value=0.1,
                    unit="hr",text="Synthetic time limit")
    assert spec_check.check([req],[claim],{"product_data"})[0].verdict=="pass"


@pytest.mark.parametrize("quote,accepted", [
    ("Dimming control interface: 0-12 V.",False), ("Energy savings 8%.",False),
    ("Dims down to 7%.",True), ("7 percent minimum dimming.",True),
    ("DIM7 7% driver",True),
])
def test_dimming_metric_needs_a_percentage_and_dimming_context(quote,accepted):
    assert extract.metric_quoted("dim_min_percent",quote) is accepted

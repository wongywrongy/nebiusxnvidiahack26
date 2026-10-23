import asyncio

import pytest

from api.pipeline import fix
from api.schemas import Claim, ClaimsOut, Evidence, Finding, Requirement
from api.web import WebClient


@pytest.mark.parametrize("mode", ["omitted", "duplicate", "conflicting", "foreign"])
def test_supplements_preserve_original_evidence_and_cannot_hide_conflicts(monkeypatch, mode):
    primary, supplement = "https://maker.test/product.pdf", "https://maker.test/support.pdf"
    text = "Model X. Rev A. Warranty 5 years"
    source = {"url":primary, "raw_content":text, "pages":[{"page":3,"text":text}]}
    extra = "Model X. CRI 80. Warranty 2 years. Model Y"
    calls = []
    async def search(*args, **kwargs):
        return [{"url":primary,"title":"Model X data"}]
    async def fetch(*args, **kwargs):
        return [source]
    def warranty(value, page):
        quote = f"Warranty {value} years"
        return Claim(id="proof",product="X",manufacturer="Maker",property="warranty_years",value=value,
                     unit="yr",page=page,quote=quote,scope="product_wide",scope_quote=quote)
    async def claims(fx, pages, labels, props):
        calls.append(pages)
        if len(calls) == 1:
            values = [warranty(5,3)]
        else:
            page = next(p["page"] for p in pages if "CRI 80" in p["text"])
            values = [Claim(id="proof",product="Y" if mode=="foreign" else "X",manufacturer="Maker",
                property="cri",value=80,page=page,quote="CRI 80",scope="unknown" if mode=="foreign" else "product_wide",
                scope_quote="CRI 80",variant="Model Y" if mode=="foreign" else None)]
            if mode in ("duplicate","conflicting"):
                values.insert(0,warranty(5 if mode=="duplicate" else 2,3 if mode=="duplicate" else page))
        return ClaimsOut(product="X",manufacturer="Maker",model="X",claims=values), []
    async def verify(case, submitted, **kwargs):
        kwargs["on_sources"]([{"url":supplement,"raw_content":extra}])
        evidence=[Evidence(url=primary,tier="manufacturer",title="Synthetic",excerpt="Rev A")]
        return [Finding(id="currency-current",check="currency",verdict="pass",severity="info",title="Current",evidence=evidence),
                Finding(id="status-active",check="status",verdict="pass",severity="info",title="Available",evidence=evidence)], [], [], 0, None
    monkeypatch.setattr(WebClient,"search",search)
    monkeypatch.setattr(WebClient,"extract",fetch)
    monkeypatch.setattr(fix.extract,"extract_claims",claims)
    monkeypatch.setattr(fix.verify,"verify",verify)
    requirements=[Requirement(id="w",section="test",paragraph="",property="warranty_years",operator="gte",value=5,unit="yr",text="Warranty"),
                  Requirement(id="c",section="test",paragraph="",property="cri",operator="gte",value=80,text="Color")]
    case={"id":"synthetic-retention","fixture":None,"title":"Luminaire","submittal":[{"role":"product_data"}],"manufacturer_domains":["maker.test"]}
    old=Finding(id="old",check="status",verdict="fail",severity="major",title="Old")
    result,_,_=asyncio.run(fix._fix(case,"currency",[old],requirements,ClaimsOut(product="X",manufacturer="Maker",claims=[]),1,40))
    candidate,=result.candidates
    assert candidate.passes is (mode in ("omitted","duplicate"))
    assert set(candidate.page_sources)=={3,4} and [p["page"] for p in calls[-1]]==[3,4]
    assert len({c.id for c in candidate.claims})==len(candidate.claims)
    warranty_check,color=candidate.checks[:2]
    assert warranty_check.ok is (None if mode=="conflicting" else True)
    assert any(e.url==primary and e.excerpt=="Warranty 5 years" for e in warranty_check.evidence)
    if mode=="foreign":
        assert color.ok is None and not color.evidence
    else:
        assert color.ok and color.evidence[0].url==supplement
    if mode=="duplicate":
        assert sum(c.property=="warranty_years" for c in candidate.claims)==1

import asyncio

import pytest

from api.pipeline import fix
from api.schemas import Claim, ClaimsOut, Evidence, Finding, Requirement, Selection
from api.web import WebClient


@pytest.mark.parametrize("current_revision,passes", [("Rev A", True), (None, False)])
@pytest.mark.parametrize("correcting_status", [False, True])
@pytest.mark.parametrize("availability_present", [False, True])
@pytest.mark.parametrize("identity_changes", [False, True])
@pytest.mark.parametrize("selection_lost", [False, True])
def test_replacement_bundle_has_at_most_three_matching_documents_and_per_check_quotes(monkeypatch, current_revision, passes, correcting_status, availability_present, identity_changes, selection_lost):
    primary = "https://maker.test/product.pdf"
    extracted_pages = []
    source = {"url": primary, "raw_content": "Model X. Rev A. Warranty 5 years" +
              (" Model X is currently available." if availability_present else ""),
              "retrieved_at":"2026-10-23T00:00:00+00:00", "archived_path":"synthetic/source.txt", "cache_hit":True}
    supplements = [
        {"url": "https://maker.test/neighbor", "raw_content": "Model X200. CRI 20"},
        {"url": "https://maker.test/photometry", "raw_content": "Model X. CRI 80"},
        {"url": "https://maker.test/third", "raw_content": "Model X. More data"},
        {"url": "https://maker.test/fourth", "raw_content": "Model X. Other data"},
    ]
    async def search(*args, **kwargs):
        return [{"url": primary, "title": "Model X current sheet"}]
    async def extract(*args, **kwargs):
        return [source]
    async def claims(fx, pages, labels, props):
        extracted_pages.append(pages)
        values = [Claim(id="w", product="X", manufacturer="Maker", property="warranty_years",
                        value=5, unit="yr", page=1, quote="Warranty 5 years")]
        for page in pages:
            if "CRI 80" in page["text"]:
                values.append(Claim(id="c", product="X", manufacturer="Maker", property="cri",
                                    value=80, page=page["page"], quote="CRI 80"))
        model = "Y" if identity_changes and len(extracted_pages) > 1 else "X"
        selection = Selection(model="X EZ1", page=1, quote="Selected: X EZ1") if selection_lost and len(extracted_pages) == 1 else None
        return ClaimsOut(product=model, manufacturer="Maker", model=model, selection=selection, document_revision=current_revision, claims=values), []
    async def verify(case, claims, **kwargs):
        kwargs["on_sources"](supplements)
        evidence = [Evidence(url=primary, title="Current", tier="manufacturer", excerpt="Rev A")] if current_revision else []
        findings = [Finding(id="currency-current", check="currency", verdict="pass", severity="info", title="Current", evidence=evidence)]
        if availability_present:
            findings.append(Finding(id="status-active", check="status", verdict="pass", severity="info", title="Available",
                evidence=[Evidence(url=primary, title="Available", tier="manufacturer", excerpt="Model X is currently available.")]))
        return findings, [], [], 0, None
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    monkeypatch.setattr(fix.extract, "extract_claims", claims)
    monkeypatch.setattr(fix.verify, "verify", verify)
    reqs = [Requirement(id="w", section="26 51 00", paragraph="", property="warranty_years", operator="gte", value=5, unit="yr", text="Warranty"),
            Requirement(id="c", section="26 51 00", paragraph="", property="cri", operator="gte", value=80, text="Color")]
    case = {"id": "test", "fixture": None, "title": "Luminaire", "submittal": [{"role": "product_data"}], "manufacturer_domains": ["maker.test"]}
    old = Finding(id="old", check="status" if correcting_status else "currency", verdict="fail" if correcting_status else "outdated", severity="major", title="Old")
    result, _, _ = asyncio.run(fix._fix(case, "currency", [old], reqs,
        ClaimsOut(product="X", manufacturer="Maker", claims=[]), 1, 40))
    candidate, = result.candidates
    assert candidate.passes is (passes and availability_present and not identity_changes and not selection_lost)
    if not availability_present:
        assert any(c.label == "Still made" and c.ok is None for c in candidate.checks)
    assert len(candidate.documents) == len(extracted_pages[-1]) == 3
    assert not any("neighbor" in e.url or "fourth" in e.url for e in candidate.documents)
    warranty, color = candidate.checks[:2]
    assert candidate.documents[0].archived_path == warranty.evidence[0].archived_path == source['archived_path']
    assert candidate.documents[0].retrieved_at == source['retrieved_at'] and candidate.documents[0].cache_hit
    assert warranty.evidence[0].url == primary and warranty.evidence[0].excerpt == "Warranty 5 years"
    if identity_changes or selection_lost:
        assert color.ok is None and not color.evidence
    else:
        assert color.evidence[0].url.endswith("photometry") and color.evidence[0].excerpt == "CRI 80"


def test_different_revision_note_cannot_qualify_a_replacement():
    note = Finding(id="currency-newer", check="currency", verdict="note", severity="minor", title="Different revision")
    assert fix._row(note, {}).ok is None


@pytest.mark.parametrize('problem', ['status','currency'])
@pytest.mark.parametrize('candidate_maker', ['Original maker','Other maker'])
def test_replacement_discovery_and_verification_do_not_reuse_another_manufacturers_domains(monkeypatch, problem, candidate_maker):
    observed = {}
    async def search(self, query, **kwargs):
        observed.update(query=query, search_domains=kwargs['include_domains'])
        return [{'url':'https://candidate.test/data.pdf','title':'Candidate X'}]
    async def extract(self, urls):
        return [{'url':urls[0],'raw_content':'Candidate X. Power 10 W'}]
    async def claims(*args, **kwargs):
        return ClaimsOut(product='Candidate X', manufacturer=candidate_maker, model='Candidate X', claims=[
            Claim(id='power', product='Candidate X', manufacturer=candidate_maker, property='watts', value=10, unit='W',
                  page=1, quote='Power 10 W', scope='product_wide', scope_quote='Power 10 W')]), []
    async def verify(case, submitted, **kwargs):
        observed['verify_domains'] = case['manufacturer_domains']
        assert case['require_availability'] is True and case['required_properties'] == ['watts']
        assert case['candidate_url'] == 'https://candidate.test/data.pdf'
        return [], [], [], 0, None
    monkeypatch.setattr(WebClient, 'search', search)
    monkeypatch.setattr(WebClient, 'extract', extract)
    monkeypatch.setattr(fix.extract, 'extract_claims', claims)
    monkeypatch.setattr(fix.verify, 'verify', verify)
    requirement = Requirement(id='power', section='26 51 00', paragraph='2.1', property='watts', operator='lte', value=20,
                              unit='W', text='Power limit')
    old = Finding(id='old', check=problem, verdict='fail' if problem == 'status' else 'outdated', severity='major', title='Old')
    case = {'id':'discovery-test','fixture':None,'title':'LED fixture, office','submittal':[{'role':'product_data'}],
            'manufacturer_domains':['original.test']}
    result, _, _ = asyncio.run(fix._fix(case, 'currency', [old], [requirement],
        ClaimsOut(product='Old product', manufacturer='Original maker', claims=[]), 1, 40))
    assert observed['search_domains'] == (['original.test'] if problem == 'currency' else None)
    assert ('Original maker' in observed['query']) is (problem == 'currency')
    if problem == 'status':
        assert '"LED fixture"' in observed['query'] and 'specification sheet' in observed['query']
        assert 'Power draw' in observed['query'] and '20' not in observed['query']
    assert observed['verify_domains'] == (['original.test'] if candidate_maker == 'Original maker' else [])
    assert not result.suggest and not result.candidates[0].passes  # Discovery alone proves no availability.


def test_quoted_changed_value_source_precedes_search_catalog(monkeypatch):
    from api.schemas import Compare, CompareRow
    primary, catalog = "https://maker.test/current.pdf", "https://maker.test/catalog.pdf"
    fetched = []
    async def search(*args, **kwargs):
        return [{"url": catalog, "title": "Catalog"}, {"url": primary, "title": "Current"}]
    async def extract(self, urls):
        fetched.extend(urls)
        return []
    monkeypatch.setattr(WebClient, "search", search)
    monkeypatch.setattr(WebClient, "extract", extract)
    old = Finding(id="old", check="currency", verdict="outdated", severity="major", title="Old",
        compare=Compare(left_label="Submitted", right_label="Current", verdict="changed", rows=[
            CompareRow(property="watts", label="Power", submitted="10 W", current="20 W", changed=True,
                       source_url=primary, quote="Power 20 W")]))
    case = {"id": "test", "fixture": None, "title": "Luminaire", "submittal": []}
    asyncio.run(fix._fix(case, "currency", [old], [], ClaimsOut(product="X", manufacturer="M", claims=[]), 1, 40))
    assert fetched == [primary]

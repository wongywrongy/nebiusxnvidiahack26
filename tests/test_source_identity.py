from api.pipeline import extract, verify
from api.schemas import Claim, ClaimsOut, VerifyOut
import asyncio
import pytest
from api.schemas import Requirement, Selection, Usage

URL = "https://maker.test/current.pdf"


@pytest.mark.parametrize('unit,quote,accepted', [('years','Warranty 5-year',True), ('yr','Warranty 5 years',True),
    ('hours','Rated life 50,000 hr',True), ('hr','Rated life 50,000 hours',True), ('lumens','Output 500 lm',True),
    ('percent','Dimming to 5%',True), ('years','Rated life 50,000 hr',False), ('hours','Warranty 5-year',False),
    ('mm','Diameter 2 in',False)])
def test_unit_synonyms_match_in_both_directions_without_changing_dimensions(unit, quote, accepted):
    assert extract.unit_quoted(unit,quote) is accepted


@pytest.mark.parametrize('qualifier', ['Not all versions are qualified.', 'Some models are qualified.',
    'Specific configurations are qualified.', 'All models except the emergency variant are qualified.'])
def test_conditional_scope_cannot_be_promoted_to_product_wide(qualifier):
    value='DLC Premium listed.'
    assert not extract.scope_is_product_wide('product_wide',f'{value} {qualifier}',value)
    assert extract.scope_is_product_wide('product_wide',value,value)


def submitted():
    return ClaimsOut(product="Series LX luminaire", manufacturer="Maker", model="LX-20",
                     claims=[Claim(id="w", product="LX", manufacturer="Maker", property="watts", value=10, unit="W")])


@pytest.mark.parametrize('revision,expected', [(None,'unverified'),('Rev C','note')])
def test_document_metadata_cannot_become_a_changed_performance_value(revision, expected):
    product=submitted().model_copy(update={'document_revision':'Rev B','claims':[
        Claim(id='date', product='X', manufacturer='Maker', property='document_revision',value='January 2026')]})
    quote='Safety Data Sheet Issue Date: 02/06/24'
    out=VerifyOut(status='unknown',current_revision=revision,current_values=[{'property':'document_revision',
        'value':'02/06/24','quote':quote,'source_url':URL,'model':'LX-20','identity_quote':'Model LX-20',
        'scope':'product_wide','scope_quote':quote}])
    pages=[{'url':URL,'raw_content':f'Model LX-20. {quote}. Rev C'}]
    confirmed=verify.gate(out,pages,submitted=product)
    findings,rows=verify.compare(product,out,confirmed,[],pages)
    assert findings[0].verdict == expected
    assert not verify._unambiguous(product.claims) and not verify._unambiguous(out.current_values)
    assert not any(f.verdict in ('fail','outdated') for f in findings)
    assert len(rows) == (1 if revision else 0)  # Explicit revision metadata keeps its dedicated note path.


def test_neighboring_model_cannot_supply_current_values_or_revision():
    out = VerifyOut(status="unknown", current_revision="Rev B", current_values=[{
        "property": "watts", "value": 15, "unit": "W", "quote": "Power 15 W"}])
    product = submitted()
    product.family = "LX"
    verify.gate(out, [{"url": URL, "raw_content": "LX family. Model LX-200. Rev B. Power 15 W"}], submitted=product)
    assert not out.current_values and out.current_revision is None
    assert not extract.model_quoted("LX", "LX-200")
    assert not extract.model_quoted("AB+", "Model AB")


def test_reader_cannot_relabel_a_source_as_the_submitted_model():
    out = VerifyOut(status="unknown", current_values=[{
        "property": "watts", "value": 15, "quote": "Power 15 W", "model": "LX-200", "identity_quote": "Model LX-200"}])
    verify.gate(out, [{"url": URL, "raw_content": "Models LX-20 and LX-200. Power 15 W"}], submitted=submitted())
    assert not out.current_values


def test_declared_source_and_identity_quote_must_share_the_fetched_page():
    out = VerifyOut(status="unknown", current_values=[{
        "property": "watts", "value": 15, "quote": "Power 15 W", "source_url": URL,
        "identity_quote": "Model LX-20"}])
    pages = [{"url": URL, "raw_content": "Unrelated power 15 W"},
             {"url": "https://maker.test/identity", "raw_content": "Model LX-20. Power 15 W"}]
    verify.gate(out, pages, submitted=submitted())
    assert not out.current_values


def test_family_status_does_not_import_family_values():
    out = VerifyOut(status="discontinued", status_family="LX", status_quote="The LX family is discontinued.",
        current_values=[{"property": "watts", "value": 15, "quote": "Power 15 W"}])
    product = submitted().model_copy(update={"family": "LX"})
    verify.gate(out, [{"url": URL, "raw_content": "The LX family is discontinued. Power 15 W"}], submitted=product)
    assert out.status == "discontinued" and not out.current_values


@pytest.mark.parametrize("descriptor", ["LX", "LX family", "LX series", "LX range"])
@pytest.mark.parametrize("model,accepted", [("2LX-2X4", True), ("2LXX-2X4", False)])
def test_family_descriptor_and_markdown_do_not_hide_a_family_wide_notice(descriptor, model, accepted):
    quote = "As of **June 30th, 2024**, the LX family will be discontinued."
    product = submitted().model_copy(update={"model": model, "family": "T Series LED"})
    out = VerifyOut(status="discontinued", status_family=descriptor, status_quote=quote)
    verify.gate(out, [{"url": URL, "raw_content": quote}], submitted=product)
    assert out.status == ("discontinued" if accepted else "unknown")


@pytest.mark.parametrize("model,quote", [("2LX-2X4", "The LX family member LX-200 is discontinued."),
    ("2LX-2X4", "The LX family remains available. The LXX family is discontinued."),
    ("2LX-2X4", "Model 2LX-2X4 is available. Model 2LXX-2X4 is discontinued."),
    ("LX-20", "Model LX-20 is available. Model ULX-20 is discontinued.")])
def test_family_or_model_mention_cannot_borrow_another_subjects_status(model, quote):
    product = submitted().model_copy(update={"model": model, "family": "T Series LED"})
    out = VerifyOut(status="discontinued", status_family="LX family", status_quote=quote)
    verify.gate(out, [{"url": URL, "raw_content": quote}], submitted=product)
    assert out.status == "unknown"


def test_header_identity_survives_an_ordering_example_without_selecting_it(monkeypatch):
    pages = [{"page": 1, "text": "2LX-2X4. T Series LED. Example: 2LX-2X4 EZ1"}]
    async def read(*args):
        return ClaimsOut(product="2LX-2X4", manufacturer="Maker", model="2LX-2X4", family="T Series LED",
            family_quote="T Series LED", claims=[]), Usage(task="extract_claims", tier="extract", model="test")
    monkeypatch.setattr(extract, "_read_claims", read)
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), []))
    assert out.model == "2LX-2X4" and out.selection is None


def test_generic_product_word_cannot_establish_family_discontinuation():
    out = VerifyOut(status="discontinued", status_family="LED", status_quote="This LED is discontinued")
    product = submitted().model_copy(update={"family": "LX", "product": "LX LED luminaire"})
    verify.gate(out, [{"url": URL, "raw_content": out.status_quote}], submitted=product)
    assert out.status == "unknown"


def test_scoped_current_value_cannot_become_a_product_wide_comparison():
    out = VerifyOut(status="unknown", current_values=[{
        "property": "watts", "value": 15, "quote": "Optional driver: Power 15 W", "variant": "Optional driver"}])
    pages = [{"url": URL, "raw_content": "Model LX-20. Optional driver: Power 15 W"}]
    confirmed = verify.gate(out, pages, submitted=submitted())
    _, rows = verify.compare(submitted(), out, confirmed, [], pages)
    assert not rows


def test_incompatible_or_missing_units_cannot_prove_an_outdated_value():
    for unit in ("min", None):
        product = submitted()
        out = VerifyOut(status="unknown", current_values=[{
            "property": "watts", "value": 15, "unit": unit, "quote": "Power 15 min"}])
        findings, rows = verify.compare(product, out, {"watts": URL}, [], [])
        assert not rows and all(f.verdict != "outdated" for f in findings)


def test_printed_family_can_identify_an_unselected_family_sheet():
    product = submitted().model_copy(update={"model": None, "family": "LX"})
    out = VerifyOut(status="unknown", current_revision="Rev B")
    verify.gate(out, [{"url": URL, "raw_content": "LX family data sheet. Rev B"}], submitted=product)
    assert out.current_revision == "Rev B"


@pytest.mark.parametrize("proof", [{}, {"source_url": URL}, {"model": "LX-20"}])
def test_omitting_identity_fields_cannot_import_a_neighbor_value(proof):
    out = VerifyOut(status="unknown", current_values=[{
        "property": "watts", "value": 15, "unit": "W", "quote": "LX-200 Power 15 W", **proof}])
    verify.gate(out, [{"url": URL, "raw_content": "Model LX-20. LX-200 Power 15 W"}], submitted=submitted())
    assert not out.current_values


@pytest.mark.parametrize("selected", [False, True])
def test_only_explicit_submitted_selection_resolves_an_option(monkeypatch, selected):
    heading = "Selected: LX-20 EZ1" if selected else "Example: LX-20 EZ1"
    pages = [{"page": 1, "text": heading + ". EZ1 dimming 1%"}]
    async def read(*args):
        return ClaimsOut(product="LX", manufacturer="Maker", model="LX-20 EZ1",
            selection=Selection(model="LX-20 EZ1", page=1, quote=heading), claims=[Claim(
                id="d", product="LX-20 EZ1", manufacturer="Maker", property="dim_min_percent", value=1, unit="%", page=1,
                quote="EZ1 dimming 1%", variant="EZ1", scope="option", scope_quote="EZ1 dimming 1%",
                selection_quote="forged selection")]), Usage(task="extract_claims", tier="extract", model="test")
    monkeypatch.setattr(extract, "_read_claims", read)
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ["dim_min_percent"]))
    req = Requirement(id="dim", section="26 51 00", paragraph="", property="dim_min_percent", operator="lte", value=5, unit="%", text="Dim")
    from api.pipeline.spec_check import check
    assert bool(out.selection) is selected
    assert check([req], out.claims, {"product_data"})[0].verdict == ("pass" if selected else "unverified")


def test_selection_quote_cannot_hide_the_ordering_example_heading():
    selection = Selection(model="LX-20", page=1, quote="Selected LX-20")
    assert not extract.selection_supported(selection, {1: "Ordering example: Selected LX-20"})


@pytest.mark.parametrize("quote", ["Not selected: LX-20", "If selected: LX-20", "Selected: LX-20 or LX-200"])
def test_negative_or_conditional_selection_cannot_resolve_options(quote):
    assert not extract.selection_supported(Selection(model="LX-20", page=1, quote=quote), {1: quote})


def test_web_scope_and_identity_are_independent_evidence():
    out = VerifyOut(status="unknown", current_values=[{
        "property": "watts", "value": 15, "unit": "W", "quote": "Power 15 W", "source_url": URL,
        "model": "LX-20", "identity_quote": "Model LX-20"}])
    pages = [{"url": URL, "raw_content": "Model LX-20. Power 15 W"}]
    confirmed = verify.gate(out, pages, submitted=submitted())
    assert len(out.current_values) == 1  # Grounded identity alone does not prove product-wide applicability.
    assert not verify.compare(submitted(), out, confirmed, [], pages)[1]


def test_scope_label_cannot_override_a_quoted_optional_driver():
    quote = "Optional driver EZ10: Power 15 W"
    out = VerifyOut(status="unknown", current_values=[{
        "property": "watts", "value": 15, "unit": "W", "quote": quote, "source_url": URL,
        "model": "LX-20", "identity_quote": "Model LX-20", "scope": "product_wide", "scope_quote": quote}])
    pages = [{"url": URL, "raw_content": "Model LX-20. " + quote}]
    confirmed = verify.gate(out, pages, submitted=submitted())
    assert not verify.compare(submitted(), out, confirmed, [], pages)[1]


@pytest.mark.parametrize("model", ["LX-20", "LX", None])
def test_member_discontinuation_cannot_spread_to_a_family(model):
    out = VerifyOut(status="discontinued", status_family="LX",
                    status_quote="Only model LX-200 in the LX family is discontinued")
    product = submitted().model_copy(update={"family": "LX", "model": model})
    verify.gate(out, [{"url": URL, "raw_content": "Model LX-20 is available. " + out.status_quote}], submitted=product)
    assert out.status == "unknown"


def test_an_alternative_in_a_selection_quote_is_not_the_selected_option(monkeypatch):
    quote = "Selected: LX-20 EZ1. Alternative EZ10"
    selection = Selection(model="LX-20 EZ1", page=1, quote=quote)
    assert extract.selection_supported(selection, {1: quote})
    product = submitted().model_copy(update={"model": "LX-20 EZ1", "selection": selection})
    pv = {"property": "watts", "value": 15, "unit": "W", "quote": "EZ10 Power 15 W", "variant": "EZ10",
          "source_url": URL, "model": "LX-20 EZ1", "identity_quote": "Model LX-20 EZ1", "scope": "option"}
    out = VerifyOut(status="unknown", current_values=[pv])
    pages = [{"url": URL, "raw_content": "Model LX-20 EZ1. EZ10 Power 15 W"}]
    confirmed = verify.gate(out, pages, submitted=product)
    assert not out.current_values[0].selection_quote
    assert not verify.compare(product, out, confirmed, [], pages)[1]


def test_reader_cannot_choose_an_alternative_as_the_selected_model():
    quote = "Selected: LX-20 EZ1. Alternative LX-30 EZ10"
    assert not extract.selection_supported(Selection(model="LX-30 EZ10", page=1, quote=quote), {1: quote})

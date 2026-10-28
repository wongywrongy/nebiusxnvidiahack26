"""Grounding repairs cannot select options, borrow another product, or hide an oversized draft."""

import asyncio
import json

import httpx
import pytest
import respx

from api.config import settings
from api.pipeline import extract, spec_check
from api.release import _claims
from api.schemas import Claim, ClaimsOut, Requirement, Usage


def test_printed_model_can_bind_its_document_display_name(monkeypatch):
    quote = 'VOC 20 g/L'
    text = 'Flexible sealant. Model ZX-10. ' + quote
    claim = Claim(id='voc', product='Flexible sealant', manufacturer='Maker', model='ZX-10',
                  property='voc_g_per_l', value=20, unit='g/L', page=1, quote=quote,
                  scope='product_wide', scope_quote=quote)
    async def read(*args):
        return ClaimsOut(product=claim.product, manufacturer='Maker', model='ZX-10', claims=[claim]), Usage(task='extract_claims', tier='extract', model='test')
    monkeypatch.setattr(extract, '_read_claims', read)
    pages = [{'page': 1, 'text': text}]
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ['voc_g_per_l']))
    assert out.claims[0].variant is None and out.claims[0].scope == 'product_wide'
    _claims(out, out.claims, None, {1: text})


def test_matching_model_does_not_import_a_different_named_products_claim(monkeypatch):
    async def read(*args):
        return ClaimsOut(product='ZX-10', manufacturer='Maker', model='ZX-10', claims=[dict(
            id='watts', product='AB-20', model='ZX-10', manufacturer='Maker', property='watts', value=20,
            unit='W', page=1, quote='Power 20 W', scope='product_wide', scope_quote='Power 20 W')]), Usage(task='extract_claims', tier='extract', model='test')
    monkeypatch.setattr(extract, '_read_claims', read)
    pages = [{'page': 1, 'text': 'Model ZX-10. Model AB-20. Power 20 W'}]
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ['watts']))
    assert out.claims[0].scope == 'unknown' and out.claims[0].variant


def test_unknown_scope_is_not_an_ordering_instruction():
    quote = 'VOC 20 g/L'
    claim = Claim(id='voc', product='ZX-10', manufacturer='Maker', property='voc_g_per_l', value=20,
                  unit='g/L', page=1, quote=quote, variant=quote, scope='unknown')
    requirement = Requirement(id='voc', section='test', paragraph='', property='voc_g_per_l',
                              operator='lte', value=250, unit='g/L', text='VOC limit')
    [finding] = spec_check.check([requirement], [claim])
    assert finding.verdict == 'unverified' and not finding.configure
    assert finding.title == "Couldn't confirm: VOC (air quality)"


def test_pdf_word_wrap_can_be_normalized_without_joining_separate_quotes():
    assert extract.quoted('This specification includes a warranty.', 'This speci-\nfication includes a warranty.')
    assert not extract.quoted('Warranty 5 years', 'Warranty 3 years. Another product offers 5 years')
    assert not extract.quoted('AB20', 'AB-20')


@pytest.mark.parametrize('borrow_quote', [False, True])
def test_continuation_header_establishes_identity_but_not_values(monkeypatch, borrow_quote):
    monkeypatch.setattr(extract, 'page_batches', lambda pages, limit: ([p] for p in pages))
    pages = [{'page': 1, 'text': 'Model ZX-10. Power 20 W'}, {'page': 2, 'text': 'Warranty 5 years'}]
    async def read(task, schema, messages, ctx):
        batch = json.loads(messages[0]['content'].split('\n\n')[-1])
        second = batch[0]['page'] == 2
        if second:
            assert batch[0]['document_header'] == pages[0]['text']
        quote, prop, value, unit = ('Power 20 W', 'watts', 20, 'W') if not second or borrow_quote else ('Warranty 5 years', 'warranty_years', 5, 'years')
        return ClaimsOut(product='ZX-10', manufacturer='Maker', model='ZX-10', claims=[dict(
            id=str(batch[0]['page']), product='ZX-10', model='ZX-10', manufacturer='Maker', property=prop,
            value=value, unit=unit, page=batch[0]['page'], quote=quote, scope='product_wide', scope_quote=quote)]), Usage(task=task, tier='extract', model='test')
    monkeypatch.setattr(extract.router, 'call', read)
    out, _ = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ['watts', 'warranty_years']))
    assert len(out.claims) == (1 if borrow_quote else 2)
    assert all(c.scope == 'product_wide' and c.variant is None for c in out.claims)
    _claims(out, out.claims, None, {p['page']: p['text'] for p in pages})


@pytest.mark.parametrize('listed', [True, False])
@pytest.mark.parametrize('limited', [True, False])
def test_incomplete_pipe_list_uses_only_the_complete_enumeration(monkeypatch, listed, limited):
    quote = 'Pipe types: PVC, ABS.'
    complete = '3. PENETRATING ITEM TO BE ONE OF THE FOLLOWING:\nA. PVC pipe.\nB. ABS pipe.\n'
    if listed:
        complete += 'C. PEX tubing.\n'
    claim = Claim(id='pipes', product='ZX-10', manufacturer='Maker', model='ZX-10', property='penetrant_types',
                  value=['PVC', 'ABS', 'PEX'], page=1, quote=quote, scope='product_wide',
                  scope_quote='Optional version. ' + quote if limited else quote)
    calls = []
    async def read(task, schema, messages, ctx):
        calls.append(schema)
        return ClaimsOut(product='ZX-10', manufacturer='Maker', model='ZX-10', claims=[claim]), Usage(task=task, tier='extract', model='test')
    monkeypatch.setattr(extract.router, 'call', read)
    pages = [{'page': 1, 'text': 'Model ZX-10. Optional version. ' + quote + '\n2. Steel studs.\n' + complete + '4. Other parts: PEX.'}]
    out, usage = asyncio.run(extract.extract_claims(None, pages, extract.all_product_data(pages), ['penetrant_types']))
    assert len(calls) == len(usage) == 1
    if listed:
        assert out.claims[0].value == claim.value and out.claims[0].quote == complete.strip()
        assert out.claims[0].scope == ('unknown' if limited else 'product_wide')
        _claims(out, out.claims, None, {1: pages[0]['text']})
        for wanted, verdict in [('steel pipe', 'fail'), ('PEX', 'pass')]:
            requirement = Requirement(id='pipes', section='test', paragraph='', property='penetrant_types',
                                      operator='contains', value=wanted, check='validity', text='Required pipe')
            assert spec_check.check([requirement], out.claims)[0].verdict == ('unverified' if limited else verdict)
    else:
        assert not out.claims


def test_oversized_draft_is_retried_under_the_actual_provider_schema(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'speccheck_mode', 'live')
    monkeypatch.setattr(settings, 'cache_dir', tmp_path)
    rule = {'id': 'voc', 'section': '07 84 00', 'paragraph': '2.1', 'property': 'voc_g_per_l',
            'operator': 'lte', 'value': 250, 'unit': 'g/L', 'text': 'VOC at most 250 g/L'}
    def reply(rules):
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'requirements': rules})}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 10}})
    with respx.mock as http:
        route = http.post(settings.nebius_base_url.rstrip('/') + '/chat/completions').mock(side_effect=[
            reply([{**rule, 'id': str(n)} for n in range(31)]), reply([rule])])
        out, _ = asyncio.run(extract.extract_requirements('07 84 00', 'VOC at most 250 g/L'))
        assert len(out.requirements) == 1 and len(route.calls) == 2
        body = json.loads(route.calls[0].request.content)
        assert body['response_format']['json_schema']['schema']['properties']['requirements']['maxItems'] == 30


@pytest.mark.parametrize('bad', ['separate_brands', 'series_as_manufacturer', 'multiple_groups'])
def test_ambiguous_draft_alternatives_are_retried_without_silently_rewriting(monkeypatch, tmp_path, bad):
    monkeypatch.setattr(settings, 'speccheck_mode', 'live')
    monkeypatch.setattr(settings, 'cache_dir', tmp_path)
    rule = dict(id='models', section='08 71 00', paragraph='3.1', product_type='cylindrical lockset',
                property='model', operator='any_of', value=['Brand A AX100', 'Brand B BX200'], text='Approved lock models')
    incorrect = [{**rule, 'property': 'manufacturer', 'operator': 'eq', 'value': 'Brand A'},
                 {**rule, 'id': 'other', 'property': 'manufacturer', 'operator': 'eq', 'value': 'Brand B'}]
    if bad == 'series_as_manufacturer':
        incorrect = [{**rule, 'property': 'manufacturer', 'value': ['Brand A AX100 series']}]
    if bad == 'multiple_groups':
        incorrect += [{**r, 'id': 'mortise-' + r['id'], 'product_type': 'mortise lockset'} for r in incorrect]
    def reply(rules):
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'requirements': rules})}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 10}})
    with respx.mock as http:
        route = http.post(settings.nebius_base_url.rstrip('/') + '/chat/completions').mock(side_effect=[reply(incorrect), reply([rule])])
        out, _ = asyncio.run(extract.extract_requirements('08 71 00', 'Allowed models: Brand A AX100 or Brand B BX200'))
        assert out.requirements[0].value == rule['value'] and out.requirements[0].property == 'model'
        assert len(route.calls) == 2
        if bad == 'multiple_groups':
            feedback = json.loads(route.calls[1].request.content)['messages'][-1]['content']
            assert 'cylindrical lockset' in feedback and 'mortise lockset' in feedback

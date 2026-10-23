"""Synthetic local files exercise promotion; none is provider evidence or a recorded live run."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from api import release
from api.config import settings
from api.pipeline.scores import scores
from api.pipeline.spec_check import check as spec_findings
from api.schemas import Claim, ClaimsOut, Compare, CompareRow, Evidence, Event, Finding, Fix, FixCandidate, FixCheck, Investigation, InvestigationStep, PropertyValue, Requirement, Result, Selection, VerificationProof, VerifyOut


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'raw_dir', tmp_path / 'raw')
    monkeypatch.setattr(settings, 'evidence_dir', tmp_path / 'archive')
    monkeypatch.setattr(release, 'required_documents', lambda: {'passed': True})
    clean = {'decision': 'approve', 'problems': []}
    statements = {'l70_hours':'L70 60,000 hours', 'warranty_years':'Warranty 5 years', 'dlc_listed':'DLC Premium',
                  'macadam_steps':'3-step MacAdam Ellipse', 'dim_min_percent':'Dims down to 1%'}
    values = {'l70_hours':60000, 'warranty_years':5, 'dlc_listed':['dlc premium'], 'macadam_steps':3, 'dim_min_percent':1}
    requirements = release._read(settings.data_dir / 'requirements/26_51_00.json')['requirements']
    requirements = [Requirement(**row) for row in requirements]
    claims = [Claim(id=row.property, product='Product X', manufacturer='Synthetic maker', property=row.property,
        value=values[row.property], unit=row.unit, page=1, quote=statements[row.property],
        scope='product_wide', scope_quote=statements[row.property]) for row in requirements]
    submitted = settings.raw_dir / 'synthetic.pdf'
    submitted.parent.mkdir(parents=True)
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((30, 50), '\n'.join(['Product X', *statements.values(), 'Power 20 W']))
        pdf.save(submitted)
    submittal = [{'role':'product_data', 'file':'synthetic.pdf'}]
    cases = {'alpha': {'id':'alpha', 'title':'Synthetic changed sheet', 'section':'26 51 00', 'submittal':submittal,
                      'expected': {'decision':'send_back', 'problems':['currency']}},
             'beta': {'id':'beta', 'title':'Synthetic clean sheet', 'section':'26 51 00', 'submittal':submittal, 'expected':clean}}
    samples = {'sample': {'id':'sample', 'title':'Synthetic tray item', 'section':'26 51 00', 'submittal':submittal, 'tray':True, 'expected':clean}}
    monkeypatch.setattr(release, 'all_cases', lambda: cases)
    monkeypatch.setattr(release, 'all_samples', lambda: samples)
    now = datetime.now(timezone.utc)
    frozen = tmp_path / 'blind-set'
    inputs, labels = [], []
    for n in range(6):
        key, quote = f'blind-{n}', f'Synthetic product {n} has a five-year warranty.'
        path = settings.raw_dir / f'blind/{key}.pdf'
        path.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((30, 50), '\n'.join(['Product X', quote, *statements.values()]))
            pdf.save(path)
        document = {'file':str(path.relative_to(settings.raw_dir)), 'url':f'https://maker.test/{key}.pdf',
                    'sha256':release.file_hash(path), 'role':'product_data'}
        inputs.append({'id':key, 'title':f'Synthetic blind {n}', 'section':'26 51 00', 'submittal':[document]})
        labels.append({'id':key, 'scope':'product_data; no selected configuration inferred', 'expected':clean,
                       'sources':[{**document, 'quotes':[{'page':1,'text':quote}]}]})
    write(frozen / 'inputs.json', {'cases':inputs})
    write(frozen / 'labels.json', {'labels':labels})
    write(frozen / 'manifest.json', {'version':1, 'prepared_by':'Synthetic independent test preparer',
        'frozen_at':(now - timedelta(hours=3)).isoformat(), 'reviewed_by':'Kyle',
        'reviewed_at':(now - timedelta(hours=2)).isoformat(),
        'inputs_sha256':release.file_hash(frozen / 'inputs.json'), 'labels_sha256':release.file_hash(frozen / 'labels.json')})
    blind, _, blind_hash = release._blind(frozen)
    content = ('Product X is currently available. Rev. 01/01/26. Power 25 W. ' + '. '.join(statements.values())).encode()
    digest = hashlib.sha256(content).hexdigest()
    archived = f'alpha/20261023T000000Z/{digest}.txt'
    path = settings.evidence_dir / archived
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    evidence = Evidence(url='https://maker.test/synthetic.pdf', tier='manufacturer', title='Synthetic source',
        sha256=digest, archived_path=archived, excerpt='Product X is currently available.',
        retrieved_at=(now - timedelta(minutes=70)).isoformat())
    def proof(extracted, *, changed=False):
        values = [PropertyValue(property='l70_hours', value=60000, unit='hr', quote=statements['l70_hours'],
            source_url=evidence.url, model='Product X', identity_quote='Product X', scope='product_wide', scope_quote=statements['l70_hours'])]
        if changed:
            values.append(PropertyValue(property='watts', value=25, unit='W', quote='Power 25 W', source_url=evidence.url,
                model='Product X', identity_quote='Product X', scope='product_wide', scope_quote='Power 25 W'))
        output = VerifyOut(status='active', status_quote='Product X is currently available.', current_values=values)
        pages = [{'url':evidence.url, 'raw_content':content.decode()}]
        confirmed = release.verify.gate(output, pages, measure=False, submitted=extracted)
        findings, rows = release.verify.compare(extracted, output, confirmed, [evidence], pages)
        return VerificationProof(submitted=extracted.model_copy(deep=True), output=output, sources=[evidence]), findings, rows
    catalogs = {'cases':cases, 'samples':samples, 'blind':blind, 'recording':{**cases, **samples}}
    current = json.loads(json.dumps(release.manifest()))
    for suite, catalog in catalogs.items():
        folder = tmp_path / suite
        identity = {**current, 'run_id':suite, 'requested_ids':list(catalog),
                    'started_at':(now - timedelta(hours=1)).isoformat()}
        if suite == 'blind':
            identity['validation_set_sha256'] = blind_hash
        write(folder / 'manifest.json', identity)
        attempts = {}
        events = []
        for key in catalog:
            result = Result(case_id=key, title='Synthetic result', decision='approve', summary='Synthetic test only',
                findings=spec_findings(requirements, claims, {'product_data'}), claims=[claim.model_copy(deep=True) for claim in claims],
                document_roles=['product_data'], mode='live', validity='valid', config_hash=current['config_hash'])
            if key == 'alpha':
                result.decision = 'send_back'
                result.claims.append(Claim(id='power', product='Product X', manufacturer='Synthetic maker', property='watts',
                    value=20, unit='W', page=1, quote='Power 20 W', scope='product_wide', scope_quote='Power 20 W'))
            result.extracted = ClaimsOut(product='Product X', manufacturer='Synthetic maker', model='Product X', claims=result.claims)
            result.verification, web_findings, result.comparison = proof(result.extracted, changed=key == 'alpha')
            if key == 'alpha':
                finding = web_findings[0]
                result.findings.insert(0, finding)
                result.findings += web_findings[1:]
                checks = [FixCheck(label=requirement.property, check='spec', requirement_id=requirement.id,
                    claim_ids=[requirement.property], ok=True, evidence=[evidence.model_copy(update={'excerpt':statements[requirement.property]})])
                    for requirement in requirements]
                extracted = ClaimsOut(product='Product X', manufacturer='Synthetic maker', model='Product X', claims=claims)
                verification, fix_web, _ = proof(extracted)
                from api.pipeline.fix import _row
                checks += [_row(item, {}) for item in fix_web]
                finding.fix = Fix(head='Synthetic replacement', query='Synthetic query', candidates=[FixCandidate(
                    name='Synthetic replacement', source_url=evidence.url, passes=True, checks=checks,
                    claims=claims, extracted=extracted, verification=verification, page_sources={1:evidence},
                    document_roles=['product_data'], documents=[evidence])])
                result.investigations = [Investigation(purpose='primary', outcome='found', resolution='problem_found',
                    scripted=VerifyOut(status='unknown'), steps=[
                        InvestigationStep(n=1, tool='extract', args={'url':evidence.url}, summary='1 extracted source', succeeded=True, source_urls=[evidence.url]),
                        InvestigationStep(n=2, tool='finish', args={'found':True,'document_url':evidence.url}, summary='Found source', succeeded=True)])]
            else:
                result.findings += web_findings
            write(folder / 'results' / f'{key}.json', result.model_dump(mode='json'))
            attempts[key] = {'duration_ms':0, 'fresh_model_cost_usd':0, 'fresh_web_credits':0, 'diagnostics':[]}
            stages = ['queued','ingest','triage','extract','spec_check','verify']
            if key == 'alpha':
                stages += ['investigate','fix']
            stages += ['report','done']
            events.extend(Event(run_id=suite, case_id=key, stage=stage, message='Synthetic test only', t_ms=0,
                                data={'decision':result.decision} if stage == 'done' else None).model_dump_json() for stage in stages)
        write(folder / 'attempts.json', attempts)
        (folder / 'events.jsonl').write_text('\n'.join(events) + '\n')
    fixture = SimpleNamespace(root=tmp_path, catalogs=catalogs, now=now, frozen=frozen)
    for suite in catalogs:
        rescore(fixture, suite)
    write(tmp_path / 'bundle.json', {**{name:name for name in catalogs}, 'blind_set':'blind-set', 'review':'review.json'})
    approve(fixture)
    return fixture


def rescore(fixture, suite):
    folder = fixture.root / suite
    results = {p.stem:Result.model_validate_json(p.read_text()) for p in (folder / 'results').glob('*.json')}
    run = SimpleNamespace(id=suite, results=results, attempts=release._read(folder / 'attempts.json'),
        manifest=release._read(folder / 'manifest.json'), ledger=SimpleNamespace(fresh_usd={}, fresh_credits={}))
    ids = sorted(fixture.catalogs['cases'] if suite == 'recording' else fixture.catalogs[suite])
    score = scores(run, ids, catalog=fixture.catalogs[suite])
    score.update(mode='live', generated_at=(fixture.now - timedelta(minutes=30)).isoformat())
    write(folder / 'scores.json', score)


def approve(fixture, accepted=()):
    hashes = {suite:release.run_hash(fixture.root / suite) for suite in fixture.catalogs}
    hashes['blind_set'] = release._blind(fixture.frozen)[2]
    write(fixture.root / 'review.json', {'approved_by':'Kyle', 'approved_at':fixture.now.isoformat(),
        'artifact_hashes':hashes, 'accepted_misses':list(accepted)})


def test_complete_reviewed_bundle_passes_and_preserves_cases_only_recording_score(bundle):
    report = release.check(bundle.root / 'bundle.json')
    assert report['passed'], report['issues']
    assert report['panels']['blind']['right_call'] == {'n':6, 'of':6}
    assert report['panels']['recording']['right_call'] == {'n':3, 'of':3}
    assert release._read(bundle.root / 'recording/scores.json')['right_call'] == {'n':2, 'of':2}


@pytest.mark.parametrize('fault', ['missing-sample','extra-result','wrong-code','wrong-config','mock','replay',
    'attempt-error','trace-warning','fake-score','uncited-fix','unknown-fix','no-rescue','missing-review',
    'changed-review-hash','premature-review','stale-archive','corrupt-archive','missing-native-pdf',
    'missing-required-check','missing-availability','rescue-no-steps','rescue-already-known','problem-without-proof',
    'decision-mismatch','done-only','done-decision-mismatch','wrong-status-quote','no-changed-row','no-returned-source',
    'fake-spec-verdict','fake-fix-verdict','fake-claim-value'])
def test_incomplete_incompatible_or_unsupported_evidence_cannot_promote(bundle, monkeypatch, fault):
    root = bundle.root
    if fault == 'missing-sample':
        (root / 'samples/results/sample.json').unlink()
    elif fault == 'extra-result':
        (root / 'samples/results/extra.json').write_text((root / 'samples/results/sample.json').read_text())
    elif fault == 'wrong-code':
        value = release._read(root / 'cases/manifest.json'); value['code_hash'] = 'bad'; write(root / 'cases/manifest.json', value)
    elif fault in ('wrong-config','mock','replay'):
        path = root / 'samples/results/sample.json'
        value = release._read(path)
        value[{'wrong-config':'config_hash','mock':'mode','replay':'replayed_from'}[fault]] = {
            'wrong-config':'bad','mock':'mock','replay':'old-run'}[fault]
        write(path, value)
    elif fault == 'attempt-error':
        value = release._read(root / 'samples/attempts.json'); value['sample']['diagnostics'] = [{'stage':'verify','kind':'budget','message':'Synthetic cap'}]
        write(root / 'samples/attempts.json', value)
    elif fault == 'trace-warning':
        with (root / 'samples/events.jsonl').open('a') as output:
            output.write(Event(run_id='samples', case_id='sample', stage='verify', message='Synthetic warning', t_ms=0,
                               data={'warning':True}).model_dump_json() + '\n')
    elif fault == 'fake-score':
        value = release._read(root / 'cases/scores.json'); value['right_call']['n'] = 999; write(root / 'cases/scores.json', value)
    elif fault in ('uncited-fix','unknown-fix','no-rescue','stale-archive','missing-required-check','missing-availability',
                   'rescue-no-steps','rescue-already-known','problem-without-proof','decision-mismatch',
                   'wrong-status-quote','no-changed-row','no-returned-source','fake-spec-verdict','fake-fix-verdict','fake-claim-value'):
        path = root / 'cases/results/alpha.json'; value = release._read(path)
        if fault == 'no-rescue':
            value['investigations'] = []
        elif fault == 'rescue-no-steps':
            value['investigations'][0]['steps'] = []
        elif fault == 'rescue-already-known':
            value['investigations'][0]['scripted']['current_values'] = [{'property':'watts','value':25,'unit':'W'}]
        elif fault == 'problem-without-proof':
            value['findings'][0]['evidence'] = []
        elif fault == 'decision-mismatch':
            value['decision'] = 'approve'
        elif fault == 'wrong-status-quote':
            source = dict(value['findings'][0]['evidence'][0])
            source['excerpt'] = 'Product X is currently available.'
            value['findings'].append(Finding(id='status-discontinued', check='status', verdict='fail', severity='major',
                title='Unsupported status', quote='Product X is discontinued.', evidence=[Evidence(**source)]).model_dump(mode='json'))
        elif fault == 'no-changed-row':
            value['findings'][0]['compare']['rows'] = []
        elif fault == 'no-returned-source':
            value['investigations'][0]['steps'][0]['source_urls'] = []
        elif fault == 'fake-spec-verdict':
            value['findings'][1]['verdict'] = 'fail'
        elif fault == 'fake-fix-verdict':
            value['findings'][0]['fix']['candidates'][0]['claims'][0]['value'] = 100
        elif fault == 'fake-claim-value':
            value['findings'][0]['fix']['candidates'][0]['claims'][0]['value'] = 70000
        elif fault == 'missing-required-check':
            value['findings'][0]['fix']['candidates'][0]['checks'].pop(0)
        elif fault == 'missing-availability':
            value['findings'][0]['fix']['candidates'][0]['checks'] = [check for check in
                value['findings'][0]['fix']['candidates'][0]['checks'] if check['check'] != 'status']
        else:
            check = value['findings'][0]['fix']['candidates'][0]['checks'][0]
            if fault == 'uncited-fix':
                check['evidence'] = []
            elif fault == 'unknown-fix':
                check['ok'] = None
            else:
                check['evidence'][0]['retrieved_at'] = (bundle.now - timedelta(days=2)).isoformat()
        write(path, value)
        rescore(bundle, 'cases')
    elif fault in ('done-only', 'done-decision-mismatch'):
        path = root / 'samples/events.jsonl'
        if fault == 'done-only':
            path.write_text(Event(run_id='samples', case_id='sample', stage='done', message='Synthetic', t_ms=0,
                                  data={'decision':'approve'}).model_dump_json() + '\n')
        else:
            events = [json.loads(line) for line in path.read_text().splitlines()]
            events[-1]['data']['decision'] = 'send_back'
            path.write_text('\n'.join(json.dumps(event) for event in events) + '\n')
    elif fault == 'missing-review':
        (root / 'review.json').unlink()
    elif fault in ('changed-review-hash','premature-review'):
        value = release._read(root / 'review.json')
        if fault == 'changed-review-hash':
            value['artifact_hashes']['cases'] = 'bad'
        else:
            value['approved_at'] = (bundle.now - timedelta(days=1)).isoformat()
        write(root / 'review.json', value)
    elif fault == 'corrupt-archive':
        next(settings.evidence_dir.rglob('*.txt')).write_text('Synthetic corrupt archive')
    else:
        monkeypatch.setattr(release, 'required_documents', lambda: {'passed':False})
    if fault not in ('missing-review','changed-review-hash','premature-review'):
        approve(bundle)  # Rebinding hashes cannot waive invalid or unsupported evidence.
    assert not release.check(root / 'bundle.json')['passed']


@pytest.mark.parametrize('fault', ['unreviewed','labels-in-input','bad-page-quote','not-bound','review-after-run'])
def test_blind_freeze_and_pre_evaluation_review_are_mandatory(bundle, fault):
    root, frozen = bundle.root, bundle.frozen
    metadata = release._read(frozen / 'manifest.json')
    if fault == 'unreviewed':
        metadata['reviewed_by'] = 'agent'
    elif fault == 'labels-in-input':
        inputs = release._read(frozen / 'inputs.json'); inputs['cases'][0]['expected'] = {'decision':'approve'}
        write(frozen / 'inputs.json', inputs); metadata['inputs_sha256'] = release.file_hash(frozen / 'inputs.json')
    elif fault == 'bad-page-quote':
        labels = release._read(frozen / 'labels.json'); labels['labels'][0]['sources'][0]['quotes'][0]['text'] = 'This text is absent.'
        write(frozen / 'labels.json', labels); metadata['labels_sha256'] = release.file_hash(frozen / 'labels.json')
    elif fault == 'review-after-run':
        metadata['reviewed_at'] = (bundle.now - timedelta(minutes=20)).isoformat()
    else:
        identity = release._read(root / 'blind/manifest.json'); identity['validation_set_sha256'] = 'bad'
        write(root / 'blind/manifest.json', identity)
    write(frozen / 'manifest.json', metadata)
    assert not release.check(root / 'bundle.json')['passed']


def test_blind_inputs_cannot_escape_the_result_folder(bundle):
    folder = bundle.frozen
    metadata = release._read(folder / 'manifest.json')
    for name, field in [('inputs.json', 'cases'), ('labels.json', 'labels')]:
        value = release._read(folder / name)
        value[field][0]['id'] = '../escape'
        write(folder / name, value)
        metadata['inputs_sha256' if field == 'cases' else 'labels_sha256'] = release.file_hash(folder / name)
    write(folder / 'manifest.json', metadata)
    with pytest.raises(ValueError, match='safe result filenames'):
        release._blind(folder)


def test_explicit_owner_disposition_preserves_raw_disagreement_and_cannot_waive_invalidity(bundle):
    path = bundle.root / 'cases/results/beta.json'
    value = release._read(path); value['decision'] = 'approve_with_note'
    value['claims'] = [claim for claim in value['claims'] if claim['property'] != 'warranty_years']
    value['extracted']['claims'] = value['claims']
    value['verification']['submitted']['claims'] = value['claims']
    requirements = [Requirement(**row) for row in release._read(settings.data_dir / 'requirements/26_51_00.json')['requirements']]
    value['findings'] = [finding for finding in value['findings'] if finding['check'] in ('currency','status')] + [
        finding.model_dump(mode='json') for finding in spec_findings(
        requirements, [Claim(**claim) for claim in value['claims']], set(value['document_roles']))]
    write(path, value)
    events_path = bundle.root / 'cases/events.jsonl'
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    for event in events:
        if event['case_id'] == 'beta' and event['stage'] == 'done':
            event['data']['decision'] = 'approve_with_note'
    events_path.write_text('\n'.join(json.dumps(event) for event in events) + '\n')
    rescore(bundle, 'cases')
    assert not release.check(bundle.root / 'bundle.json')['passed']


    source = release._read(bundle.frozen / 'labels.json')['labels'][0]['sources'][0]
    accepted = [{'suite':'cases', 'id':'beta', 'misses':['wrong_call','unnecessary_note'],
        'reason':'Synthetic owner-adjudicated source conflict', 'evidence':[source]}]
    approve(bundle, accepted)
    report = release.check(bundle.root / 'bundle.json')
    assert report['passed'], report['issues']
    assert report['panels']['cases']['right_call'] == {'n':1,'of':2}
    value['validity'] = 'invalid'; write(path, value); rescore(bundle, 'cases'); approve(bundle, accepted)
    assert not release.check(bundle.root / 'bundle.json')['passed']


def test_returned_linked_pdf_is_attributed_to_its_actual_extract_result(bundle):
    path = bundle.root / 'cases/results/alpha.json'
    value = release._read(path)
    value['investigations'][0]['steps'][0]['args']['url'] = 'https://maker.test/product-page'
    write(path, value)
    rescore(bundle, 'cases'); approve(bundle)
    report = release.check(bundle.root / 'bundle.json')
    assert report['passed'], report['issues']


@pytest.mark.parametrize('fault', ['absent-claim-quote','wrong-claim-page','absent-scope-quote','omitted-web-outcome',
    'counterfeit-availability','counterfeit-currency','unbound-verification'])
def test_promotion_replays_page_and_web_gates_instead_of_trusting_saved_checks(bundle, fault):
    path = bundle.root / 'cases/results/alpha.json'
    result = release._read(path)
    candidate = result['findings'][0]['fix']['candidates'][0]
    if fault in ('absent-claim-quote','wrong-claim-page','absent-scope-quote'):
        field, value = {'absent-claim-quote':('quote','THIS QUOTE DOES NOT OCCUR ON THE PAGE'),
            'wrong-claim-page':('page',99), 'absent-scope-quote':('scope_quote','All options share this value')}[fault]
        for claims in (result['claims'], result['extracted']['claims'], result['verification']['submitted']['claims']):
            claims[0][field] = value
    elif fault == 'omitted-web-outcome':
        result['findings'] = [f for f in result['findings'] if f['check'] not in ('currency','status')]
        result['verification'] = None
        result['comparison'] = []
        result['decision'] = 'approve'
    elif fault == 'counterfeit-availability':
        candidate['verification']['output']['status_quote'] = 'Power 25 W'
        next(check for check in candidate['checks'] if check['check'] == 'status')['evidence'][0]['excerpt'] = 'Power 25 W'
    elif fault == 'counterfeit-currency':
        next(check for check in candidate['checks'] if check['check'] == 'currency')['evidence'][0]['excerpt'] = 'Power 25 W'
    else:
        result['verification']['submitted']['model'] = 'Another product'
    write(path, result)
    rescore(bundle, 'cases'); approve(bundle)
    with pytest.raises(ValueError):
        release._run(bundle.root / 'cases', set(bundle.catalogs['cases']), bundle.catalogs['cases'],
                     json.loads(json.dumps(release.manifest())))
    assert not release.check(bundle.root / 'bundle.json')['passed']


@pytest.mark.parametrize('prefix,accepted', [('Submitted package:',True), ('Example:',False)])
def test_selection_proof_preserves_surrounding_example_context(tmp_path, monkeypatch, prefix, accepted):
    monkeypatch.setattr(settings, 'evidence_dir', tmp_path)
    now = datetime.now(timezone.utc)
    body = f'{prefix}\nSelected: X EZ1\n'.encode()
    path = tmp_path / 'source.txt'; path.write_bytes(body)
    evidence = Evidence(url='https://maker.test/product', tier='manufacturer', title='Synthetic source',
        sha256=hashlib.sha256(body).hexdigest(), archived_path=path.name,
        retrieved_at=(now - timedelta(minutes=30)).isoformat())
    candidate = SimpleNamespace(documents=[evidence])
    selection = Selection(model='X EZ1', quote='Selected: X EZ1', page=1)
    assert release._selection_proof(candidate, selection, now - timedelta(hours=1), now) is accepted


@pytest.mark.parametrize('base,selected,accepted', [('LX-20','LX-20 EZ1',True), ('Alpha-1','Beta-2 EZ1',False)])
def test_selected_configuration_must_extend_the_same_grounded_base_model(base, selected, accepted):
    text = f'{base}\nSelected: {selected}\nEZ1 dimming 1%'
    selection = Selection(model=selected, page=1, quote=f'Selected: {selected}')
    claim = Claim(id='d', product=base, manufacturer='Maker', model=base, page=1, property='dim_min_percent',
        value=1, unit='%', quote='EZ1 dimming 1%', variant='EZ1', scope='option', selection_quote=selection.quote)
    extracted = ClaimsOut(product=base, manufacturer='Maker', model=selected if accepted else base,
                          selection=selection, claims=[claim])
    if accepted:
        release._claims(extracted, [claim], selection, {1:text})
    else:
        with pytest.raises(ValueError):
            release._claims(extracted, [claim], selection, {1:text})

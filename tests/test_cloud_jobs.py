"""Controller/worker protocol with a real isolated wallet and a CLI that cannot reach Nebius."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api import authority, cloud_jobs, job_control, main
from api.config import settings
from api.providers import campaign
from api.providers.budget import BudgetExceeded
from api.schemas import Evidence, Finding, Result

pytestmark = pytest.mark.campaign


@pytest.fixture
def cloud(monkeypatch, tmp_path):
    binary = tmp_path / 'nebius'
    binary.write_bytes((Path(__file__).parent / 'fake_nebius.py').read_bytes())
    binary.chmod(0o755)
    monkeypatch.setenv('PATH', f'{tmp_path}:{os.environ["PATH"]}')
    monkeypatch.setenv('FAKE_NEBIUS_CALLS', str(tmp_path / 'calls.jsonl'))
    monkeypatch.setenv('FAKE_NEBIUS_STATE', str(tmp_path / 'state'))
    (tmp_path / 'state').write_text('fixture-starting')
    controller = tmp_path / 'controller'
    controller.mkdir()
    monkeypatch.setattr(Path, 'is_mount', lambda path: path == controller)
    monkeypatch.setattr(authority, 'filesystem_type', lambda _: 'virtiofs')
    monkeypatch.setattr(settings, 'controller_state_dir', None)
    monkeypatch.setattr(settings, 'evidence_dir', tmp_path / 'evidence')
    source = tmp_path / 'source.sqlite3'
    campaign.initialize(source, campaign.Amount(), {}, campaign.Amount(usd_nano=20000000000, credits=2000),
                        campaign.Amount(usd_nano=10000000000, credits=1000))
    authority.install(source, controller)
    values = dict(speccheck_mode='live', runs_dir=tmp_path / 'runs', cache_dir=tmp_path / 'cache', nebius_sa_id='fixture-sa',
                  nebius_public_key_id='fixture-public-id', nebius_project_id='fixture-project',
                  speccheck_image='example.test/speccheck@sha256:' + 'a' * 64, speccheck_url='https://speccheck.test',
                  controller_state_dir=controller,
                  campaign_budget_file=controller / 'campaign.sqlite3', budget_usd_per_run=3.0,
                  budget_usd_per_day=8.0, budget_tavily_credits_per_item=60.0, budget_tavily_credits_per_day=600.0)
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    for key in ('nebius_api_key', 'tavily_api_key', 'admin_token', 'nebius_private_key', 'worker_token'):
        monkeypatch.setattr(settings, key, SecretStr(f'fixture-only-{key}'))
    for key in ('nebius_api_key', 'tavily_api_key', 'worker_token'):
        monkeypatch.setattr(settings, f'nebius_secret_{key}', f'fixture-selector-{key}')
    monkeypatch.setattr(settings, 'nebius_job_state_map', {'fixture-starting': 'starting', 'fixture-running': 'running',
                                                       'fixture-failure': 'failed', 'COMPLETED': 'done'})
    main._uploads_by_ip.clear()
    with TestClient(main.app) as client:
        client.headers.update({'X-Admin-Token': 'fixture-only-admin_token', 'Idempotency-Key': 'fixture-request'})
        yield client, tmp_path


def commands(folder):
    return [json.loads(line) for line in (folder / 'calls.jsonl').read_text().splitlines()]


def signed(client, job, action, payload, *, body=None):
    raw = body or json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return client.post(f'/api/watch/leases/{job.lease_id}/{action}', content=raw,
        headers={'Content-Type': 'application/json', 'X-Worker-Signature': job_control.signature(job.lease_id, action, raw),
                 'X-Worker-Proof': job_control.signature(job.lease_id, action, b'')})


def report_for(client, job, *, unknown=False, invalid=False):
    session = uuid.uuid4().hex
    assert signed(client, job, 'claim', {'session': session}).status_code == 200
    stamp = datetime.now(timezone.utc)
    content = b'Synthetic current product: still available and unchanged.'
    digest = hashlib.sha256(content).hexdigest()
    relative = f'{job.ids[0]}/{stamp.strftime("%Y%m%dT%H%M%SZ")}/{digest}.txt'
    evidence = Evidence(url='https://maker.test/current.pdf', tier='manufacturer', title='Synthetic source',
                        sha256=digest, archived_path=relative, retrieved_at=stamp.isoformat())
    wallet = campaign.State(seed=campaign.Amount(), day_seed={}, limit=job.allowance,
        phases={'engineering': job.allowance, 'final': campaign.Amount()}, blocked=True)
    wallet.payments['known'] = campaign.Payment(run='worker-run', item=job.ids[0], day=stamp.date().isoformat(),
        phase='engineering', owner='synthetic-worker', held=campaign.Amount(usd_nano=100000000, credits=4),
        actual=campaign.Amount(usd_nano=20000000, credits=3))
    if unknown:
        wallet.payments['unknown'] = campaign.Payment(run='worker-run', item=job.ids[0], day=stamp.date().isoformat(),
            phase='engineering', owner='synthetic-worker', held=campaign.Amount(usd_nano=50000000), unknown=True)
    results = {key: Result(case_id=key, title='Synthetic worker result', mode='live', validity='invalid' if invalid else 'valid',
        config_hash=job.manifest['config_hash'], decision='approve', summary='Synthetic current product',
        fresh_model_cost_usd=0.02 if key == job.ids[0] else 0, fresh_web_credits=3 if key == job.ids[0] else 0,
        findings=[Finding(id=check, check=check, verdict='pass', severity='info', title=check, evidence=[evidence])
                  for check in ('currency', 'status')]) for key in job.ids}
    return job_control.WorkerReport(session=session, run_id='worker-run', checked_at=stamp.isoformat(),
        manifest=job.manifest, wallet=wallet, results=results,
        artifacts={relative: base64.b64encode(content).decode()}, duration_ms=1234).model_dump(mode='json')


def poll(client, folder, monkeypatch, state='COMPLETED'):
    (folder / 'state').write_text(state)
    monkeypatch.setattr(cloud_jobs, '_last_poll', 0)
    return client.get('/api/watch/jobs')


def test_create_reserves_before_cli_has_no_controller_mount_or_admin_and_forwards_profile(cloud, caplog, monkeypatch):
    client, folder = cloud
    monkeypatch.setattr(settings, 'model_write', settings.model_triage)
    monkeypatch.setattr(settings, 'nebius_base_url', 'https://factory.test/v1/')
    assert client.get('/api/project').json()['jobs_available']
    response = client.post('/api/watch/run')
    assert response.status_code == 200
    job = response.json()
    assert job['id'] == 'fixture-job-id'
    assert 'lease_id' not in job and 'manifest' not in job
    held = campaign.status(settings.campaign_budget_file)
    assert held['held_usd'] == 3 and held['held_credits'] == 60
    create = next(c for c in commands(folder) if c[:3] == ['ai', 'job', 'create'])
    assert create.count('--env-secret') == 3 and '--volume' not in create
    assert any(arg.startswith('WORKER_TOKEN=fixture-selector') for arg in create)
    assert not any(arg.startswith(('ADMIN_TOKEN=', 'EVIDENCE_DIR=', 'CONTROLLER_STATE_DIR=')) for arg in create)
    assert 'MODEL_WRITE=' + settings.model_triage in create and 'NEBIUS_BASE_URL=https://factory.test/v1/' in create
    assert 'BUDGET_USD_PER_DAY=3.0' in create and 'BUDGET_TAVILY_CREDITS_PER_DAY=60' in create
    assert all(any(arg.startswith(name + '=') for arg in create) for name in ('MAX_OUTPUT_TOKENS', 'FIX_CREDIT_CAP', 'FIX_MAX_CANDIDATES', 'MAP_MAX_DEPTH'))
    assert not any('fixture-only' in arg for arg in create)
    assert 'fixture-only' not in caplog.text + response.text
    assert client.post('/api/watch/run').json() == job
    assert sum(c[:3] == ['ai', 'job', 'create'] for c in commands(folder)) == 1
    assert client.post('/api/watch/run', headers={'Idempotency-Key': 'another'}).status_code == 409


def test_worker_report_waits_for_cloud_end_then_settles_and_publishes_atomically(cloud, monkeypatch):
    client, folder = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    payload = report_for(client, job)
    accepted = signed(client, job, 'report', payload)
    assert accepted.status_code == 200 and not accepted.json()['published']
    assert client.get('/api/watch').status_code == 404
    assert campaign.status(settings.campaign_budget_file)['held_usd'] == 3
    response = poll(client, folder, monkeypatch)
    assert response.status_code == 200 and response.json()['jobs'][0]['state'] == 'done'
    status = campaign.status(settings.campaign_budget_file)
    assert status['total_usd'] == 0.02 and status['total_credits'] == 3 and not status['held_usd'] and not status['blocked']
    assert client.get('/api/watch').json()['job_name'] == job.name
    assert all((settings.evidence_dir / name).exists() for name in payload['artifacts'])
    assert signed(client, job, 'report', payload).json()['published']
    assert campaign.status(settings.campaign_budget_file) == status
    payload['duration_ms'] += 1
    assert signed(client, job, 'report', payload).status_code == 409


def test_restart_keeps_allowance_and_one_worker_claim(cloud, monkeypatch):
    client, folder = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    session = uuid.uuid4().hex
    claim = {'session': session}
    assert signed(client, job, 'claim', claim).status_code == 200
    monkeypatch.setattr(campaign, 'SESSION', 'restarted-controller')
    assert not campaign.status(settings.campaign_budget_file)['blocked']  # Its bounded escrow survives the controller process.
    assert signed(client, job, 'claim', claim).status_code == 200
    assert signed(client, job, 'claim', {'session': uuid.uuid4().hex}).status_code == 409
    assert client.post('/api/watch/run').json()['name'] == job.name
    assert sum(c[:3] == ['ai', 'job', 'create'] for c in commands(folder)) == 1


@pytest.mark.parametrize('unknown,invalid', [(True, False), (False, True)])
def test_incomplete_worker_never_publishes_no_change_and_known_usage_is_retained(cloud, monkeypatch, unknown, invalid):
    client, folder = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    payload = report_for(client, job, unknown=unknown, invalid=invalid)
    assert signed(client, job, 'report', payload).status_code == 200
    assert poll(client, folder, monkeypatch).status_code == 200
    status = campaign.status(settings.campaign_budget_file)
    assert client.get('/api/watch').status_code == 404
    assert status['usd'] == 0.02 and status['credits'] == 3
    assert status['blocked'] is unknown
    assert status['held_usd'] == (2.98 if unknown else 0)
    assert job_control.records()[0].settled is (not unknown)


def test_cloud_completion_without_worker_accounting_keeps_hold(cloud, monkeypatch):
    client, folder = cloud
    client.post('/api/watch/run')
    assert poll(client, folder, monkeypatch).status_code == 200
    status = campaign.status(settings.campaign_budget_file)
    assert status['held_usd'] == 3 and status['blocked']
    assert client.get('/api/watch').status_code == 404
    assert client.post('/api/watch/run', headers={'Idempotency-Key': 'another'}).status_code == 409
    assert client.post('/api/watch/run').status_code == 200  # An identical launch only returns the existing job.


def test_unauthorized_or_unpinned_or_corrupt_authority_sends_no_create(cloud, monkeypatch):
    client, folder = cloud
    assert client.post('/api/watch/run', headers={'X-Admin-Token': 'wrong'}).status_code == 403
    assert client.post('/api/watch/run', headers={'Idempotency-Key': ''}).status_code == 400
    with monkeypatch.context() as patch:
        patch.setattr(settings, 'speccheck_image', 'example.test/app:latest')
        assert client.post('/api/watch/run').status_code == 409
    (settings.controller_state_dir / 'authority.json').write_text('corrupt')
    assert client.post('/api/watch/run').status_code == 503
    assert not any(c[:3] == ['ai', 'job', 'create'] for c in commands(folder))


def test_controller_rejects_legacy_publish_and_worker_cannot_use_admin_endpoint(cloud):
    client, _ = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    assert client.post('/api/watch/report', json={'checked_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'live', 'runner': 'synthetic', 'items': []}).status_code == 409
    assert client.post('/api/watch/run', headers={'X-Admin-Token': settings.secret('worker_token')}).status_code == 403
    assert client.post(f'/api/watch/leases/{job.lease_id}/claim', json={'session': uuid.uuid4().hex}).status_code == 403
    assert client.post(f'/api/watch/leases/{job.lease_id}/claim', content=b'{}',
                       headers={'X-Worker-Proof': 'z' * 64}).status_code == 403


def test_evidence_failure_retains_durable_receipt_and_hold_until_identical_retry(cloud, monkeypatch):
    client, folder = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    payload = report_for(client, job)
    assert poll(client, folder, monkeypatch).status_code == 200
    original = settings.evidence_dir
    monkeypatch.setattr(settings, 'evidence_dir', None)
    assert signed(client, job, 'report', payload).status_code == 503
    stored = job_control.records()[0]
    assert stored.report_hash and not stored.settled
    status = campaign.status(settings.campaign_budget_file)
    assert status['held_usd'] == 3 and status['blocked']
    monkeypatch.setattr(settings, 'evidence_dir', original)
    assert signed(client, job, 'report', payload).json()['published']


@pytest.mark.parametrize('fault', ['missing', 'corrupt'])
def test_receipt_loss_blocks_other_paid_work_until_original_receipt_is_restored(cloud, monkeypatch, fault):
    client, folder = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    payload = report_for(client, job)
    assert signed(client, job, 'report', payload).status_code == 200
    stored = job_control.records()[0]
    receipt = settings.controller_state_dir / stored.report_path
    original = receipt.read_bytes()
    if fault == 'missing':
        receipt.unlink()
    else:
        receipt.write_bytes(b'corrupt')
    assert poll(client, folder, monkeypatch).status_code == 503
    status = campaign.status(settings.campaign_budget_file)
    assert status['blocked'] and status['held_usd'] == 3
    assert job_control.records()[0].reconciliation_required
    with pytest.raises(BudgetExceeded, match='reconciliation'):
        campaign.reserve(settings.campaign_budget_file, campaign.Amount(usd_nano=1), run='other', item='other',
                         run_usd_nano=3000000000, day_usd_nano=8000000000, item_credits=60, day_credits=600, scopes=[])
    assert client.get('/api/watch').status_code == 404
    assert poll(client, folder, monkeypatch).status_code == 503
    receipt.write_bytes(original)
    assert poll(client, folder, monkeypatch).json()['jobs'][0]['state'] == 'done'
    assert not campaign.status(settings.campaign_budget_file)['blocked']
    assert not job_control.records()[0].reconciliation_required


@pytest.mark.parametrize('url', ['https://controller.test/subpath', 'https://@controller.test',
                                 'https://controller.test:invalid', 'https://controller.test/#fragment'])
def test_bad_controller_origin_is_rejected_before_reserving_or_creating(cloud, monkeypatch, url):
    client, folder = cloud
    monkeypatch.setattr(settings, 'speccheck_url', url)
    assert client.post('/api/watch/run').status_code == 409
    assert not campaign.status(settings.campaign_budget_file)['held_usd']
    assert not any(c[:3] == ['ai', 'job', 'create'] for c in commands(folder))


def test_ambiguous_creation_keeps_full_allowance_and_blocks_paid_work(cloud, monkeypatch):
    client, _ = cloud
    calls = []
    async def unconfirmed(*args):
        calls.append(args)
        return '{"id":"operation-only"}'
    monkeypatch.setattr(cloud_jobs, 'cli', unconfirmed)
    response = client.post('/api/watch/run')
    assert response.status_code == 200 and not response.json()['state_known']
    status = campaign.status(settings.campaign_budget_file)
    assert status['held_usd'] == 3 and status['blocked']
    assert client.post('/api/watch/run').json()['name'] == response.json()['name']
    assert sum(args[:3] == ('ai', 'job', 'create') for args in calls) == 1


def test_receipt_directories_are_synced_before_metadata_commit(cloud, monkeypatch):
    client, _ = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    payload = report_for(client, job)
    synced = []
    original = authority.sync_directory
    def sync(directory):
        synced.append(directory)
        original(directory)
    monkeypatch.setattr(authority, 'sync_directory', sync)
    assert signed(client, job, 'report', payload).status_code == 200
    assert synced == [settings.controller_state_dir / 'reports' / job.lease_id,
                      settings.controller_state_dir / 'reports', settings.controller_state_dir]


def test_receipt_sync_failure_blocks_paid_work_and_identical_retry_can_recover(cloud, monkeypatch):
    client, folder = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    payload = report_for(client, job)
    original = job_control.os.fsync
    def fail(_):
        raise OSError('Synthetic disk sync failure')
    monkeypatch.setattr(job_control.os, 'fsync', fail)
    assert signed(client, job, 'report', payload).status_code == 503
    stored = job_control.records()[0]
    assert stored.report_path is None and stored.reconciliation_required
    status = campaign.status(settings.campaign_budget_file)
    assert status['blocked'] and status['held_usd'] == 3
    monkeypatch.setattr(job_control.os, 'fsync', original)
    assert signed(client, job, 'report', payload).status_code == 200
    assert poll(client, folder, monkeypatch).json()['jobs'][0]['state'] == 'done'
    assert not campaign.status(settings.campaign_budget_file)['blocked']


def test_worker_settlement_preserves_original_utc_payment_day(cloud):
    client, _ = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    payload = report_for(client, job)
    previous = datetime.now(timezone.utc) - timedelta(days=1)
    with campaign.transaction(settings.campaign_budget_file) as state:
        state.jobs[job.lease_id].created_at = previous.isoformat()
        state.payments[job.payment_id].day = previous.date().isoformat()
    payload['wallet']['payments']['known']['day'] = previous.date().isoformat()
    assert signed(client, job, 'report', payload).status_code == 200
    job_control.observe(job.lease_id, state='done', cloud_terminal=True)
    with campaign.transaction(settings.campaign_budget_file) as state:
        old = campaign.report(state, previous.date().isoformat())
        today = campaign.report(state, datetime.now(timezone.utc).date().isoformat())
    assert old['usd'] == 0.02 and old['credits'] == 3
    assert today['usd'] == 0 and today['credits'] == 0 and today['total_usd'] == 0.02


@pytest.mark.parametrize('field,value', [('report_path', '../private.json'), ('report_hash', 'bad'), ('report_digest', None)])
def test_receipt_identity_cannot_escape_private_storage_or_be_partial(cloud, field, value):
    client, _ = cloud
    client.post('/api/watch/run')
    job = job_control.records()[0]
    assert signed(client, job, 'report', report_for(client, job)).status_code == 200
    with pytest.raises(BudgetExceeded):
        with campaign.transaction(settings.campaign_budget_file) as state:
            setattr(state.jobs[job.lease_id], field, value)


def test_independent_concurrent_admissions_and_history_survive_public_five_job_limit(cloud, monkeypatch):
    client, _ = cloud
    monkeypatch.setattr(settings, 'watch_run_interval_s', 0)
    def admit(index):
        try:
            return job_control.reserve(f'parallel-{index}')[1]
        except Exception as error:
            assert getattr(error, 'status_code', None) == 409
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(admit, range(2))) == 1
    first = job_control.records()[0]
    for _ in range(6):
        job = job_control.records()[0]
        payload = report_for(client, job)
        job_control.receive(job.lease_id, job_control.WorkerReport.model_validate(payload), hashlib.sha256(json.dumps(payload).encode()).hexdigest())
        job_control.observe(job.lease_id, state='done', raw_state='COMPLETED', cloud_terminal=True)
        if _ < 5:
            job_control.reserve(f'next-{_}')
    assert len(job_control.records()) == 6
    assert len(client.get('/api/watch/jobs').json()['jobs']) == 5
    assert job_control.reserve(first.request_id)[1] is False

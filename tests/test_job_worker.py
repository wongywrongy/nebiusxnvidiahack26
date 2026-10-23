import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import httpx
import pytest
from pydantic import SecretStr

from api import archive, job_control, job_worker
from api.config import settings
from api.providers import budget, campaign
from api.providers.budget import BudgetExceeded
from api.readiness import CONFIG_FIELDS, manifest
from api.schemas import Evidence, Finding, Result
from scripts import recheck

pytestmark = pytest.mark.campaign


@pytest.fixture
def worker(tmp_path, monkeypatch):
    # execute applies the leased profile; restore every setting it can change after the test.
    for name in (*CONFIG_FIELDS, 'speccheck_mode', 'model_triage', 'model_extract', 'model_verify', 'model_write',
                 'campaign_budget_file', 'cache_dir', 'runs_dir', 'evidence_dir', 'evidence_label'):
        monkeypatch.setattr(settings, name, getattr(settings, name))
    monkeypatch.setattr(settings, 'controller_state_dir', None)
    monkeypatch.setattr(settings, 'admin_token', SecretStr(''))
    monkeypatch.setattr(settings, 'worker_token', SecretStr('synthetic-worker-credential'))
    monkeypatch.setattr(settings, 'nebius_api_key', SecretStr('synthetic-nebius-key'))
    monkeypatch.setattr(settings, 'tavily_api_key', SecretStr('synthetic-tavily-key'))
    monkeypatch.setattr(settings, 'budget_usd_per_day', 3.0)
    monkeypatch.setattr(settings, 'budget_usd_per_run', 3.0)
    monkeypatch.setattr(settings, 'budget_tavily_credits_per_day', 60.0)
    monkeypatch.setattr(settings, 'budget_tavily_credits_per_item', 60.0)
    local = tmp_path / 'child'
    local.mkdir()
    monkeypatch.setattr(job_worker.tempfile, 'mkdtemp', lambda **_: str(local))
    lease_id = uuid.uuid4().hex
    lease = {'lease_id': lease_id, 'job_name': 'synthetic-job', 'ids': ['synthetic-item'],
             'manifest': json.loads(json.dumps(manifest())), 'allowance': {'usd_nano': 3000000000, 'credits': 60}}
    return lease, local


def test_worker_uses_only_its_allowance_seals_before_report_and_does_not_publish_locally(worker, monkeypatch):
    lease, local = worker
    seen = []
    async def check(ids):
        led = budget.LEDGER.set(budget.Ledger('worker-run'))
        item = budget.ITEM.set(ids[0])
        try:
            ticket = budget.reserve_payment(usd=0.1, credits=4)
            budget.settle_payment(ticket, usd=0.02, credits=3)
            relative = archive.save(ids[0], b'Synthetic manufacturer source', 'txt')
            source = Evidence(url='https://maker.test/current.pdf', tier='manufacturer', title='Synthetic source', archived_path=relative)
            result = Result(case_id=ids[0], mode='live', validity='valid', config_hash=lease['manifest']['config_hash'],
                title='Synthetic product', decision='approve', summary='Synthetic current product',
                fresh_model_cost_usd=0.02, fresh_web_credits=3,
                findings=[Finding(id=name, check=name, verdict='pass', severity='info', title=name, evidence=[source])
                          for name in ('currency', 'status')])
            return {'items': [{'id': ids[0], 'status': 'no_change'}]}, SimpleNamespace(id='worker-run', results={ids[0]: result})
        finally:
            budget.LEDGER.reset(led)
            budget.ITEM.reset(item)
    monkeypatch.setattr(recheck, 'check', check)
    def controller(request):
        action = request.url.path.rsplit('/', 1)[-1]
        assert request.headers['X-Worker-Signature'] == job_control.signature(lease['lease_id'], action, request.content)
        assert request.headers['X-Worker-Proof'] == job_control.signature(lease['lease_id'], action, b'')
        payload = json.loads(request.content)
        seen.append((action, payload))
        if action == 'claim':
            return httpx.Response(200, json=lease)
        assert campaign.status(settings.campaign_budget_file)['blocked']
        with pytest.raises(BudgetExceeded):
            campaign.reserve(settings.campaign_budget_file, campaign.Amount(usd_nano=1), run='after-seal', item=lease['ids'][0],
                run_usd_nano=3000000000, day_usd_nano=3000000000, item_credits=60, day_credits=60, scopes=[])
        assert payload['wallet']['blocked'] and payload['wallet']['limit'] == lease['allowance']
        assert payload['wallet']['payments'] and payload['artifacts']
        return httpx.Response(200, json={'accepted': True, 'settled': False, 'published': False})
    async def run():
        async with httpx.AsyncClient(base_url='https://controller.test', transport=httpx.MockTransport(controller)) as client:
            return await job_worker.execute(client, lease['lease_id'])
    assert asyncio.run(run()) == 0
    assert [action for action, _ in seen] == ['claim', 'report']
    assert seen[0][1]['session'] == seen[1][1]['session']
    assert not (local / 'runs/watch/latest.json').exists()
    assert not (local / 'evidence/watch/latest.json').exists()
    assert (local / 'report.json').exists()


def test_worker_pipeline_crash_still_reports_sealed_known_accounting(worker, monkeypatch):
    lease, _ = worker
    async def failed(_):
        raise RuntimeError('Synthetic internal failure')
    monkeypatch.setattr(recheck, 'check', failed)
    def controller(request):
        if request.url.path.endswith('/claim'):
            return httpx.Response(200, json=lease)
        payload = json.loads(request.content)
        assert payload['wallet']['blocked'] and payload['failure'] and payload['results'] == {}
        return httpx.Response(200, json={'accepted': True})
    async def run():
        async with httpx.AsyncClient(base_url='https://controller.test', transport=httpx.MockTransport(controller)) as client:
            return await job_worker.execute(client, lease['lease_id'])
    assert asyncio.run(run()) == 2


def test_wrong_code_manifest_prevents_provider_work(worker, monkeypatch):
    lease, local = worker
    lease['manifest']['code_hash'] = 'changed'
    async def forbidden(_):
        raise AssertionError('No work should start')
    monkeypatch.setattr(recheck, 'check', forbidden)
    async def run():
        async with httpx.AsyncClient(base_url='https://controller.test', transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=lease))) as client:
            with pytest.raises(RuntimeError, match='do not match'):
                await job_worker.execute(client, lease['lease_id'])
    asyncio.run(run())
    assert not (local / 'campaign.sqlite3').exists()


def test_worker_transport_retry_is_identical_and_redirect_does_not_forward(worker):
    lease, _ = worker
    requests = []
    def controller(request):
        requests.append(request)
        if len(requests) == 1:
            raise httpx.ReadTimeout('Synthetic lost response')
        return httpx.Response(200, json={'accepted': True})
    async def run():
        async with httpx.AsyncClient(base_url='https://controller.test', transport=httpx.MockTransport(controller)) as client:
            assert await job_worker._post(client, lease['lease_id'], 'claim', b'{"session":"synthetic"}') == {'accepted': True}
        async with httpx.AsyncClient(base_url='https://controller.test', transport=httpx.MockTransport(
                lambda _: httpx.Response(302, headers={'Location': 'https://untrusted.test'})), follow_redirects=False) as client:
            with pytest.raises(RuntimeError, match='302'):
                await job_worker._post(client, lease['lease_id'], 'report', b'{}')
    asyncio.run(run())
    assert len(requests) == 2 and requests[0].content == requests[1].content
    assert requests[0].headers['X-Worker-Signature'] == requests[1].headers['X-Worker-Signature']


@pytest.mark.parametrize('url', ['http://controller.test', 'https://user:pass@controller.test', 'https://controller.test?key=private',
                                 'https://controller.test/subpath', 'https://@controller.test', 'https://controller.test:invalid'])
def test_worker_rejects_unsafe_controller_origin_without_network(url):
    with pytest.raises(RuntimeError, match='HTTPS origin'):
        asyncio.run(job_worker.run(url, 'a' * 32))

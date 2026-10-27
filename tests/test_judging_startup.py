import hashlib
import json

import pytest

from api.config import settings
from api.providers import campaign
from scripts import campaign_budget, serve

pytestmark = pytest.mark.campaign


def test_judging_cli_creates_only_a_fresh_allowance_and_refuses_replacement(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'judging.sqlite3'
    monkeypatch.setattr(settings, 'campaign_budget_file', path)
    monkeypatch.setattr('sys.argv', ['campaign_budget.py', 'init-judging', '--usd', '75', '--credits', '6000'])
    campaign_budget.cli()
    report = json.loads(capsys.readouterr().out)
    assert report['total_usd'] == report['total_credits'] == 0
    assert report['usd_limit'] == report['phase_usd_limit'] == 75
    assert report['credit_limit'] == report['phase_credit_limit'] == 6000 and not report['blocked']
    with campaign.transaction(path) as state:
        assert not state.day_seed and not state.payments and state.seed == campaign.Amount()
    with pytest.raises(SystemExit, match='File exists'):
        campaign_budget.cli()
    assert campaign.status(path) == report


def test_plain_startup_seeds_locked_pages_and_preserves_allowance_and_uploads(tmp_path, monkeypatch):
    image, mounted = tmp_path / 'image', tmp_path / 'state'
    (image / 'raw').mkdir(parents=True)
    mounted.mkdir()
    data = b'Synthetic public document bytes for storage test only'
    (image / 'raw/product.pdf').write_bytes(data)
    (image / 'documents.lock.json').write_text(json.dumps({'documents': {
        'product.pdf': {'sha256': hashlib.sha256(data).hexdigest()}}}))
    for field, value in {'data_dir': image, 'raw_dir': image/'raw', 'uploads_dir': image/'raw/uploads',
                         'cache_dir': image/'cache', 'runs_dir': image/'runs', 'scores_file': image/'runs/scores.json',
                         'campaign_budget_file': image/'absent.sqlite3', 'app_state_dir': mounted,
                         'controller_state_dir': None, 'judging_usd': 75, 'judging_credits': 6000}.items():
        monkeypatch.setattr(settings, field, value)
    recorded = settings.recorded_dir
    serve.prepare_judging()
    assert settings.raw_dir == mounted/'raw' and settings.uploads_dir == mounted/'raw/uploads'
    assert settings.recorded_dir == recorded and (settings.raw_dir/'product.pdf').read_bytes() == data
    marker = settings.uploads_dir/'retained.pdf'
    marker.write_bytes(b'Existing upload; never overwrite')
    identifier = campaign.reserve(settings.campaign_budget_file, campaign.Amount(usd_nano=100000000), run='test', item='test',
        run_usd_nano=3000000000, day_usd_nano=8000000000, item_credits=60, day_credits=600, scopes=[])
    campaign.settle(settings.campaign_budget_file, identifier, campaign.Amount(usd_nano=20000000))
    before = campaign.status(settings.campaign_budget_file)
    serve.prepare_judging()
    assert campaign.status(settings.campaign_budget_file) == before and before['total_usd'] == 0.02
    assert marker.read_bytes() == b'Existing upload; never overwrite'
    (settings.raw_dir/'product.pdf').write_bytes(b'Corrupt stored source')
    with pytest.raises(ValueError, match='differs'):
        serve.prepare_judging()


def test_partial_judging_config_does_not_start_or_initialize(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'judging_usd', 75)
    monkeypatch.setattr(settings, 'judging_credits', None)
    monkeypatch.setattr(settings, 'campaign_budget_file', tmp_path/'absent.sqlite3')
    with pytest.raises(ValueError, match='both'):
        serve.prepare_judging()
    assert not settings.campaign_budget_file.exists()

"""The scheduled fallback spends once per day and stops at the approved availability date."""

import datetime
from pathlib import Path

import httpx
import pytest
import respx
import yaml


@pytest.mark.parametrize('report,expired,needed', [
    ({}, False, True),
    ({'mode': 'live', 'runner': 'GitHub Actions', 'checked_at': '2026-10-28T09:00:00+00:00'}, False, False),
    ({'mode': 'mock', 'runner': 'GitHub Actions', 'checked_at': '2026-10-28T09:00:00+00:00'}, False, True),
    ({}, True, False),
])
def test_fallback_admission(report, expired, needed, monkeypatch, tmp_path):
    original = datetime.datetime

    class Clock(original):
        @classmethod
        def now(cls, tz=None):
            return original(2026, 12, 15, 20, tzinfo=tz) if expired else original(2026, 10, 28, 9, tzinfo=tz)

    monkeypatch.setattr(datetime, 'datetime', Clock)
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    monkeypatch.setenv('SPECCHECK_URL', 'https://example.test')
    workflow = yaml.safe_load((Path(__file__).resolve().parents[1] / '.github/workflows/daily-recheck.yml').read_text())
    script = workflow['jobs']['recheck']['steps'][0]['run'].split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    with respx.mock:
        respx.get('https://example.test/api/watch').mock(return_value=httpx.Response(200 if report else 404, json=report))
        exec(compile(script, 'daily-recheck-preflight', 'exec'), {})
    assert output.read_text().strip() == f'needed={str(needed).lower()}'

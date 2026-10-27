import asyncio
import json
import sys

import pytest

from api.config import settings
from api.pipeline import runner, verify
from api.pipeline.cases import all_cases
from api.llm import router
from api import release
from scripts import eval as evaluate


def test_external_catalog_runs_without_labels_or_global_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "speccheck_mode", "mock")
    monkeypatch.setattr(settings, "runs_dir", tmp_path / "runs")
    monkeypatch.setattr(settings, "scores_file", tmp_path / "public-scores.json")
    monkeypatch.setattr(runner, "get_case", lambda _: pytest.fail("External input reached the demonstration catalog"))
    case = {**all_cases()["c01"], "id": "synthetic-new", "fixture": "c01"}
    canary = "PRIVATE_LABEL_MUST_NEVER_ENTER_A_MODEL_MESSAGE"
    case["expected"] = {**case["expected"], "audit_canary": canary}
    original_verify = verify.verify
    original_call = router.call
    seen = []

    async def checked_call(*args, **kwargs):
        assert canary not in json.dumps([args, kwargs], default=str)
        return await original_call(*args, **kwargs)

    async def checked_verify(package, *args, **kwargs):
        assert "expected" not in package
        seen.append(package["id"])
        return await original_verify(package, *args, **kwargs)

    monkeypatch.setattr(verify, "verify", checked_verify)
    monkeypatch.setattr(router, "call", checked_call)
    output = tmp_path / "blind-score.json"
    assert asyncio.run(evaluate.main([case["id"]], output, catalog={case["id"]: case},
                                    validation_set_sha256="a" * 64)) == 0
    panel = json.loads(output.read_text())
    identity = json.loads((settings.runs_dir / panel["run_id"] / "manifest.json").read_text())
    assert seen == [case["id"]]
    assert panel["rows"][0]["expected"] == case["expected"]["decision"]
    assert identity["validation_set_sha256"] == panel["manifest"]["validation_set_sha256"] == "a" * 64
    assert not settings.scores_file.exists()
    assert "expected" in case  # Scoring labels were not mutated.


def test_blind_preflight_checks_review_without_starting_a_run(monkeypatch, capsys):
    monkeypatch.setattr(release, "_blind", lambda _: ({f"new-{n}": {} for n in range(6)}, {}, "b" * 64))
    monkeypatch.setattr(evaluate, "Run", lambda *a, **k: pytest.fail("Check-only must not start a run"))
    monkeypatch.setattr(sys, "argv", ["eval.py", "--blind-set", "/synthetic", "--check"])
    assert evaluate.cli() == 0
    assert json.loads(capsys.readouterr().out) == {
        "packages": 6, "validation_set_sha256": "b" * 64, "checked_only": True}


@pytest.mark.parametrize("fault", ["unreviewed", "mock", "mixed-suites", "check-without-set", "case-gate"])
def test_blind_cli_fails_before_execution(monkeypatch, capsys, fault):
    monkeypatch.setattr(settings, "speccheck_mode", "mock")

    def load(_):
        if fault == "unreviewed":
            raise ValueError("Owner review pending")
        return {f"new-{n}": {} for n in range(6)}, {}, "b" * 64

    monkeypatch.setattr(release, "_blind", load)
    monkeypatch.setattr(evaluate, "Run", lambda *a, **k: pytest.fail("Invalid blind evaluation started"))
    args = ["--check"] if fault == "check-without-set" else ["--blind-set", "/synthetic"]
    if fault == "mixed-suites":
        args += ["--samples"]
    if fault == "case-gate":
        args += ["--release-gate"]
    monkeypatch.setattr(sys, "argv", ["eval.py", *args])
    with pytest.raises(SystemExit) as error:
        evaluate.cli()
    assert error.value.code == 2
    assert capsys.readouterr().err

"""Accuracy pass: the L80-implies-L70 rule and the quote-gate drop-reason diagnostics. Offline only."""

import asyncio

from api.pipeline import metrics, spec_check
from api.pipeline.runner import Run, execute
from api.pipeline.scores import scores
from api.schemas import Claim, Requirement

L70 = Requirement(id="l70", section="26 51 00", paragraph="2.02.S.3", property="l70_hours", operator="gte",
                  value=50000, unit="hr", text="L70 of at least 50,000 hours")


def claim(prop, value, variant=None):
    return Claim(id=prop, product="BLT", manufacturer="Lithonia", property=prop, value=value, unit="hr",
                 variant=variant, quote=f"{prop.split('_')[0].upper()} {value} hours", page=1)


def test_l70_rule_asks_for_the_stricter_lumen_ratings_too():
    props = spec_check.properties_for([L70])
    assert {"l70_hours", "l80_hours", "l90_hours"} <= set(props)


def test_a_long_enough_l80_proves_l70():
    [f] = spec_check.check([L70], [claim("l80_hours", 60000)])
    assert f.verdict == "pass" and f.compare.right_value == "L80 60000 hr" and f.claim_ids == ["l80_hours"]


def test_a_short_l80_or_an_option_only_l80_proves_nothing():
    [short] = spec_check.check([L70], [claim("l80_hours", 40000)])
    [option] = spec_check.check([L70], [claim("l80_hours", 60000, variant="HE driver")])
    assert short.verdict == "unverified" and option.verdict == "unverified"


def test_a_stated_l70_still_wins_and_can_still_fail():
    [f] = spec_check.check([L70], [claim("l70_hours", 36000), claim("l80_hours", 60000)])
    assert f.verdict == "fail"


def test_lte_rules_never_use_the_implication():
    lte = L70.model_copy(update={"operator": "lte"})
    [f] = spec_check.check([lte], [claim("l80_hours", 60000)])
    assert f.verdict == "unverified"


def test_drop_reasons_are_recorded_per_result():
    token = metrics.REASONS.set({})
    metrics.drop("claim", "value_not_in_quote")
    metrics.drop("claim", None)
    assert metrics.REASONS.get() == {"claim:value_not_in_quote": 1}
    metrics.REASONS.reset(token)
    run = asyncio.run(execute(Run(["c03"], delay_ms=0)))
    assert isinstance(run.results["c03"].drop_reasons, dict)
    run.results["c03"].drop_reasons = {"web:quote_not_on_source": 102}
    panel = scores(run, ["c03"])  # per-item averages divide by the item count, not a drop-reason count
    assert panel["cost_usd_per_item"] == round(panel["rows"][0]["cost_usd"], 6)
    assert panel["time_ms_per_item"] == panel["rows"][0]["time_ms"]


def test_reservation_is_bounded_by_request_bytes_not_the_whole_context():
    from api.providers import tokenfactory
    model = "nvidia/Nemotron-3-Ultra-550b-a55b"
    body = {"model": model, "max_tokens": 1000, "messages": [{"role": "user", "content": "é" * 1000}]}
    bound = tokenfactory.input_token_bound(model, body)
    assert 2000 <= bound - tokenfactory.TEMPLATE_TOKENS < 2200  # 2 UTF-8 bytes per é
    huge = {**body, "messages": [{"role": "user", "content": "x" * 2_000_000}]}
    assert tokenfactory.input_token_bound(model, huge) == tokenfactory.CONTEXT_LIMITS[model]

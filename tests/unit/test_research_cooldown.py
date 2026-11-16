"""Actual-decision regressions for the research-only post-risk-off no-entry interval."""

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from packages.data.snapshots import load_dataset_snapshot
from packages.research.models import ResearchConfig
from packages.research.signals import generate_research_signals


def cooldown_case(length: int, *, repeated: bool = False, delayed: bool = False):
    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    values = yaml.safe_load(Path("experiments/configs/baseline.yaml").read_text())
    values["regime"].update(
        risk_off_confirm_closes=1,
        risk_on_confirm_closes=1,
        rv20_risk_on_max=10.0,
        rv20_risk_off_min=20.0,
        risk_off_cooldown_days=length,
    )
    proxy = list(snapshot.feature_bars_by_symbol["SPY"])
    changes = {199: 80.0, 200: 110.0}
    if repeated:
        changes.update({201: 80.0, 202: 110.0})
    for index, close in changes.items():
        proxy[index] = proxy[index].model_copy(
            update={"open": close, "high": close + 1, "low": close - 1, "close": close}
        )
    bars = {**snapshot.feature_bars_by_symbol, "SPY": tuple(proxy)}
    availability = dict(snapshot.availability_by_key)
    if delayed:
        availability[("SPY", snapshot.sessions[200].date)] = snapshot.sessions[201].close_at
    snapshot = replace(snapshot, feature_bars_by_symbol=bars, availability_by_key=availability)
    return snapshot, ResearchConfig.model_validate(values)


@pytest.mark.parametrize("length", [0, 1, 3])
def test_nonconfirming_caution_is_blocked_for_exact_cooldown(length: int) -> None:
    snapshot, config = cooldown_case(length)
    result = generate_research_signals(snapshot, config)
    decisions = {d.decision_session: d for d in result.decisions if d.symbol == "QQQ"}
    assert not decisions[snapshot.sessions[199].date].accepted
    for index in range(200, 200 + length):
        decision = decisions[snapshot.sessions[index].date]
        assert not decision.accepted
        assert "regime_blocks_new_entries" in decision.reason_codes
    # Session 200 is CAUTION without risk-on confirmation; length0 allows its half-sized entry.
    assert decisions[snapshot.sessions[200 + length].date].accepted
    if length == 0:
        assert decisions[snapshot.sessions[200].date].quantity == 1


@pytest.mark.parametrize("length", [0, 1, 3])
def test_repeated_risk_off_restarts_the_entire_subsequent_interval(length: int) -> None:
    snapshot, config = cooldown_case(length, repeated=True)
    result = generate_research_signals(snapshot, config)
    decisions = {d.decision_session: d for d in result.decisions if d.symbol == "QQQ"}
    assert not decisions[snapshot.sessions[201].date].accepted
    for index in range(202, 202 + length):
        assert not decisions[snapshot.sessions[index].date].accepted
        assert "regime_blocks_new_entries" in decisions[snapshot.sessions[index].date].reason_codes
    assert decisions[snapshot.sessions[202 + length].date].accepted


@pytest.mark.parametrize("length", [0, 1, 3])
def test_missing_proxy_blocks_entries_but_consumes_one_calendar_session(length: int) -> None:
    snapshot, config = cooldown_case(length, delayed=True)
    result = generate_research_signals(snapshot, config)
    decisions = {d.decision_session: d for d in result.decisions if d.symbol == "QQQ"}
    assert not decisions[snapshot.sessions[200].date].accepted
    assert "incomplete_feature_history" in decisions[snapshot.sessions[200].date].reason_codes
    for index in range(201, 200 + length):
        assert not decisions[snapshot.sessions[index].date].accepted
    assert decisions[snapshot.sessions[max(201, 200 + length)].date].accepted


def test_nonconfirming_conditions_persist_across_multiple_caution_sessions() -> None:
    snapshot, config = cooldown_case(3)
    bars = dict(snapshot.feature_bars_by_symbol)
    proxy = list(bars["SPY"])
    for index in (201, 202):
        proxy[index] = proxy[index].model_copy(
            update={"open": 110.0, "high": 111.0, "low": 109.0, "close": 110.0}
        )
    bars["SPY"] = tuple(proxy)
    result = generate_research_signals(replace(snapshot, feature_bars_by_symbol=bars), config)
    decisions = {d.decision_session: d for d in result.decisions if d.symbol == "QQQ"}
    assert all(not decisions[snapshot.sessions[i].date].accepted for i in (200, 201, 202))
    assert decisions[snapshot.sessions[203].date].accepted

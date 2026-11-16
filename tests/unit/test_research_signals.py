"""Real strategy/risk tests: warm-up, availability, exclusions and deterministic cutoffs."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

FIXTURE = Path("tests/fixtures/market_snapshot/manifest.json")


def configuration(**updates: object):
    from packages.research.models import ResearchConfig

    values = yaml.safe_load(Path("experiments/configs/baseline.yaml").read_text())
    values.update(updates)
    return ResearchConfig.model_validate(values)


def test_real_helpers_produce_auditable_warmup_and_accepted_signals() -> None:
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(FIXTURE)
    result = generate_research_signals(snapshot, configuration())
    assert result == generate_research_signals(snapshot, configuration())
    assert result.accepted_signals
    first = result.decisions[0]
    assert "insufficient_warmup" in first.reason_codes
    accepted = result.accepted_signals[0]
    assert accepted.quantity > 0
    assert accepted.eligible_session > accepted.decision_session
    assert accepted.decision_at > snapshot.session_by_date[accepted.decision_session].close_at
    assert all(d.symbol == "QQQ" for d in result.accepted_signals)
    assert any(
        "earnings_unknown" in d.reason_codes
        for d in result.rejected_decisions
        if d.symbol == "AAPL"
    )
    assert len(result.decisions) == 630


def test_future_prices_cannot_change_past_decisions() -> None:
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(FIXTURE)
    cutoff = snapshot.sessions[202].date
    future = {
        symbol: tuple(
            b
            if b.date <= cutoff
            else b.model_copy(
                update={"open": 999.0, "high": 1000.0, "low": 998.0, "close": 999.0, "volume": 1}
            )
            for b in bars
        )
        for symbol, bars in snapshot.feature_bars_by_symbol.items()
    }
    changed = replace(snapshot, feature_bars_by_symbol=future)
    before = generate_research_signals(snapshot, configuration())
    after = generate_research_signals(changed, configuration())
    assert tuple(d for d in before.decisions if d.decision_session <= cutoff) == tuple(
        d for d in after.decisions if d.decision_session <= cutoff
    )


def test_delayed_observation_cannot_enter_features_early() -> None:
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(FIXTURE)
    session = snapshot.sessions[199]
    availability = dict(snapshot.availability_by_key)
    availability[("QQQ", session.date)] = session.close_at + timedelta(days=3)
    changed = replace(snapshot, availability_by_key=availability)
    result = generate_research_signals(changed, configuration())
    decision = next(
        d for d in result.decisions if d.symbol == "QQQ" and d.decision_session == session.date
    )
    assert not decision.accepted
    assert "observation_unavailable" in decision.reason_codes


def test_symbol_and_sizing_exclusions_are_recorded() -> None:
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(FIXTURE)
    result = generate_research_signals(snapshot, configuration(approved_symbols=["SPY"]))
    assert not result.accepted_signals
    assert any("symbol_not_approved" in d.reason_codes for d in result.rejected_decisions)
    tiny = generate_research_signals(snapshot, configuration(initial_cash=1))
    assert any("position_size_below_one_share" in d.reason_codes for d in tiny.rejected_decisions)


def test_config_rejects_unsupported_feature_periods() -> None:
    values = yaml.safe_load(Path("experiments/configs/baseline.yaml").read_text())
    values["strategy"]["trend_fast_ma"] = 20
    from packages.research.models import ResearchConfig

    with pytest.raises(ValueError, match="unsupported_feature_periods"):
        ResearchConfig.model_validate(values)


@pytest.mark.parametrize("cooldown_days", [0, 1, 3])
def test_regime_cooldown_survives_intermediate_caution_sessions(cooldown_days: int) -> None:
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(FIXTURE)
    bars = dict(snapshot.feature_bars_by_symbol)
    proxy = list(bars["SPY"])
    proxy[199] = proxy[199].model_copy(
        update={"open": 80.0, "high": 81.0, "low": 79.0, "close": 80.0}
    )
    bars["SPY"] = tuple(proxy)
    snapshot = replace(snapshot, feature_bars_by_symbol=bars)
    config = configuration()
    regime = config.regime.model_copy(
        update={
            "risk_off_confirm_closes": 1,
            "risk_on_confirm_closes": 1,
            "rv20_risk_on_max": 10.0,
            "rv20_risk_off_min": 20.0,
            "risk_off_cooldown_days": cooldown_days,
        }
    )
    result = generate_research_signals(snapshot, config.model_copy(update={"regime": regime}))
    for session in snapshot.sessions[200 : 200 + cooldown_days]:
        decision = next(
            d for d in result.decisions if d.symbol == "QQQ" and d.decision_session == session.date
        )
        assert "regime_blocks_new_entries" in decision.reason_codes
    recovered = next(
        d
        for d in result.decisions
        if d.symbol == "QQQ" and d.decision_session == snapshot.sessions[200 + cooldown_days].date
    )
    assert "regime_blocks_new_entries" not in recovered.reason_codes


def test_known_earnings_blackout_cannot_be_displaced_by_later_event() -> None:
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(FIXTURE)
    session = snapshot.sessions[199]
    known_at = snapshot.sessions[0].close_at.isoformat()
    config = configuration(
        etf_symbols=["SPY"],
        earnings=[
            {"symbol": "QQQ", "earnings_date": str(session.date), "available_at": known_at},
            {
                "symbol": "QQQ",
                "earnings_date": str(snapshot.sessions[-1].date),
                "available_at": known_at,
            },
        ],
    )
    result = generate_research_signals(snapshot, config)
    decision = next(
        d for d in result.decisions if d.symbol == "QQQ" and d.decision_session == session.date
    )
    assert not decision.accepted
    assert "earnings_blackout" in decision.reason_codes


def test_future_earnings_publication_cannot_change_an_earlier_decision() -> None:
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(FIXTURE)
    session = snapshot.sessions[199]
    baseline = generate_research_signals(snapshot, configuration(etf_symbols=["SPY"]))
    changed = generate_research_signals(
        snapshot,
        configuration(
            etf_symbols=["SPY"],
            earnings=[
                {
                    "symbol": "QQQ",
                    "earnings_date": str(session.date),
                    "available_at": snapshot.sessions[201].decision_at.isoformat(),
                }
            ],
        ),
    )
    assert tuple(d for d in baseline.decisions if d.decision_session <= session.date) == tuple(
        d for d in changed.decisions if d.decision_session <= session.date
    )

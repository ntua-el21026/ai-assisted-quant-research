"""Independent literal arithmetic, timing and accounting fixtures (absolute tolerance 1e-8)."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
import yaml

from packages.data.models import AdjustedDailyBar
from packages.data.snapshots import load_dataset_snapshot
from packages.research.models import ResearchConfig, ResearchDecision, ResearchSignalSet


def case(prices=None, *, initial_cash=10000, symbols=("QQQ",)):
    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    sessions = snapshot.sessions[:4]
    prices = prices or [
        (80, 81, 79, 80),
        (100, 103, 99, 102),
        (110, 111, 109, 110),
        (110, 111, 109, 110),
    ]
    bars = {
        s: tuple(
            AdjustedDailyBar(
                symbol=s,
                date=d.date,
                open=p[0],
                high=p[1],
                low=p[2],
                close=p[3],
                volume=1000000,
                adjusted=False,
            )
            for d, p in zip(sessions, prices, strict=True)
        )
        for s in symbols
    }
    snapshot = replace(
        snapshot,
        sessions=sessions,
        feature_bars_by_symbol=bars,
        execution_bars_by_symbol=bars,
        availability_by_key={
            (s, d.date): d.close_at + timedelta(seconds=30) for s in symbols for d in sessions
        },
    )
    data = yaml.safe_load(Path("experiments/configs/baseline.yaml").read_text())
    data.update(
        initial_cash=initial_cash,
        date_start=str(sessions[0].date),
        date_end=str(sessions[-1].date),
        approved_symbols=sorted(symbols),
        sectors={s: "test" for s in symbols},
    )
    data["risk"].update(
        max_position_size_pct=1,
        max_gross_exposure_pct=1,
        max_deployable_capital_pct=1,
        max_sector_exposure_pct=1,
        max_risk_per_trade_pct=1,
        min_cash_buffer_pct=0,
    )
    return snapshot, ResearchConfig.model_validate(data)


def order(snapshot, *, index=0, symbol="QQQ", quantity=10, action="buy", stop=75, id="entry"):
    sessions = snapshot.sessions
    return ResearchDecision(
        decision_id=id,
        symbol=symbol,
        action=action,
        decision_session=sessions[index].date,
        decision_at=sessions[index].decision_at,
        eligible_session=sessions[index + 1].date if index + 1 < len(sessions) else None,
        accepted=True,
        quantity=quantity,
        reference_price=100,
        stop_price=stop,
        breakout_level=70,
        reason_codes=("explicit_numerical_fixture",),
    )


def simulate(snapshot, config, *orders):
    from packages.backtesting.execution import run_causal_backtest

    return run_causal_backtest(snapshot, ResearchSignalSet(decisions=orders), config)


def test_next_open_fees_terminal_position_and_conservation() -> None:
    snapshot, config = case()
    result = simulate(snapshot, config, order(snapshot))
    entry = next(e for e in result.order_events if e.status == "filled")
    assert entry.session == snapshot.sessions[1].date
    assert entry.fill_price == pytest.approx(100.1, abs=1e-8)
    assert entry.fee == pytest.approx(0.1001, abs=1e-8)
    assert result.equity_curve[1].cash == pytest.approx(8998.8999, abs=1e-8)
    assert result.equity_curve[1].equity == pytest.approx(10018.8999, abs=1e-8)
    assert result.equity_curve[-1].equity == pytest.approx(10098.8999, abs=1e-8)
    assert not result.trades
    position = result.open_positions[0]
    assert position.quantity == 10
    assert position.cost_basis == pytest.approx(1001.1001, abs=1e-8)
    assert position.unrealized_pnl == pytest.approx(98.8999, abs=1e-8)
    assert result.equity_curve[-1].equity - 10000 == pytest.approx(position.unrealized_pnl)


def test_neutral_shadow_blocks_replacement_entries_at_execution() -> None:
    from packages.backtesting.execution import run_causal_backtest

    snapshot, config = case(symbols=("AAA", "BBB"))
    config = config.model_copy(
        update={"risk": config.risk.model_copy(update={"max_open_positions": 1})}
    )
    original = order(snapshot, symbol="AAA", id="original")
    replacement = order(snapshot, symbol="BBB", index=1, id="replacement")
    neutral = simulate(snapshot, config, original, replacement)
    assert next(e for e in neutral.order_events if e.order_id == "replacement").reason == (
        "max_open_positions_exceeded"
    )
    vetoed = original.model_copy(update={"accepted": False, "quantity": 0})
    negative = run_causal_backtest(
        snapshot,
        ResearchSignalSet(decisions=(vetoed, replacement)),
        config,
        neutral_entry_fills=neutral.order_events,
    )
    assert not negative.open_positions
    assert not [e for e in negative.order_events if e.status == "filled"]
    assert next(e for e in negative.order_events if e.order_id == "replacement").reason == (
        "neutral_shadow_entry_ineligible"
    )
    assert all(
        n.gross_exposure <= c.gross_exposure
        for n, c in zip(negative.equity_curve, neutral.equity_curve, strict=True)
    )


def test_neutral_shadow_bounds_entry_quantity_and_ignores_future_fills() -> None:
    from packages.backtesting.execution import run_causal_backtest

    snapshot, config = case()
    original = order(snapshot, quantity=10)
    neutral = simulate(snapshot, config, original)
    reduced = run_causal_backtest(
        snapshot,
        ResearchSignalSet(decisions=(original.model_copy(update={"quantity": 5}),)),
        config,
        neutral_entry_fills=neutral.order_events,
    )
    assert reduced.open_positions[0].quantity == 5
    for negative, control in zip(reduced.equity_curve, neutral.equity_curve, strict=True):
        assert negative.gross_exposure == control.gross_exposure / 2
    excessive = run_causal_backtest(
        snapshot,
        ResearchSignalSet(decisions=(original.model_copy(update={"quantity": 11}),)),
        config,
        neutral_entry_fills=neutral.order_events,
    )
    assert excessive.order_events[0].reason == "neutral_shadow_quantity_exceeded"
    future_only = tuple(
        e.model_copy(update={"session": snapshot.sessions[-1].date}) for e in neutral.order_events
    )
    blocked = run_causal_backtest(
        snapshot,
        ResearchSignalSet(decisions=(original,)),
        config,
        neutral_entry_fills=future_only,
    )
    assert not blocked.open_positions
    assert blocked.order_events[0].session == snapshot.sessions[1].date
    assert blocked.order_events[0].reason == "neutral_shadow_entry_ineligible"


def test_routine_exit_has_next_open_costs_and_net_pnl() -> None:
    snapshot, config = case()
    result = simulate(
        snapshot, config, order(snapshot), order(snapshot, index=1, action="sell", id="exit")
    )
    assert len(result.trades) == 1
    assert result.trades[0].exit_date == snapshot.sessions[2].date
    assert result.trades[0].exit_price == pytest.approx(109.89, abs=1e-8)
    assert result.trades[0].exit_fee == pytest.approx(0.10989, abs=1e-8)
    assert result.trades[0].pnl == pytest.approx(97.69001, abs=1e-8)
    assert result.equity_curve[-1].equity == pytest.approx(10097.69001, abs=1e-8)
    assert not result.open_positions


@pytest.mark.parametrize(
    ("third", "fill", "pnl", "equity"),
    [
        ((100, 101, 94, 96), 94.81, -53.09491, 9946.90509),
        ((90, 92, 88, 91), 89.82, -102.98992, 9897.01008),
    ],
)
def test_stop_and_overnight_gap_use_attainable_base(third, fill, pnl, equity) -> None:
    snapshot, config = case([(100, 101, 99, 100), (100, 103, 99, 102), third, (100, 101, 99, 100)])
    result = simulate(snapshot, config, order(snapshot, stop=95))
    assert result.trades[0].exit_price == pytest.approx(fill, abs=1e-8)
    assert result.trades[0].pnl == pytest.approx(pnl, abs=1e-8)
    assert result.equity_curve[-1].equity == pytest.approx(equity, abs=1e-8)


def test_missing_next_bar_is_unfilled_without_silent_deferral() -> None:
    snapshot, config = case()
    bars = {
        "QQQ": snapshot.execution_bars_by_symbol["QQQ"][:1]
        + snapshot.execution_bars_by_symbol["QQQ"][2:]
    }
    result = simulate(replace(snapshot, execution_bars_by_symbol=bars), config, order(snapshot))
    assert not result.open_positions and not result.trades
    assert result.order_events[0].reason == "missing_execution_bar"
    assert result.order_events[0].status == "unfilled"
    assert result.equity_curve[-1].equity == 10000


def test_missing_mark_fails_instead_of_fabricating_equity() -> None:
    snapshot, config = case()
    bars = {
        "QQQ": snapshot.execution_bars_by_symbol["QQQ"][:2]
        + snapshot.execution_bars_by_symbol["QQQ"][3:]
    }
    with pytest.raises(ValueError, match="missing_position_bar"):
        simulate(replace(snapshot, execution_bars_by_symbol=bars), config, order(snapshot))


def test_simultaneous_symbols_and_duplicates_have_stable_cash_priority() -> None:
    snapshot, config = case([(100, 101, 99, 100)] * 4, initial_cash=1000, symbols=("QQQ", "SPY"))
    a = order(snapshot, quantity=5)
    b = order(snapshot, symbol="SPY", quantity=5, id="entry-b")
    duplicate = order(snapshot, quantity=5, id="entry-duplicate")
    first = simulate(snapshot, config, b, duplicate, a)
    second = simulate(snapshot, config, a, b, duplicate)
    assert first == second
    assert len(first.open_positions) == 1 and first.open_positions[0].symbol == "QQQ"
    assert first.equity_curve[-1].cash == pytest.approx(499.44995, abs=1e-8)
    assert first.equity_curve[-1].equity == pytest.approx(999.44995, abs=1e-8)
    assert {e.reason for e in first.order_events if e.status == "rejected"} == {
        "duplicate_order",
        "insufficient_cash",
    }


def test_duplicate_order_id_is_rejected_even_across_sessions() -> None:
    snapshot, config = case()
    result = simulate(snapshot, config, order(snapshot), order(snapshot))
    assert sum(e.status == "filled" for e in result.order_events) == 1
    assert any(e.reason == "duplicate_order" for e in result.order_events)


def test_no_next_session_and_zero_trade_cases() -> None:
    snapshot, config = case()
    result = simulate(snapshot, config, order(snapshot, index=3))
    assert result.order_events[0].reason == "no_next_session"
    assert result.metrics.trade_count == 0
    assert all(e.equity == e.cash == 10000 and e.gross_exposure == 0 for e in result.equity_curve)
    assert result.metrics.total_return == 0
    assert result.metrics.win_rate is result.metrics.sharpe is None


def test_gap_entry_revalidates_stop_and_risk() -> None:
    snapshot, config = case(
        [(100, 101, 99, 100), (70, 71, 69, 70), (80, 81, 79, 80), (80, 81, 79, 80)]
    )
    result = simulate(snapshot, config, order(snapshot, stop=95))
    assert any("invalid_stop_distance" in e.reason for e in result.order_events)
    assert not result.open_positions


def test_fill_timestamp_and_exact_calendar_session_are_validated() -> None:
    snapshot, config = case()
    too_late = order(snapshot).model_copy(update={"decision_at": snapshot.sessions[1].open_at})
    with pytest.raises(ValueError, match="invalid_decision_timing"):
        simulate(snapshot, config, too_late)
    delayed = order(snapshot).model_copy(update={"eligible_session": snapshot.sessions[2].date})
    with pytest.raises(ValueError, match="invalid_eligible_session"):
        simulate(snapshot, config, delayed)


def test_intraday_stop_proceeds_cannot_finance_opening_entries() -> None:
    snapshot, config = case(
        [(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 94, 96), (100, 101, 99, 100)],
        initial_cash=1000,
        symbols=("QQQ", "SPY"),
    )
    first = order(snapshot, quantity=9, stop=95)
    later = order(snapshot, symbol="SPY", index=1, quantity=5, id="later")
    result = simulate(snapshot, config, first, later)
    assert any(e.symbol == "SPY" and e.reason == "insufficient_cash" for e in result.order_events)
    assert len(result.trades) == 1


def test_partial_exit_quantity_is_explicitly_rejected() -> None:
    snapshot, config = case()
    result = simulate(
        snapshot,
        config,
        order(snapshot),
        order(snapshot, index=1, quantity=5, action="sell", id="partial"),
    )
    assert any(e.reason == "partial_exit_unsupported" for e in result.order_events)
    assert result.open_positions[0].quantity == 10


def test_opening_risk_capacity_rejects_second_symbol() -> None:
    snapshot, config = case([(100, 101, 99, 100)] * 4, symbols=("QQQ", "SPY"))
    risk = config.risk.model_copy(update={"max_open_positions": 1})
    result = simulate(
        snapshot,
        config.model_copy(update={"risk": risk}),
        order(snapshot),
        order(snapshot, symbol="SPY", id="second"),
    )
    assert len(result.open_positions) == 1
    assert any("max_open_positions_exceeded" in e.reason for e in result.order_events)


def test_trailing_stop_computed_at_close_is_effective_next_session() -> None:
    snapshot, config = case([(100, 101, 99, 100)] * 4)
    # Use enough pre-entry history for ATR; the last low precedes the higher closing trail.
    sessions = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json")).sessions[
        :16
    ]
    bars = tuple(
        AdjustedDailyBar(
            symbol="QQQ",
            date=s.date,
            open=100,
            high=101,
            low=99,
            close=100,
            volume=1000000,
            adjusted=False,
        )
        for s in sessions[:-1]
    )
    last = AdjustedDailyBar(
        symbol="QQQ",
        date=sessions[-1].date,
        open=100,
        high=111,
        low=96,
        close=110,
        volume=1000000,
        adjusted=False,
    )
    snapshot = replace(
        snapshot,
        sessions=sessions,
        feature_bars_by_symbol={"QQQ": bars + (last,)},
        execution_bars_by_symbol={"QQQ": bars + (last,)},
        availability_by_key={("QQQ", s.date): s.close_at + timedelta(seconds=30) for s in sessions},
    )
    config = config.model_copy(update={"date_end": sessions[-1].date})
    result = simulate(snapshot, config, order(snapshot, index=13, stop=95))
    assert not result.trades
    assert result.open_positions[0].stop_price > 96
    assert result.open_positions[0].quantity == 10


def test_open_gap_price_cannot_seed_a_close_derived_trailing_stop() -> None:
    snapshot, config = case()
    sessions = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json")).sessions[
        :17
    ]
    bars = []
    for i, session in enumerate(sessions):
        prices = (110, 111, 99, 100) if i == 15 else (100, 101, 99, 100)
        bars.append(
            AdjustedDailyBar(
                symbol="QQQ",
                date=session.date,
                open=prices[0],
                high=prices[1],
                low=prices[2],
                close=prices[3],
                volume=1000000,
                adjusted=False,
            )
        )
    snapshot = replace(
        snapshot,
        sessions=sessions,
        feature_bars_by_symbol={"QQQ": tuple(bars)},
        execution_bars_by_symbol={"QQQ": tuple(bars)},
        availability_by_key={("QQQ", s.date): s.close_at + timedelta(seconds=30) for s in sessions},
    )
    config = config.model_copy(update={"date_end": sessions[-1].date})
    result = simulate(snapshot, config, order(snapshot, index=14, stop=95))
    assert not result.trades
    assert result.open_positions[0].stop_price == 95


def test_stop_fill_event_records_the_active_trailing_level() -> None:
    snapshot, config = case()
    sessions = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json")).sessions[
        :17
    ]
    bars = []
    for i, session in enumerate(sessions):
        prices = (100, 111, 96, 110) if i == 15 else (100, 101, 99, 100)
        bars.append(
            AdjustedDailyBar(
                symbol="QQQ",
                date=session.date,
                open=prices[0],
                high=prices[1],
                low=prices[2],
                close=prices[3],
                volume=1000000,
                adjusted=False,
            )
        )
    snapshot = replace(
        snapshot,
        sessions=sessions,
        feature_bars_by_symbol={"QQQ": tuple(bars)},
        execution_bars_by_symbol={"QQQ": tuple(bars)},
        availability_by_key={("QQQ", s.date): s.close_at + timedelta(seconds=30) for s in sessions},
    )
    config = config.model_copy(update={"date_end": sessions[-1].date})
    result = simulate(snapshot, config, order(snapshot, index=14, stop=95))
    exit_event = next(e for e in result.order_events if e.reason == "gap_stop")
    # ATR after the wide 15th-index bar: (2*13+15)/14 = 41/14.
    # Close-derived trailing level: 110 - 2.5*(41/14) = 102.67857142857143.
    assert exit_event.stop_price == pytest.approx(102.67857142857143, abs=1e-8)
    assert exit_event.parent_entry_id == "entry"
    assert exit_event.decision_session == sessions[15].date
    assert exit_event.decision_at == sessions[15].decision_at
    assert exit_event.eligible_session == sessions[16].date

"""Literal independent arithmetic for the audited research reporting contract."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.backtesting.metrics import calculate_backtest_metrics, total_return
from packages.backtesting.models import (
    BacktestResult,
    BacktestTrade,
    EquityPoint,
    OpenResearchPosition,
    ResearchOrderEvent,
)
from packages.data.models import AdjustedDailyBar
from packages.data.snapshots import DatasetSnapshot, load_dataset_snapshot
from packages.research.config import load_research_config
from packages.research.models import ResearchConfig


def _result(
    equities: tuple[float, ...],
    *,
    exposures: tuple[float, ...] | None = None,
    trades: tuple[BacktestTrade, ...] = (),
    events: tuple[ResearchOrderEvent, ...] = (),
    positions: tuple[OpenResearchPosition, ...] = (),
) -> BacktestResult:
    gross = exposures or (0.0,) * len(equities)
    curve = tuple(
        EquityPoint(
            date=date(2025, 1, 2) + timedelta(days=i),
            equity=equity,
            cash=equity - exposure,
            gross_exposure=exposure,
        )
        for i, (equity, exposure) in enumerate(zip(equities, gross, strict=True))
    )
    return BacktestResult(
        name="literal arithmetic",
        trades=trades,
        equity_curve=curve,
        metrics=calculate_backtest_metrics(equity_curve=curve, trades=trades),
        validation_note="Synthetic arithmetic; not proof of profitability.",
        order_events=events,
        open_positions=positions,
    )


def _trade(pnl: float, *, first: int = 0, last: int = 2) -> BacktestTrade:
    return BacktestTrade(
        symbol="SPY",
        entry_date=date(2025, 1, 2) + timedelta(days=first),
        exit_date=date(2025, 1, 2) + timedelta(days=last),
        quantity=10,
        entry_price=10.1,
        exit_price=10.89,
        entry_fee=1.01,
        exit_fee=1.089,
        pnl=pnl,
        return_pct=pnl / 101,
    )


def _event(action: str, *, status: str = "filled") -> ResearchOrderEvent:
    return ResearchOrderEvent.model_validate(
        dict(
            order_id=action,
            symbol="SPY",
            action=action,
            decision_session=date(2025, 1, 1),
            decision_at=datetime(2025, 1, 1, 21, tzinfo=UTC),
            eligible_session=date(2025, 1, 2),
            session=date(2025, 1, 2 if action == "buy" else 4),
            quantity=10,
            status=status,
            reason="independent_fixture",
            base_price=10 if action == "buy" else 11,
            fill_price=10.1 if action == "buy" else 10.89,
            fee=1.01 if action == "buy" else 1.089,
            slippage_cost=1 if action == "buy" else 1.1,
        )
    )


def _benchmark_case() -> tuple[DatasetSnapshot, BacktestResult, ResearchConfig]:
    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    sessions = snapshot.sessions[:3]
    # First SPY open 100, closes 110, 99, 118.8: total B&H return 18.8%.
    bars = {
        symbol: tuple(
            AdjustedDailyBar(
                symbol=symbol,
                date=session.date,
                open=opening,
                high=max(opening, closing) + 1,
                low=min(opening, closing) - 1,
                close=closing,
                volume=1_000_000,
                adjusted=False,
            )
            for session, opening, closing in zip(sessions, opens, closes, strict=True)
        )
        for symbol, opens, closes in (
            ("SPY", (100, 110, 99), (110, 99, 118.8)),
            ("QQQ", (50, 50, 50), (50, 50, 50)),
        )
    }
    snapshot = replace(
        snapshot,
        sessions=sessions,
        feature_bars_by_symbol=bars,
        execution_bars_by_symbol=bars,
    )
    config = load_research_config(Path("experiments/configs/baseline.yaml")).model_copy(
        update=dict(
            initial_cash=100.0,
            date_start=sessions[0].date,
            date_end=sessions[-1].date,
            approved_symbols=("QQQ", "SPY"),
        )
    )
    result = _result((100, 100, 100), exposures=(100, 0, 100))
    result = result.model_copy(
        update={
            "equity_curve": tuple(
                point.model_copy(update={"date": session.date})
                for point, session in zip(result.equity_curve, sessions, strict=True)
            )
        }
    )
    return snapshot, result, config


def test_initial_capital_return_and_drawdown_include_first_session_loss() -> None:
    from packages.research.metrics import evaluate_research_metrics

    result = _result((90, 120, 96))
    report = evaluate_research_metrics(result, 100)
    assert report.values["total_return"] == pytest.approx(-0.04)
    assert report.values["max_drawdown"] == pytest.approx(-0.20)
    assert report.values["max_drawdown_magnitude"] == pytest.approx(0.20)
    first = evaluate_research_metrics(_result((90,)), 100)
    assert first.values["max_drawdown"] == pytest.approx(-0.10)
    assert first.values["total_return"] == pytest.approx(-0.10)
    # The historical explicit-signal metric keeps its first-mark convention.
    assert total_return(result.equity_curve) == pytest.approx(96 / 90 - 1)


def test_annualized_return_sharpe_rf_ddof_and_rms_sortino_literal_reference() -> None:
    from packages.research.metrics import MetricSettings, evaluate_research_metrics

    settings = MetricSettings(
        sessions_per_year=3,
        minimum_annualization_sessions=3,
        annual_risk_free_rate=0.331,
        annual_downside_target=0,
        sharpe_ddof=1,
    )
    report = evaluate_research_metrics(_result((110, 99, 118.8)), 100, settings=settings)
    # Returns .1, -.1, .2; daily rf .1; sample variance .0233333333333.
    assert report.values["annualized_return"] == pytest.approx(0.188)
    assert report.values["sharpe"] == pytest.approx(-0.3779644730092272)
    # RMS downside sqrt((0 + .01 + 0)/3), mean excess 1/15, annualizer sqrt(3).
    assert report.values["sortino"] == pytest.approx(2.0)
    population = evaluate_research_metrics(
        _result((110, 99, 118.8)),
        100,
        settings=settings.model_copy(update={"sharpe_ddof": 0}),
    )
    assert population.values["sharpe"] == pytest.approx(-0.4629100498862757)


def test_sortino_target_is_compounded_per_session_and_rms_uses_all_sessions() -> None:
    from packages.research.metrics import MetricSettings, evaluate_research_metrics

    report = evaluate_research_metrics(
        _result((110, 99, 118.8)),
        100,
        settings=MetricSettings(sessions_per_year=3, annual_downside_target=0.331),
    )
    assert report.values["sortino"] == pytest.approx(-0.5)


def test_annualization_minimum_sample_and_bankruptcy_contract() -> None:
    from packages.research.metrics import MetricSettings, evaluate_research_metrics

    short = evaluate_research_metrics(_result((110, 121)), 100)
    assert short.values["annualized_return"] is None
    assert short.undefined["annualized_return"] == "insufficient_sessions_for_annualization"
    bankrupt = evaluate_research_metrics(
        _result((50, 0)),
        100,
        settings=MetricSettings(minimum_annualization_sessions=2),
    )
    assert bankrupt.values["annualized_return"] == -1
    assert bankrupt.values["max_drawdown"] == -1
    after_zero = evaluate_research_metrics(_result((0, 0)), 100)
    assert after_zero.undefined["sharpe"] == "nonpositive_previous_equity"
    assert after_zero.undefined["average_exposure"] == "nonpositive_equity"


def test_exposure_is_fraction_and_gross_exposure_is_currency() -> None:
    from packages.research.metrics import evaluate_research_metrics

    report = evaluate_research_metrics(_result((110, 99, 118.8), exposures=(55, 0, 59.4)), 100)
    assert report.values["average_exposure"] == pytest.approx(1 / 3)
    assert report.values["average_gross_exposure"] == pytest.approx(38.13333333333333)
    assert report.units["average_exposure"] == "fraction"
    assert report.units["average_gross_exposure"] == "currency"


def test_filled_notional_turnover_and_net_gross_cost_bridge() -> None:
    from packages.research.metrics import evaluate_research_metrics

    result = _result(
        (998.99, 998.99, 1005.801),
        trades=(_trade(5.801),),
        events=(
            _event("buy"),
            _event("sell"),
            _event("buy", status="rejected"),
            _event("buy", status="unfilled"),
        ),
    )
    report = evaluate_research_metrics(result, 1000)
    assert report.values["turnover"] == pytest.approx(0.2099)
    assert report.values["fees"] == pytest.approx(2.099)
    assert report.values["slippage"] == pytest.approx(2.1)
    assert report.values["transaction_cost"] == pytest.approx(4.199)
    assert report.values["net_pnl"] == pytest.approx(5.801)
    assert report.values["gross_pnl"] == pytest.approx(10)
    assert report.values["gross_return"] == pytest.approx(0.01)
    assert report.values["net_return"] == pytest.approx(0.005801)
    assert report.values["realized_pnl"] == pytest.approx(5.801)
    assert report.values["unrealized_pnl"] == pytest.approx(0)
    assert report.values["rejected_count"] == 1
    assert report.values["unfilled_count"] == 1
    assert report.values["average_holding_sessions"] == 2
    assert report.values["average_holding_calendar_days"] == 2


def test_closed_and_open_holding_periods_distinguish_session_and_calendar_days() -> None:
    from packages.research.metrics import evaluate_research_metrics

    snapshot, result, _ = _benchmark_case()  # Thu/Fri/Mon.
    trade = _trade(5).model_copy(
        update={"entry_date": snapshot.sessions[1].date, "exit_date": snapshot.sessions[2].date}
    )
    position = OpenResearchPosition(
        symbol="QQQ",
        entry_date=snapshot.sessions[0].date,
        quantity=5,
        entry_price=10.1,
        entry_fee=0.505,
        stop_price=9,
        mark_price=11,
        cost_basis=51.005,
        unrealized_pnl=3.995,
    )
    report = evaluate_research_metrics(
        result.model_copy(update={"trades": (trade,), "open_positions": (position,)}), 100
    )
    assert report.values["average_holding_sessions"] == 1
    assert report.values["average_holding_calendar_days"] == 3
    assert report.values["average_open_holding_sessions"] == 2
    assert report.values["average_open_holding_calendar_days"] == 4
    assert report.values["open_position_count"] == 1


def test_zero_trades_no_losses_and_flat_returns_have_explicit_undefined_reasons() -> None:
    from packages.research.metrics import evaluate_research_metrics

    flat = evaluate_research_metrics(_result((100, 100, 100)), 100)
    assert flat.values["trade_count"] == 0
    assert flat.values["turnover"] == 0
    assert flat.values["fees"] == 0
    assert flat.values["gross_pnl"] == 0
    assert flat.undefined["profit_factor"] == "no_closed_trades"
    assert flat.undefined["win_rate"] == "no_closed_trades"
    assert flat.undefined["average_holding_sessions"] == "no_closed_trades"
    assert flat.undefined["average_win"] == "no_winning_trades"
    assert flat.undefined["average_loss"] == "no_losing_trades"
    assert flat.undefined["sharpe"] == "zero_return_variance"
    assert flat.undefined["sortino"] == "zero_downside_deviation"
    gains = evaluate_research_metrics(_result((100, 105, 110), trades=(_trade(10),)), 100)
    assert gains.values["win_rate"] == 1
    assert gains.undefined["profit_factor"] == "no_losing_trades"
    mixed = evaluate_research_metrics(
        _result((100, 105, 110), trades=(_trade(12), _trade(-3), _trade(0))), 100
    )
    assert mixed.values["profit_factor"] == 4
    assert mixed.values["win_rate"] == pytest.approx(1 / 3)
    assert mixed.values["average_win"] == 12
    assert mixed.values["average_loss"] == -3


def test_missing_fill_provenance_never_fabricates_cost_or_turnover() -> None:
    from packages.research.metrics import evaluate_research_metrics

    report = evaluate_research_metrics(_result((100, 110), exposures=(50, 55)), 100)
    for key in ("turnover", "fees", "slippage", "transaction_cost", "gross_pnl", "gross_return"):
        assert report.values[key] is None
        assert report.undefined[key] == "missing_filled_order_events"


def test_terminal_open_entry_costs_are_included_in_net_gross_bridge() -> None:
    from packages.research.metrics import evaluate_research_metrics

    position = OpenResearchPosition(
        symbol="SPY",
        entry_date=date(2025, 1, 2),
        quantity=10,
        entry_price=10.1,
        entry_fee=1.01,
        stop_price=9,
        mark_price=11,
        cost_basis=102.01,
        unrealized_pnl=7.99,
    )
    report = evaluate_research_metrics(
        _result(
            (997.99, 1007.99, 1007.99),
            exposures=(100, 110, 110),
            events=(_event("buy"),),
            positions=(position,),
        ),
        1000,
    )
    assert report.values["trade_count"] == 0
    assert report.values["realized_pnl"] == 0
    assert report.values["unrealized_pnl"] == pytest.approx(7.99)
    assert report.values["net_pnl"] == pytest.approx(7.99)
    assert report.values["fees"] == pytest.approx(1.01)
    assert report.values["slippage"] == pytest.approx(1)
    assert report.values["turnover"] == pytest.approx(0.101)
    assert report.values["gross_pnl"] == pytest.approx(10)


def test_benchmark_metrics_do_not_invent_a_position_ledger() -> None:
    from packages.research.benchmarks import evaluate_benchmarks

    snapshot, result, config = _benchmark_case()
    report = evaluate_benchmarks(snapshot, result, config).metrics["spy_buy_and_hold"]
    for key in (
        "open_position_count",
        "realized_pnl",
        "unrealized_pnl",
        "average_open_holding_sessions",
        "average_open_holding_calendar_days",
    ):
        assert report.values[key] is None
        assert report.undefined[key] == "analytical_benchmark_no_position_ledger"
    assert report.values["turnover"] is None
    assert report.undefined["turnover"] == "analytical_benchmark_no_execution_ledger"
    assert set(report.undefined) == {key for key, value in report.values.items() if value is None}


def test_only_losses_breakeven_and_partial_holding_coverage_are_explicit() -> None:
    from packages.research.metrics import evaluate_research_metrics

    losses = evaluate_research_metrics(_result((100, 100, 90), trades=(_trade(-10),)), 100)
    assert losses.values["profit_factor"] == 0
    assert losses.values["win_rate"] == 0
    breakeven = evaluate_research_metrics(_result((100, 100, 100), trades=(_trade(0),)), 100)
    assert breakeven.undefined["profit_factor"] == "no_losing_trades"
    partial = evaluate_research_metrics(_result((100, 110), trades=(_trade(10),)), 100)
    assert partial.undefined["average_holding_sessions"] == "holding_dates_outside_equity_curve"
    assert partial.values["average_holding_calendar_days"] == 2
    with pytest.raises(ValueError, match="negative_holding_period"):
        evaluate_research_metrics(_result((100, 100), trades=(_trade(0, first=1, last=0),)), 100)


def test_annualization_overflow_is_null_and_zero_equity_exposure_is_unavailable() -> None:
    from packages.research.benchmarks import evaluate_benchmarks
    from packages.research.metrics import MetricSettings, evaluate_research_metrics

    report = evaluate_research_metrics(
        _result((100, 1_000_000)),
        1,
        settings=MetricSettings(minimum_annualization_sessions=2),
    )
    assert report.undefined["annualized_return"] == "numerical_overflow"
    snapshot, result, config = _benchmark_case()
    point = result.equity_curve[0].model_copy(update={"equity": 0, "cash": 0, "gross_exposure": 0})
    comparison = evaluate_benchmarks(
        snapshot,
        result.model_copy(update={"equity_curve": (point, *result.equity_curve[1:])}),
        config,
    )
    assert (
        comparison.unavailable["spy_exposure_adjusted"]
        == "nonpositive_strategy_equity_for_exposure"
    )


def test_empty_short_sample_reasons_and_serialized_report_metadata() -> None:
    from packages.research.metrics import evaluate_research_metrics

    report = evaluate_research_metrics(_result(()), 100)
    assert report.undefined["total_return"] == "empty_equity_curve"
    assert report.undefined["annualized_return"] == "empty_equity_curve"
    assert report.undefined["sharpe"] == "insufficient_returns"
    assert report.undefined["sortino"] == "insufficient_returns"
    assert report.undefined["average_exposure"] == "empty_equity_curve"
    assert set(report.undefined) == {k for k, v in report.values.items() if v is None}
    assert set(report.values) == set(report.definitions) == set(report.units)
    dumped = report.model_dump(mode="json")
    assert dumped["assumptions"]["initial_capital"] == 100
    assert dumped["assumptions"]["settings"]["sharpe_ddof"] == 1
    short = evaluate_research_metrics(_result((110,)), 100)
    assert short.undefined["sharpe"] == "insufficient_returns"
    assert short.undefined["sortino"] == "insufficient_returns"


@pytest.mark.parametrize("initial", [0, -1, float("nan"), float("inf")])
def test_invalid_initial_capital_rejected(initial: float) -> None:
    from packages.research.metrics import evaluate_research_metrics

    with pytest.raises(ValueError, match="invalid_initial_capital"):
        evaluate_research_metrics(_result((100,)), initial)


@pytest.mark.parametrize(
    "settings",
    [
        {"sessions_per_year": 0},
        {"minimum_annualization_sessions": 1},
        {"annual_risk_free_rate": -1},
        {"annual_downside_target": float("nan")},
        {"sharpe_ddof": 2},
    ],
)
def test_metric_settings_reject_invalid_values(settings: dict[str, float]) -> None:
    from packages.research.metrics import MetricSettings

    with pytest.raises(ValidationError):
        MetricSettings.model_validate(settings)
    frozen = MetricSettings()
    with pytest.raises(ValidationError, match="frozen"):
        frozen.sessions_per_year = 100


def test_bad_curves_and_incomplete_fills_fail_explicitly() -> None:
    from packages.research.metrics import evaluate_research_metrics

    result = _result((100, 110))
    with pytest.raises(ValueError, match="equity_dates_must_be_sorted_unique"):
        evaluate_research_metrics(
            result.model_copy(update={"equity_curve": result.equity_curve[::-1]}), 100
        )
    with pytest.raises(ValueError, match="nonfinite_equity_point"):
        evaluate_research_metrics(
            result.model_copy(
                update={
                    "equity_curve": (
                        result.equity_curve[0].model_copy(update={"equity": float("nan")}),
                    )
                }
            ),
            100,
        )
    with pytest.raises(ValueError, match="invalid_filled_order_event"):
        evaluate_research_metrics(
            result.model_copy(
                update={"order_events": (_event("buy").model_copy(update={"fill_price": None}),)}
            ),
            100,
        )


def test_benchmarks_use_exact_dates_first_open_and_lagged_exposure() -> None:
    from packages.research.benchmarks import evaluate_benchmarks

    snapshot, result, config = _benchmark_case()
    report = evaluate_benchmarks(snapshot, result, config)
    assert set(report.curves) == {
        "strategy",
        "spy_buy_and_hold",
        "spy_exposure_adjusted",
        "equal_weight",
    }
    assert all(
        tuple(p.date for p in c) == tuple(p.date for p in result.equity_curve)
        for c in report.curves.values()
    )
    assert [p.equity for p in report.curves["spy_buy_and_hold"]] == pytest.approx([110, 99, 118.8])
    # First session stays cash; prior strategy exposure is 1 then 0.
    assert [p.equity for p in report.curves["spy_exposure_adjusted"]] == pytest.approx(
        [100, 90, 90]
    )
    assert [p.equity for p in report.curves["equal_weight"]] == pytest.approx([105, 99.5, 109.4])
    assert report.metrics["spy_buy_and_hold"].values["total_return"] == pytest.approx(0.188)
    assert report.metrics["equal_weight"].values["total_return"] == pytest.approx(0.094)
    assert report.metrics["spy_buy_and_hold"].values["fees"] == 0
    assert report.metrics["spy_buy_and_hold"].values["slippage"] == 0
    assert report.metrics["spy_buy_and_hold"].values["gross_return"] == pytest.approx(0.188)
    dumped = report.model_dump(mode="json")
    assert dumped["assumptions"]["cash_annual_return"] == 0
    assert dumped["assumptions"]["initial_order"] == "frozen_before_first_session_open"
    assert any("price_return" in warning for warning in report.warnings)
    assert any("survivorship" in warning for warning in report.warnings)


def test_exposure_benchmark_ignores_current_session_exposure_for_that_return() -> None:
    from packages.research.benchmarks import evaluate_benchmarks

    snapshot, result, config = _benchmark_case()
    before = evaluate_benchmarks(snapshot, result, config)
    last = result.equity_curve[-1].model_copy(update={"gross_exposure": 0, "cash": 100})
    after = evaluate_benchmarks(
        snapshot,
        result.model_copy(update={"equity_curve": (*result.equity_curve[:-1], last)}),
        config,
    )
    assert before.curves["spy_exposure_adjusted"] == after.curves["spy_exposure_adjusted"]


def test_missing_benchmark_prices_omit_whole_comparator_with_reason() -> None:
    from packages.research.benchmarks import evaluate_benchmarks

    snapshot, result, config = _benchmark_case()
    bars = dict(snapshot.execution_bars_by_symbol)
    bars["SPY"] = (bars["SPY"][0], bars["SPY"][2])
    missing = evaluate_benchmarks(replace(snapshot, execution_bars_by_symbol=bars), result, config)
    assert set(missing.curves) == {"strategy"}
    assert "missing_price:SPY:" in missing.unavailable["spy_buy_and_hold"]
    assert "missing_price:SPY:" in missing.unavailable["equal_weight"]
    assert missing.unavailable["spy_exposure_adjusted"] == missing.unavailable["spy_buy_and_hold"]


def test_missing_equal_weight_member_never_reweights_available_survivors() -> None:
    from packages.research.benchmarks import evaluate_benchmarks

    snapshot, result, config = _benchmark_case()
    bars = {"SPY": snapshot.execution_bars_by_symbol["SPY"]}
    report = evaluate_benchmarks(replace(snapshot, execution_bars_by_symbol=bars), result, config)
    assert "spy_buy_and_hold" in report.curves
    assert "equal_weight" not in report.curves
    assert report.unavailable["equal_weight"].startswith("missing_price:QQQ:")


def test_benchmark_alignment_provenance_and_price_basis_are_checked() -> None:
    from packages.research.benchmarks import evaluate_benchmarks

    snapshot, result, config = _benchmark_case()
    with pytest.raises(ValueError, match="benchmark_result_calendar_mismatch"):
        evaluate_benchmarks(
            snapshot, result.model_copy(update={"equity_curve": result.equity_curve[1:]}), config
        )
    with pytest.raises(ValueError, match="benchmark_dataset_hash_mismatch"):
        evaluate_benchmarks(
            snapshot, result, config.model_copy(update={"dataset_manifest_sha256": "0" * 64})
        )
    with pytest.raises(ValueError, match="unsupported_benchmark_price_basis"):
        evaluate_benchmarks(
            replace(
                snapshot,
                manifest=snapshot.manifest.model_copy(update={"dividend_policy": "unknown"}),
            ),
            result,
            config,
        )
    adjusted = {
        symbol: tuple(b.model_copy(update={"adjusted": True}) for b in bars)
        for symbol, bars in snapshot.execution_bars_by_symbol.items()
    }
    with pytest.raises(ValueError, match="unsupported_benchmark_price_basis"):
        evaluate_benchmarks(replace(snapshot, execution_bars_by_symbol=adjusted), result, config)


def test_exposure_comparator_rejects_leverage_instead_of_clipping() -> None:
    from packages.research.benchmarks import evaluate_benchmarks

    snapshot, result, config = _benchmark_case()
    point = result.equity_curve[0].model_copy(update={"gross_exposure": 101})
    report = evaluate_benchmarks(
        snapshot,
        result.model_copy(update={"equity_curve": (point, *result.equity_curve[1:])}),
        config,
    )
    assert report.unavailable["spy_exposure_adjusted"] == "strategy_exposure_outside_unit_interval"
    assert "spy_buy_and_hold" in report.curves


def test_benchmark_settings_are_identical_for_every_curve_and_change_calculations() -> None:
    from packages.research.benchmarks import evaluate_benchmarks
    from packages.research.metrics import MetricSettings

    snapshot, result, config = _benchmark_case()
    settings = MetricSettings(
        sessions_per_year=3,
        minimum_annualization_sessions=3,
        annual_risk_free_rate=0.331,
        annual_downside_target=0.331,
        sharpe_ddof=0,
    )
    comparison = evaluate_benchmarks(snapshot, result, config, settings=settings)
    assert all(
        report.assumptions["settings"] == settings.model_dump(mode="json")
        for report in comparison.metrics.values()
    )
    spy = comparison.metrics["spy_buy_and_hold"]
    # .1, -.1, .2 returns; daily risk-free/target .1; population ddof.
    assert spy.values["annualized_return"] == pytest.approx(0.188)
    assert spy.values["sharpe"] == pytest.approx(-0.4629100498862757)
    assert spy.values["sortino"] == pytest.approx(-0.5)
    assert comparison.metrics["strategy"].values["annualized_return"] == 0
    assert comparison.metrics["spy_exposure_adjusted"].values["annualized_return"] == pytest.approx(
        -0.1
    )
    assert comparison.metrics["equal_weight"].values["annualized_return"] == pytest.approx(0.094)
    default = evaluate_benchmarks(snapshot, result, config)
    assert all(
        report.undefined["annualized_return"] == "insufficient_sessions_for_annualization"
        for report in default.metrics.values()
    )

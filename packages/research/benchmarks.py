"""Local, calendar-aligned price-return comparators with explicit qualifications."""

from __future__ import annotations

import math
from datetime import date

from pydantic import BaseModel, ConfigDict

from packages.backtesting.models import BacktestResult, EquityPoint
from packages.data.models import AdjustedDailyBar
from packages.data.snapshots import DatasetSnapshot
from packages.research.metrics import (
    MetricSettings,
    ResearchMetricReport,
    evaluate_research_metrics,
)
from packages.research.models import ResearchConfig


class BenchmarkComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    curves: dict[str, tuple[EquityPoint, ...]]
    metrics: dict[str, ResearchMetricReport]
    unavailable: dict[str, str]
    warnings: tuple[str, ...]
    assumptions: dict[str, object]


def _aligned_bars(
    snapshot: DatasetSnapshot, symbol: str, dates: tuple[date, ...]
) -> tuple[AdjustedDailyBar, ...]:
    bars = snapshot.execution_bars_by_symbol.get(symbol, ())
    lookup = {b.date: b for b in bars}
    if len(lookup) != len(bars):
        raise ValueError(f"duplicate_benchmark_price:{symbol}")
    for session in dates:
        if session not in lookup:
            raise ValueError(f"missing_price:{symbol}:{session}")
        bar = lookup[session]
        if bar.adjusted:
            raise ValueError("unsupported_benchmark_price_basis")
        if not all(math.isfinite(v) and v > 0 for v in (bar.open, bar.close)):
            raise ValueError(f"invalid_benchmark_price:{symbol}:{session}")
    return tuple(lookup[d] for d in dates)


def _buy_and_hold(
    members: tuple[tuple[AdjustedDailyBar, ...], ...], initial: float
) -> tuple[EquityPoint, ...]:
    # Frozen equal initial allocations, fractional units, no later rebalancing.
    allocation = initial / len(members)
    return tuple(
        EquityPoint(
            date=members[0][i].date,
            equity=value,
            cash=0,
            gross_exposure=value,
        )
        for i in range(len(members[0]))
        for value in (sum(allocation * bars[i].close / bars[0].open for bars in members),)
    )


def _exposure_adjusted(
    spy: tuple[AdjustedDailyBar, ...], result: BacktestResult, initial: float
) -> tuple[EquityPoint, ...]:
    curve = [EquityPoint(date=spy[0].date, equity=initial, cash=initial, gross_exposure=0)]
    for index in range(1, len(spy)):
        prior = result.equity_curve[index - 1]
        if prior.equity <= 0:
            raise ValueError("nonpositive_strategy_equity_for_exposure")
        weight = prior.gross_exposure / prior.equity
        if not 0 <= weight <= 1:
            raise ValueError("strategy_exposure_outside_unit_interval")
        previous_equity = curve[-1].equity
        cash = previous_equity * (1 - weight)
        exposure = previous_equity * weight * spy[index].close / spy[index - 1].close
        curve.append(
            EquityPoint(
                date=spy[index].date, equity=cash + exposure, cash=cash, gross_exposure=exposure
            )
        )
    return tuple(curve)


def _benchmark_metrics(
    result: BacktestResult,
    curve: tuple[EquityPoint, ...],
    initial: float,
    *,
    settings: MetricSettings | None = None,
) -> ResearchMetricReport:
    report = evaluate_research_metrics(
        result.model_copy(
            update={"equity_curve": curve, "trades": (), "open_positions": (), "order_events": ()}
        ),
        initial,
        settings=settings,
    )
    # These are analytical fractional-unit comparators, not simulated order ledgers.
    values, undefined, definitions = (
        dict(report.values),
        dict(report.undefined),
        dict(report.definitions),
    )
    for name in ("fees", "slippage", "transaction_cost"):
        values[name] = 0
        undefined.pop(name, None)
        definitions[name] = "Zero by the declared frictionless analytical benchmark convention."
    for name, net in (("gross_pnl", "net_pnl"), ("gross_return", "total_return")):
        values[name] = values[net]
        undefined.pop(name, None)
        definitions[name] = "Equals net metric under the declared zero-cost benchmark convention."
    values["turnover"] = None
    undefined["turnover"] = "analytical_benchmark_no_execution_ledger"
    definitions["turnover"] = (
        "Unavailable: analytical comparator has no simulated execution ledger."
    )
    for name in (
        "open_position_count",
        "realized_pnl",
        "unrealized_pnl",
        "average_open_holding_sessions",
        "average_open_holding_calendar_days",
    ):
        values[name] = None
        undefined[name] = "analytical_benchmark_no_position_ledger"
    return report.model_copy(
        update={
            "values": values,
            "undefined": undefined,
            "definitions": definitions,
            "assumptions": {
                **report.assumptions,
                "benchmark_costs": (
                    "Zero fees/slippage; analytical comparator without an execution ledger."
                ),
            },
        }
    )


def evaluate_benchmarks(
    snapshot: DatasetSnapshot,
    result: BacktestResult,
    config: ResearchConfig,
    *,
    settings: MetricSettings | None = None,
) -> BenchmarkComparison:
    """Compare precisely the strategy's sessions, without filling missing prices.

    Raw action/dividend-free coverage permits qualified price returns only. B&H
    orders are frozen before the first aligned open, include first open-to-close
    return, and remain open at the terminal close. The exposure comparator is an
    analytical cash/SPY mixture: first session in cash, then prior strategy EOD
    gross exposure weights the next close-to-close return. It is not an executable
    strategy and includes neither cash interest nor transaction costs.
    """
    if snapshot.manifest_sha256 != config.dataset_manifest_sha256:
        raise ValueError("benchmark_dataset_hash_mismatch")
    manifest = snapshot.manifest
    if (
        manifest.execution_price_basis != "raw"
        or manifest.corporate_action_policy != "none_in_coverage"
        or manifest.dividend_policy != "none_in_coverage"
    ):
        raise ValueError("unsupported_benchmark_price_basis")
    dates = tuple(
        s.date for s in snapshot.sessions if config.date_start <= s.date <= config.date_end
    )
    if not dates or tuple(p.date for p in result.equity_curve) != dates:
        raise ValueError("benchmark_result_calendar_mismatch")
    curves = {"strategy": result.equity_curve}
    reports = {
        "strategy": evaluate_research_metrics(result, config.initial_cash, settings=settings)
    }
    unavailable: dict[str, str] = {}

    def missing(name: str, exc: ValueError) -> None:
        if not str(exc).startswith("missing_price:"):
            raise exc
        unavailable[name] = str(exc)

    try:
        spy = _aligned_bars(snapshot, "SPY", dates)
    except ValueError as exc:
        missing("spy_buy_and_hold", exc)
        unavailable["spy_exposure_adjusted"] = str(exc)
    else:
        curves["spy_buy_and_hold"] = _buy_and_hold((spy,), config.initial_cash)
        try:
            curves["spy_exposure_adjusted"] = _exposure_adjusted(spy, result, config.initial_cash)
        except ValueError as exc:
            unavailable["spy_exposure_adjusted"] = str(exc)
    try:
        members = tuple(
            _aligned_bars(snapshot, symbol, dates) for symbol in config.approved_symbols
        )
    except ValueError as exc:
        missing("equal_weight", exc)
    else:
        curves["equal_weight"] = _buy_and_hold(members, config.initial_cash)
    for name, curve in curves.items():
        if name != "strategy":
            reports[name] = _benchmark_metrics(
                result, curve, config.initial_cash, settings=settings
            )
    warnings = (
        *snapshot.warnings,
        "benchmark_price_return_only: raw prices; equivalence to total return is restricted "
        "to declared action/dividend-free coverage; no dividend-inclusive historical series.",
        "benchmark_costs_omitted: fees, slippage, spread, market impact and taxes are zero; "
        "strategy costs remain recorded.",
        f"benchmark_survivorship_limitation:{manifest.survivorship_bias}; "
        f"universe_source:{manifest.universe_source}",
        "exposure_comparator_analytical: lagged EOD allocation, fractional units, "
        "frictionless close-to-close return; not executable fills.",
        *(f"benchmark_unavailable:{name}:{reason}" for name, reason in sorted(unavailable.items())),
    )
    return BenchmarkComparison(
        curves=curves,
        metrics=reports,
        unavailable=unavailable,
        warnings=tuple(dict.fromkeys(warnings)),
        assumptions={
            "price_basis": (
                "Raw action/dividend-free price return; "
                "no separate dividend cash flows or adjustment factors."
            ),
            "initial_order": "frozen_before_first_session_open",
            "buy_and_hold": (
                "Initial capital divided by first aligned raw open; "
                "fractional units; no terminal liquidation."
            ),
            "equal_weight": (
                "Equal initial capital per configured approved symbol; fixed units; "
                "no rebalancing or missing-member substitution."
            ),
            "exposure_adjusted": (
                "First session cash, then prior strategy EOD gross exposure / equity "
                "weights next SPY close-to-close return; no current-session exposure."
            ),
            "cash_annual_return": 0,
            "benchmark_fee_bps": 0,
            "benchmark_slippage_bps": 0,
            "dates": (
                "Exact strategy result sessions, "
                "equal to snapshot sessions within configured range."
            ),
            "dataset_manifest_sha256": snapshot.manifest_sha256,
        },
    )

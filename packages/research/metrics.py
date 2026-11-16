"""Audited research metrics; the historical backtest metrics remain unchanged.

The declared capital precedes the first close. Each close contributes one session
return, including the first session. The calendar must be complete at the caller's
snapshot boundary; this module never inserts or drops observations.
"""

from __future__ import annotations

import math
import statistics
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.backtesting.models import BacktestResult


class MetricSettings(BaseModel):
    """Frozen conventions recorded verbatim with every metric report."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    sessions_per_year: int = Field(default=252, ge=1, strict=True)
    minimum_annualization_sessions: int = Field(default=252, ge=2, strict=True)
    annual_risk_free_rate: float = Field(default=0, gt=-1)
    annual_downside_target: float = Field(default=0, gt=-1)
    sharpe_ddof: Literal[0, 1] = 1


class ResearchMetricReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    values: dict[str, float | int | None]
    undefined: dict[str, str]
    definitions: dict[str, str]
    units: dict[str, str]
    assumptions: dict[str, object]


def evaluate_research_metrics(
    result: BacktestResult,
    initial_cash: float,
    *,
    settings: MetricSettings | None = None,
) -> ResearchMetricReport:
    """Evaluate daily equity and actual fills without altering legacy arithmetic.

    Cost removal is a fixed-execution accounting bridge, not a zero-cost strategy
    rerun: changed cash availability can change a hypothetical strategy's fills.
    Holding sessions count elapsed session boundaries (same-session trades: zero).
    Open holdings are right-censored and reported separately from closed trades.
    """
    if not math.isfinite(initial_cash) or initial_cash <= 0:
        raise ValueError("invalid_initial_capital")
    convention = settings or MetricSettings()
    curve = result.equity_curve
    dates = tuple(p.date for p in curve)
    if dates != tuple(sorted(set(dates))):
        raise ValueError("equity_dates_must_be_sorted_unique")
    if any(
        not all(math.isfinite(v) for v in (p.equity, p.cash, p.gross_exposure))
        or p.equity < 0
        or p.gross_exposure < 0
        for p in curve
    ):
        raise ValueError("nonfinite_equity_point")
    if any(not math.isfinite(t.pnl) for t in result.trades):
        raise ValueError("nonfinite_trade_pnl")

    values: dict[str, float | int | None] = {}
    undefined: dict[str, str] = {}
    definitions: dict[str, str] = {}
    units: dict[str, str] = {}

    def metric(
        name: str,
        value: float | int | None,
        unit: str,
        definition: str,
        reason: str = "empty_equity_curve",
    ) -> None:
        if value is not None and not math.isfinite(value):
            value, reason = None, "numerical_overflow"
        values[name], definitions[name], units[name] = value, definition, unit
        if value is None:
            undefined[name] = reason

    terminal = curve[-1].equity if curve else None
    net_pnl = terminal - initial_cash if terminal is not None else None
    total = net_pnl / initial_cash if net_pnl is not None else None
    metric("total_return", total, "fraction", "Last close equity / declared initial capital - 1.")
    metric("net_return", total, "fraction", "Total return after recorded execution costs.")
    metric("net_pnl", net_pnl, "currency", "Last close equity minus declared initial capital.")
    annualized = None
    annual_reason = "empty_equity_curve" if not curve else "insufficient_sessions_for_annualization"
    if terminal is not None and len(curve) >= convention.minimum_annualization_sessions:
        try:
            annualized = (terminal / initial_cash) ** (
                convention.sessions_per_year / len(curve)
            ) - 1
        except OverflowError:
            annual_reason = "numerical_overflow"
    metric(
        "annualized_return",
        annualized,
        "fraction_per_year",
        "(Last equity / initial capital) ** (sessions_per_year / observed sessions) - 1; "
        "requires minimum_annualization_sessions.",
        annual_reason,
    )
    peak, worst = initial_cash, 0.0
    for point in curve:
        peak = max(peak, point.equity)
        worst = min(worst, point.equity / peak - 1)
    metric(
        "max_drawdown",
        worst if curve else None,
        "fraction",
        "Minimum equity / running peak - 1, including initial capital in the peak.",
    )
    metric(
        "max_drawdown_magnitude",
        -worst if curve else None,
        "fraction",
        "Nonnegative magnitude of signed maximum drawdown.",
    )
    metric(
        "average_exposure",
        statistics.fmean(p.gross_exposure / p.equity for p in curve)
        if curve and all(p.equity > 0 for p in curve)
        else None,
        "fraction",
        "Unweighted mean of each session's EOD gross marked exposure / equity.",
        "nonpositive_equity" if curve else "empty_equity_curve",
    )
    metric(
        "average_gross_exposure",
        statistics.fmean(p.gross_exposure for p in curve) if curve else None,
        "currency",
        "Unweighted mean EOD gross marked exposure in account currency.",
    )

    returns: list[float] = []
    previous, risk_reason = initial_cash, "insufficient_returns"
    for point in curve:
        if previous <= 0:
            risk_reason = "nonpositive_previous_equity"
            break
        returns.append(point.equity / previous - 1)
        previous = point.equity
    valid_returns = len(returns) == len(curve) and len(returns) >= 2
    rf = math.expm1(math.log1p(convention.annual_risk_free_rate) / convention.sessions_per_year)
    target = math.expm1(
        math.log1p(convention.annual_downside_target) / convention.sessions_per_year
    )
    sharpe = sortino = None
    sharpe_reason = sortino_reason = risk_reason
    if valid_returns:
        mean = statistics.fmean(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - convention.sharpe_ddof)
        if variance > 0:
            sharpe = (mean - rf) / math.sqrt(variance) * math.sqrt(convention.sessions_per_year)
        else:
            sharpe_reason = "zero_return_variance"
        downside = math.sqrt(statistics.fmean(min(0, r - target) ** 2 for r in returns))
        if downside > 0:
            sortino = (mean - target) / downside * math.sqrt(convention.sessions_per_year)
        else:
            sortino_reason = "zero_downside_deviation"
    metric(
        "sharpe",
        sharpe,
        "ratio",
        "sqrt(sessions_per_year) * mean(session return - compounded daily risk-free rate) / "
        "return standard deviation with configured ddof; at least two returns.",
        sharpe_reason,
    )
    metric(
        "sortino",
        sortino,
        "ratio",
        "sqrt(sessions_per_year) * mean(session return - compounded daily target) / "
        "sqrt(mean(min(return - target, 0) ** 2)); at least two returns, "
        "all sessions in RMS denominator.",
        sortino_reason,
    )

    trades = result.trades
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    metric("trade_count", len(trades), "count", "Number of closed trades; open positions excluded.")
    metric(
        "win_rate",
        len(wins) / len(trades) if trades else None,
        "fraction",
        "Strictly positive net-P&L closed trades / all closed trades (including breakeven).",
        "no_closed_trades",
    )
    metric(
        "average_win",
        statistics.fmean(wins) if wins else None,
        "currency",
        "Mean strictly positive closed-trade net P&L.",
        "no_winning_trades",
    )
    metric(
        "average_loss",
        statistics.fmean(losses) if losses else None,
        "currency",
        "Mean strictly negative closed-trade net P&L.",
        "no_losing_trades",
    )
    metric(
        "profit_factor",
        sum(wins) / -sum(losses) if losses else None,
        "ratio",
        "Sum positive closed-trade net P&L / magnitude of sum negative closed-trade net P&L.",
        "no_losing_trades" if trades else "no_closed_trades",
    )
    metric(
        "realized_pnl",
        sum(t.pnl for t in trades),
        "currency",
        "Sum closed-trade net P&L, including their entry/exit fees.",
    )
    metric(
        "unrealized_pnl",
        sum(p.unrealized_pnl for p in result.open_positions),
        "currency",
        "Sum terminal open-position unrealized P&L, including their entry fees.",
    )
    metric(
        "open_position_count",
        len(result.open_positions),
        "count",
        "Number of identified terminal open positions.",
    )

    date_index = {d: i for i, d in enumerate(dates)}
    for prefix, intervals in (
        ("", [(t.entry_date, t.exit_date) for t in trades]),
        ("open_", [(p.entry_date, dates[-1]) for p in result.open_positions] if dates else []),
    ):
        if any(start > end for start, end in intervals):
            raise ValueError("negative_holding_period")
        reason = "no_open_positions" if prefix else "no_closed_trades"
        if prefix and result.open_positions and not dates:
            reason = "empty_equity_curve"
        calendar_mean = (
            statistics.fmean((end - start).days for start, end in intervals) if intervals else None
        )
        in_curve = all(start in date_index and end in date_index for start, end in intervals)
        session_mean = (
            statistics.fmean(date_index[end] - date_index[start] for start, end in intervals)
            if intervals and in_curve
            else None
        )
        metric(
            f"average_{prefix}holding_calendar_days",
            calendar_mean,
            "calendar_days",
            "Mean elapsed calendar days from entry to exit "
            "(or terminal mark for right-censored open positions).",
            reason,
        )
        metric(
            f"average_{prefix}holding_sessions",
            session_mean,
            "sessions",
            "Mean elapsed observed session boundaries from entry to exit "
            "(or terminal mark for right-censored open positions); same-session holding is zero.",
            "holding_dates_outside_equity_curve" if intervals and not in_curve else reason,
        )

    fills = [e for e in result.order_events if e.status == "filled"]
    for fill in fills:
        if (
            fill.fill_price is None
            or fill.base_price is None
            or fill.quantity <= 0
            or fill.session not in date_index
            or not all(
                math.isfinite(v)
                for v in (fill.fill_price, fill.base_price, fill.fee, fill.slippage_cost)
            )
            or min(fill.fill_price, fill.base_price) <= 0
            or min(fill.fee, fill.slippage_cost) < 0
            or not math.isclose(
                fill.slippage_cost,
                abs(fill.fill_price - fill.base_price) * fill.quantity,
                rel_tol=1e-9,
                abs_tol=1e-8,
            )
        ):
            raise ValueError("invalid_filled_order_event")
    known_costs = bool(fills) or not (
        trades or result.open_positions or any(p.gross_exposure for p in curve)
    )
    fees = sum(e.fee for e in fills) if known_costs else None
    slippage = sum(e.slippage_cost for e in fills) if known_costs else None
    costs = fees + slippage if fees is not None and slippage is not None else None
    notional = sum(e.quantity * e.fill_price for e in fills if e.fill_price is not None)
    reason = "missing_filled_order_events"
    metric(
        "turnover",
        notional / initial_cash if known_costs else None,
        "fraction",
        "Sum absolute filled notional across buys and sells / declared initial capital; "
        "no divide-by-two.",
        reason,
    )
    metric(
        "fees",
        fees,
        "currency",
        "Sum recorded fees on filled events, including terminal-open entries.",
        reason,
    )
    metric(
        "slippage",
        slippage,
        "currency",
        "Sum abs(fill price - base price) * quantity on filled events.",
        reason,
    )
    metric(
        "transaction_cost",
        costs,
        "currency",
        "Recorded fees plus absolute modeled slippage cost.",
        reason,
    )
    gross_pnl = net_pnl + costs if net_pnl is not None and costs is not None else None
    gross_reason = "empty_equity_curve" if net_pnl is None else reason
    metric(
        "gross_pnl",
        gross_pnl,
        "currency",
        "Net P&L plus fees and slippage: fixed-execution accounting bridge, "
        "not a counterfactual rerun.",
        gross_reason,
    )
    metric(
        "gross_return",
        gross_pnl / initial_cash if gross_pnl is not None else None,
        "fraction",
        "Fixed-execution gross P&L / declared initial capital.",
        gross_reason,
    )
    for status in ("rejected", "unfilled"):
        metric(
            f"{status}_count",
            sum(e.status == status for e in result.order_events),
            "count",
            f"Number of {status} order/decision records.",
        )
    return ResearchMetricReport(
        values=values,
        undefined=undefined,
        definitions=definitions,
        units=units,
        assumptions={
            "initial_capital": initial_cash,
            "settings": convention.model_dump(mode="json"),
            "initial_equity": "Declared initial capital immediately before first observed session.",
            "calendar": (
                "One EOD observation per declared trading session; no inserted or skipped returns."
            ),
            "cost_bridge": (
                "Same fills/quantities; gross = net + recorded fees + absolute slippage; "
                "no hypothetical rerun."
            ),
            "fill_ledger": (
                "Recorded research filled events are assumed complete; legacy results without "
                "filled-event provenance have undefined costs and turnover when holdings exist."
            ),
            "currency": "Account currency; no foreign-exchange conversion.",
            "open_holdings": (
                "Right-censored at final observation; excluded from closed-trade statistics."
            ),
        },
    )

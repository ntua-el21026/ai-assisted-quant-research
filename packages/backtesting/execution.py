"""Causal, full-or-none, long-only daily simulation (research-execution/v1).

Session phases: opening stops/exits, ordered opening entries, intraday stops,
close marks and next-session exit/trailing decisions. No broker or provider I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from packages.backtesting.metrics import calculate_backtest_metrics
from packages.backtesting.models import (
    BacktestResult,
    BacktestTrade,
    EquityPoint,
    OpenResearchPosition,
    ResearchOrderEvent,
)
from packages.data.features import compute_feature_rows
from packages.data.models import AdjustedDailyBar
from packages.data.snapshots import DatasetSnapshot
from packages.research.models import ResearchConfig, ResearchDecision, ResearchSignalSet
from packages.research.signals import available_history, simulation_risk_input
from packages.risk.checks import evaluate_simulated_risk_order
from packages.strategy.exits import evaluate_exit_conditions, trailing_stop_price


@dataclass
class _Position:
    decision: ResearchDecision
    entry_date: date
    quantity: int
    entry_price: float
    entry_fee: float
    stop: float
    initial_risk: float
    highest_close: float
    stop_decision: ResearchDecision
    held: int = 0


def run_causal_backtest(
    snapshot: DatasetSnapshot,
    signals: ResearchSignalSet,
    config: ResearchConfig,
    *,
    neutral_entry_fills: tuple[ResearchOrderEvent, ...] | None = None,
) -> BacktestResult:
    """Simulate, optionally bounding AI entries by the paired neutral opening phase.

    The shadow gate is consulted only at the eligible opening session, never by
    feature/decision generation. It reads only that session's executable entry
    quantity. Later shadow fills cannot authorize an earlier order. The default
    remains the R1 execution contract.
    """
    shadow_limits = (
        {
            (e.session, e.order_id, e.symbol): e.quantity
            for e in neutral_entry_fills
            if e.action == "buy" and e.status == "filled"
        }
        if neutral_entry_fills is not None
        else None
    )
    calendar = snapshot.session_by_date
    dates = tuple(s.date for s in snapshot.sessions)
    active_dates = tuple(d for d in dates if config.date_start <= d <= config.date_end)
    if not active_dates:
        raise ValueError("empty_research_range")
    lookup = {s: {b.date: b for b in bars} for s, bars in snapshot.execution_bars_by_symbol.items()}
    if any(b.adjusted for bars in snapshot.execution_bars_by_symbol.values() for b in bars):
        raise ValueError("raw_execution_prices_required")
    scheduled: dict[date, list[ResearchDecision]] = {}
    events: list[ResearchOrderEvent] = []
    trades: list[BacktestTrade] = []
    positions: dict[str, _Position] = {}
    cash = config.initial_cash
    points: list[EquityPoint] = []

    def event(
        d: ResearchDecision,
        status: str,
        reason: str,
        session: date | None,
        base: float | None = None,
        fill: float | None = None,
        fee: float = 0,
        quantity: int | None = None,
        parent_entry_id: str | None = None,
    ) -> None:
        qty = d.quantity if quantity is None else quantity
        events.append(
            ResearchOrderEvent.model_validate(
                dict(
                    order_id=d.decision_id,
                    symbol=d.symbol,
                    action=d.action,
                    decision_session=d.decision_session,
                    decision_at=d.decision_at,
                    eligible_session=d.eligible_session,
                    session=session,
                    quantity=qty,
                    parent_entry_id=parent_entry_id,
                    decision_accepted=d.accepted,
                    decision_reason_codes=d.reason_codes,
                    reference_price=d.reference_price,
                    stop_price=d.stop_price,
                    breakout_level=d.breakout_level,
                    status=status,
                    reason=reason,
                    base_price=base,
                    fill_price=fill,
                    fee=fee,
                    slippage_cost=abs(fill - base) * qty
                    if fill is not None and base is not None
                    else 0,
                )
            )
        )

    seen_ids: set[str] = set()
    seen_orders: set[tuple[str, str, date | None]] = set()
    for d in sorted(
        signals.decisions, key=lambda d: (d.decision_session, d.symbol, d.action, d.decision_id)
    ):
        if (
            d.decision_session not in calendar
            or d.decision_at != calendar[d.decision_session].decision_at
        ):
            raise ValueError("invalid_decision_timing")
        next_index = dates.index(d.decision_session) + 1
        expected = dates[next_index] if next_index < len(dates) else None
        if d.eligible_session != expected:
            raise ValueError("invalid_eligible_session")
        if not config.date_start <= d.decision_session <= config.date_end:
            raise ValueError("decision_outside_research_range")
        if not d.accepted:
            event(d, "rejected", "|".join(d.reason_codes), d.decision_session)
            continue
        key = (d.symbol, d.action, d.eligible_session)
        if d.decision_id in seen_ids or key in seen_orders:
            event(d, "rejected", "duplicate_order", d.eligible_session)
            continue
        seen_ids.add(d.decision_id)
        seen_orders.add(key)
        if expected is None:
            event(d, "unfilled", "no_next_session", None)
        elif d.decision_at >= calendar[expected].open_at:
            raise ValueError("invalid_decision_timing")
        elif expected not in active_dates:
            event(d, "unfilled", "outside_research_range", expected)
        else:
            scheduled.setdefault(expected, []).append(d)

    def close_position(
        symbol: str,
        session: date,
        base: float,
        reason: str,
        decision: ResearchDecision | None = None,
    ) -> None:
        nonlocal cash
        p = positions.pop(symbol)
        slippage = (
            config.execution.stop_slippage_bps
            if reason in ("gap_stop", "intraday_stop")
            else config.execution.exit_slippage_bps
        )
        fill = base * (1 - slippage / 10000)
        notional = fill * p.quantity
        fee = notional * config.execution.fee_bps_per_side / 10000
        pnl = notional - fee - p.entry_price * p.quantity - p.entry_fee
        cash += notional - fee
        trades.append(
            BacktestTrade(
                symbol=symbol,
                entry_date=p.entry_date,
                exit_date=session,
                quantity=p.quantity,
                entry_price=p.entry_price,
                exit_price=fill,
                entry_fee=p.entry_fee,
                exit_fee=fee,
                pnl=pnl,
                return_pct=pnl / (p.entry_price * p.quantity),
            )
        )
        d = decision or p.stop_decision.model_copy(
            update={"action": "sell", "decision_id": f"{p.decision.decision_id}:stop:{session}"}
        )
        event(d, "filled", reason, session, base, fill, fee, p.quantity, p.decision.decision_id)

    day_start_equity = config.initial_cash
    week_start_equity = config.initial_cash
    month_start_equity = config.initial_cash
    prior_day: date | None = None
    bar: AdjustedDailyBar | None
    for session in active_dates:
        if prior_day is None or session.isocalendar()[:2] != prior_day.isocalendar()[:2]:
            week_start_equity = points[-1].equity if points else config.initial_cash
        if prior_day is None or (session.year, session.month) != (prior_day.year, prior_day.month):
            month_start_equity = points[-1].equity if points else config.initial_cash
        day_start_equity = points[-1].equity if points else config.initial_cash
        for symbol in sorted(positions):
            if session not in lookup.get(symbol, {}):
                raise ValueError(f"missing_position_bar:{symbol}:{session}")
        exited: set[str] = set()
        for symbol in sorted(tuple(positions)):
            bar = lookup[symbol][session]
            if bar.open <= positions[symbol].stop:
                close_position(symbol, session, bar.open, "gap_stop")
                exited.add(symbol)
        orders = sorted(
            scheduled.get(session, ()), key=lambda d: (d.action != "sell", d.symbol, d.decision_id)
        )
        for d in orders:
            bar = lookup.get(d.symbol, {}).get(session)
            if bar is None:
                event(d, "unfilled", "missing_execution_bar", session)
                continue
            if d.action == "sell":
                if d.symbol not in positions:
                    event(d, "rejected", "position_not_open", session)
                elif d.quantity != positions[d.symbol].quantity:
                    event(d, "rejected", "partial_exit_unsupported", session)
                else:
                    close_position(d.symbol, session, bar.open, "|".join(d.reason_codes), d)
                    exited.add(d.symbol)
                continue
            if d.symbol in positions:
                event(d, "rejected", "symbol_already_held", session)
                continue
            if d.symbol in exited:
                event(d, "rejected", "same_session_reentry", session)
                continue
            if d.symbol not in config.approved_symbols:
                event(d, "rejected", "symbol_not_approved", session)
                continue
            if shadow_limits is not None:
                limit = shadow_limits.get((session, d.decision_id, d.symbol), 0)
                if limit == 0:
                    event(d, "rejected", "neutral_shadow_entry_ineligible", session)
                    continue
                if d.quantity > limit:
                    event(d, "rejected", "neutral_shadow_quantity_exceeded", session)
                    continue
            fill = bar.open * (1 + config.execution.entry_slippage_bps / 10000)
            notional = d.quantity * fill
            fee = notional * config.execution.fee_bps_per_side / 10000
            if notional + fee > cash:
                event(d, "rejected", "insufficient_cash", session)
                continue
            gross = sum(lookup[s][session].open * p.quantity for s, p in positions.items())
            equity = cash + gross
            sector_value = sum(
                lookup[s][session].open * p.quantity
                for s, p in positions.items()
                if config.sectors[s] == config.sectors[d.symbol]
            )
            if equity <= 0:
                event(d, "rejected", "nonpositive_equity", session)
                continue
            assessment = evaluate_simulated_risk_order(
                simulation_risk_input(
                    d,
                    equity=equity,
                    cash=cash - fee,
                    price=fill,
                    gross=gross,
                    open_positions=len(positions),
                    sector_exposure=sector_value / equity,
                    daily_loss=max(0, 1 - equity / day_start_equity),
                    weekly_loss=max(0, 1 - equity / week_start_equity),
                    monthly_loss=max(0, 1 - equity / month_start_equity),
                ),
                risk_config=config.risk,
            )
            if not assessment.approved:
                event(d, "rejected", "|".join(assessment.rejection_reasons), session)
                continue
            assert d.stop_price is not None
            cash -= notional + fee
            positions[d.symbol] = _Position(
                d,
                session,
                d.quantity,
                fill,
                fee,
                d.stop_price,
                fill - d.stop_price,
                0.0,
                d.model_copy(update={"action": "sell", "reason_codes": ("protective_stop",)}),
            )
            event(d, "filled", "next_session_open", session, bar.open, fill, fee)
        # Intraday proceeds are available only after all opening orders were processed.
        for symbol in sorted(tuple(positions)):
            bar = lookup[symbol][session]
            if bar.low <= positions[symbol].stop:
                close_position(symbol, session, positions[symbol].stop, "intraday_stop")
        gross = sum(lookup[s][session].close * p.quantity for s, p in positions.items())
        points.append(
            EquityPoint(date=session, cash=cash, gross_exposure=gross, equity=cash + gross)
        )
        if cash < -1e-8:
            raise ValueError("negative_cash_invariant")
        realized = sum(t.pnl for t in trades)
        unrealized = sum(
            (lookup[s][session].close - p.entry_price) * p.quantity - p.entry_fee
            for s, p in positions.items()
        )
        if abs((cash + gross - config.initial_cash) - (realized + unrealized)) > 1e-7 * max(
            1, abs(cash + gross)
        ):
            raise ValueError("pnl_conservation_invariant")
        for symbol, p in sorted(positions.items()):
            p.held += 1
            history = available_history(snapshot, symbol, session, calendar[session].decision_at)
            expected_history = {d for d in dates if d <= session}
            if {b.date for b in history} != expected_history:
                raise ValueError(f"unavailable_position_features:{symbol}:{session}")
            features = compute_feature_rows(history, atr_window=config.strategy.atr_period)
            p.highest_close = max(p.highest_close, history[-1].close)
            exit_eval = evaluate_exit_conditions(
                closes=[f.close for f in features],
                ema_10_values=[f.ema_10 for f in features],
                bars_held=p.held,
                unrealized_r_multiple=(history[-1].close - p.entry_price) / p.initial_risk,
                bars_since_entry=p.held,
                breakout_level=p.decision.breakout_level or p.entry_price,
                technical_confirm_closes=config.strategy.technical_exit_confirm_closes,
                time_stop_days=config.strategy.time_stop_days,
                fail_fast_days=config.strategy.fail_fast_exit_days,
            )
            next_index = dates.index(session) + 1
            next_session = dates[next_index] if next_index < len(dates) else None
            if exit_eval.should_exit:
                d = ResearchDecision(
                    decision_id=f"{p.decision.decision_id}:exit:{session}",
                    symbol=symbol,
                    action="sell",
                    decision_session=session,
                    decision_at=calendar[session].decision_at,
                    eligible_session=next_session,
                    accepted=True,
                    quantity=p.quantity,
                    reference_price=history[-1].close,
                    reason_codes=exit_eval.reason_codes,
                )
                if next_session in active_dates:
                    scheduled.setdefault(next_session, []).append(d)
                else:
                    event(
                        d,
                        "unfilled",
                        "no_next_session" if next_session is None else "outside_research_range",
                        next_session,
                    )
            atr = features[-1].atr_14
            if atr is not None:
                new_stop = trailing_stop_price(
                    old_stop=p.stop,
                    highest_close_since_entry=p.highest_close,
                    atr_14=atr,
                    multiplier=config.strategy.trailing_stop_atr_multiplier,
                )
                if new_stop > p.stop:
                    p.stop = new_stop
                    p.stop_decision = ResearchDecision(
                        decision_id=f"{p.decision.decision_id}:trail:{session}",
                        symbol=symbol,
                        action="sell",
                        decision_session=session,
                        decision_at=calendar[session].decision_at,
                        eligible_session=next_session,
                        accepted=True,
                        quantity=p.quantity,
                        reference_price=history[-1].close,
                        stop_price=new_stop,
                        reason_codes=("trailing_stop_update",),
                    )
        prior_day = session
    terminal = tuple(
        OpenResearchPosition(
            symbol=s,
            entry_date=p.entry_date,
            quantity=p.quantity,
            entry_price=p.entry_price,
            entry_fee=p.entry_fee,
            stop_price=p.stop,
            mark_price=lookup[s][active_dates[-1]].close,
            cost_basis=p.entry_price * p.quantity + p.entry_fee,
            unrealized_pnl=(lookup[s][active_dates[-1]].close - p.entry_price) * p.quantity
            - p.entry_fee,
        )
        for s, p in sorted(positions.items())
    )
    # There is no fill at the first decision session, preserving the initial-cash metric baseline.
    metrics = calculate_backtest_metrics(equity_curve=points, trades=trades)
    metrics = metrics.model_copy(update={"sharpe": None, "sortino": None})
    return BacktestResult(
        name=config.experiment_id,
        trades=tuple(trades),
        equity_curve=tuple(points),
        metrics=metrics,
        validation_note="Synthetic or historical simulation is not proof of profitability.",
        optimistic_universe_warning=True,
        open_positions=terminal,
        order_events=tuple(
            sorted(
                events,
                key=lambda e: (e.session or date.max, e.symbol, e.order_id, e.status, e.reason),
            )
        ),
        warnings=("risk_adjusted_metrics_deferred_to_R2",),
    )

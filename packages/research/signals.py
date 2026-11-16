"""Causal adapters around existing feature, regime, candidate and sizing logic."""

from __future__ import annotations

import hashlib
from datetime import date, datetime

from packages.data.models import AdjustedDailyBar, FeatureRow, UniverseMember
from packages.data.snapshots import DatasetSnapshot
from packages.research.feature_cache import CausalFeatureCache
from packages.research.models import ResearchConfig, ResearchDecision, ResearchSignalSet
from packages.risk.checks import evaluate_simulated_risk_order
from packages.risk.models import KillSwitchSnapshot, NewRiskOrderInput, PositionSizingInput
from packages.risk.sizing import calculate_position_size
from packages.strategy.exits import initial_stop_price
from packages.strategy.models import EarningsBlackoutEvaluation, RegimeState
from packages.strategy.regime import classify_regime
from packages.strategy.signals import evaluate_candidate, evaluate_earnings_blackout


def available_history(
    snapshot: DatasetSnapshot,
    symbol: str,
    session: date,
    cutoff: datetime,
) -> tuple[AdjustedDailyBar, ...]:
    return tuple(
        b
        for b in snapshot.feature_bars_by_symbol.get(symbol, ())
        if b.date <= session and snapshot.availability_by_key[(symbol, b.date)] <= cutoff
    )


def simulation_risk_input(
    decision: ResearchDecision,
    *,
    equity: float,
    cash: float,
    price: float,
    gross: float = 0,
    open_positions: int = 0,
    sector_exposure: float = 0,
    daily_loss: float = 0,
    weekly_loss: float = 0,
    monthly_loss: float = 0,
) -> NewRiskOrderInput:
    return NewRiskOrderInput(
        symbol=decision.symbol,
        asset_class="equity",
        quantity=decision.quantity,
        entry_price=price,
        stop_loss_price=decision.stop_price,
        account_equity=equity,
        cash=cash,
        current_gross_exposure=gross,
        current_deployable_capital=gross,
        current_open_positions=open_positions,
        current_sector_exposure_pct=sector_exposure,
        daily_loss_pct=daily_loss,
        weekly_loss_pct=weekly_loss,
        monthly_loss_pct=monthly_loss,
        data_is_fresh=True,
        market_session_valid=True,
        broker_reconciliation_clean=None,
        broker_account_environment=None,
        kill_switch=KillSwitchSnapshot(),
        active_duplicate_intent=False,
        temporal_workflow_consistent=None,
        system_health_ok=True,
    )


def generate_research_signals(
    snapshot: DatasetSnapshot,
    config: ResearchConfig,
    *,
    feature_cache: CausalFeatureCache | None = None,
    disabled_filters: frozenset[str] = frozenset(),
) -> ResearchSignalSet:
    if not disabled_filters.issubset({"regime", "relative_strength", "volume"}):
        raise ValueError("unsupported_research_ablation")
    cache = feature_cache or CausalFeatureCache(
        snapshot,
        config.strategy.atr_period,
        through_date=config.date_end,
        proxy_symbol=config.regime.proxy,
    )
    cache.validate(snapshot, config.strategy.atr_period, config.date_end, config.regime.proxy)
    decisions: list[ResearchDecision] = []
    previous_state: RegimeState | None = None
    cooldown = 0
    all_dates = tuple(s.date for s in snapshot.sessions)
    for index, session in enumerate(cache.sessions):
        # The loop also traverses warm-up sessions before the requested range for regime state.
        histories = {
            symbol: cache.history(symbol, index, session.decision_at)
            for symbol in snapshot.feature_bars_by_symbol
        }
        proxy_complete = cache.complete(config.regime.proxy, index, session.decision_at)
        regime = None
        if proxy_complete:
            count = max(config.regime.risk_on_confirm_closes, config.regime.risk_off_confirm_closes)
            observations = cache.regime_observations[max(0, index + 1 - count) : index + 1]
            regime = classify_regime(
                observations,
                config.regime,
                previous_state="RISK_OFF" if cooldown > 0 else previous_state,
                cooldown_days_remaining=cooldown,
            )
            # Legacy classification blocks cooldown only on confirmed RISK_ON recovery.
            # Research enforces no new entries throughout the independent interval,
            # including non-confirming CAUTION, without changing operational callers.
            if cooldown > 0 and regime.state != "RISK_OFF":
                regime = regime.model_copy(
                    update={
                        "state": "CAUTION",
                        "new_entries_allowed": False,
                        "size_multiplier": 0.0,
                        "cooldown_days_remaining": cooldown,
                        "reason_codes": tuple(
                            dict.fromkeys((*regime.reason_codes, "risk_off_cooldown_active"))
                        ),
                    }
                )
            previous_state = regime.state
            # A risk-off session starts a cooldown of subsequent calendar sessions.
            # Preserve it through CAUTION and incomplete/non-confirming recovery states.
            cooldown = (
                config.regime.risk_off_cooldown_days
                if regime.state == "RISK_OFF"
                else max(0, cooldown - 1)
            )
        else:
            cooldown = max(0, cooldown - 1)
        if not config.date_start <= session.date <= config.date_end:
            continue
        features: dict[str, tuple[FeatureRow, ...]] = {}
        for symbol in histories:
            rows = cache.features(symbol, index, session.decision_at)
            if rows:
                features[symbol] = rows
        ranks = {
            symbol: rows[-1].rs_63
            for symbol, rows in features.items()
            if symbol in config.approved_symbols and rows[-1].rs_63 is not None
        }
        for symbol in sorted(histories):
            reasons: list[str] = []
            rows = features.get(symbol, ())
            history = histories[symbol]
            reference = history[-1].close if history and history[-1].date == session.date else None
            eligible = all_dates[index + 1] if index + 1 < len(all_dates) else None
            identity = (
                f"research-decision/v1:{snapshot.manifest_sha256}:{symbol}:{session.date}:buy"
            )
            base = dict(
                decision_id=hashlib.sha256(identity.encode()).hexdigest(),
                symbol=symbol,
                decision_session=session.date,
                decision_at=session.decision_at,
                eligible_session=eligible,
                accepted=False,
                quantity=0,
                reference_price=reference,
                reason_codes=(),
            )
            if symbol not in config.approved_symbols:
                reasons.append("symbol_not_approved")
            if reference is None:
                reasons.append("observation_unavailable")
            if not rows or regime is None:
                reasons.append("incomplete_feature_history")
            if len(rows) < 200:
                reasons.append("insufficient_warmup")
            if reasons:
                decisions.append(
                    ResearchDecision.model_validate({**base, "reason_codes": tuple(reasons)})
                )
                continue
            assert regime is not None
            if symbol in config.etf_symbols:
                earnings = EarningsBlackoutEvaluation(
                    status="clear",
                    as_of=session.date,
                    allow_entries=True,
                    reason_codes=("etf_earnings_not_applicable",),
                )
            else:
                known = sorted(
                    (
                        e
                        for e in config.earnings
                        if e.symbol == symbol and e.available_at <= session.decision_at
                    ),
                    key=lambda e: (e.available_at, e.earnings_date),
                )
                evaluations = tuple(
                    evaluate_earnings_blackout(
                        as_of=session.date,
                        earnings_date=e.earnings_date,
                        trading_calendar=all_dates,
                    )
                    for e in known
                )
                if not evaluations:
                    earnings = evaluate_earnings_blackout(
                        as_of=session.date, earnings_date=None, trading_calendar=all_dates
                    )
                else:
                    # v1 announcements are additive facts, not implicit revisions.
                    # Every known event can block; a later date cannot erase a blackout.
                    earnings = next(
                        (e for e in evaluations if e.status == "blackout"),
                        next((e for e in evaluations if not e.allow_entries), evaluations[-1]),
                    )
            own_rank = ranks.get(symbol)
            percentile = (
                (100 * sum(v <= own_rank for v in ranks.values() if v is not None) / len(ranks))
                if own_rank is not None
                else None
            )
            candidate = evaluate_candidate(
                rows[-1],
                universe_member=UniverseMember(
                    symbol=symbol,
                    universe="research",
                    as_of=session.date,
                    included=True,
                    point_in_time_available=False,
                    optimistic_backtest_warning=True,
                ),
                strategy_config=config.strategy,
                research_universe_config=config.research_universe,
                regime=regime,
                disabled_filters=disabled_filters,
                earnings=earnings,
                prior_high_20=max(b.high for b in history[-21:-1]),
                prior_high_55=max(b.high for b in history[-56:-1]),
                rs_percentile=percentile,
            )
            if not candidate.accepted:
                decisions.append(
                    ResearchDecision.model_validate(
                        {**base, "reason_codes": candidate.rejection_reasons}
                    )
                )
                continue
            atr = rows[-1].atr_14
            assert atr is not None and reference is not None
            stop = initial_stop_price(
                entry_price=reference,
                atr_14=atr,
                multiplier=config.strategy.initial_stop_atr_multiplier,
            )
            if stop <= 0:
                decisions.append(
                    ResearchDecision.model_validate(
                        {**base, "reason_codes": ("invalid_stop_distance",)}
                    )
                )
                continue
            sizing = calculate_position_size(
                PositionSizingInput(
                    account_equity=config.initial_cash,
                    entry_price=reference,
                    stop_price=stop,
                    regime_size_multiplier=1.0
                    if "regime" in disabled_filters
                    else regime.size_multiplier,
                ),
                config.risk,
            )
            if not sizing.accepted:
                decisions.append(
                    ResearchDecision.model_validate(
                        {**base, "reason_codes": sizing.rejection_reasons}
                    )
                )
                continue
            decision = ResearchDecision.model_validate(
                {
                    **base,
                    "accepted": True,
                    "quantity": sizing.shares,
                    "stop_price": stop,
                    "breakout_level": candidate.breakout_level,
                    "reason_codes": candidate.reason_codes + ("simulation_risk_sizing",),
                }
            )
            assessment = evaluate_simulated_risk_order(
                simulation_risk_input(
                    decision, equity=config.initial_cash, cash=config.initial_cash, price=reference
                ),
                risk_config=config.risk,
            )
            if not assessment.approved:
                decision = decision.model_copy(
                    update={"accepted": False, "reason_codes": assessment.rejection_reasons}
                )
            decisions.append(decision)
    return ResearchSignalSet(decisions=tuple(decisions))

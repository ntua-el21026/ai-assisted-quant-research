"""Versioned, explicit contracts for the offline R1 baseline."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.core.config import (
    RegimeConfig,
    ResearchUniverseConfig,
    RiskLevelConfig,
    StrategyConfig,
)


class ResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ExecutionCosts(ResearchModel):
    entry_slippage_bps: float = Field(ge=0, lt=10000)
    exit_slippage_bps: float = Field(ge=0, lt=10000)
    stop_slippage_bps: float = Field(ge=0, lt=10000)
    fee_bps_per_side: float = Field(ge=0, lt=10000)


class EarningsAnnouncement(ResearchModel):
    symbol: str
    earnings_date: date
    available_at: datetime

    @model_validator(mode="after")
    def aware(self) -> Self:
        if self.available_at.tzinfo is None:
            raise ValueError("earnings availability requires an offset")
        return self


class ResearchConfig(ResearchModel):
    schema_version: Literal["research-config/v1"]
    experiment_id: str = Field(min_length=1)
    dataset_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hypothesis: str = Field(min_length=1)
    seed: int = Field(ge=0)
    date_start: date
    date_end: date
    initial_cash: float = Field(gt=0)
    approved_symbols: tuple[str, ...] = Field(min_length=1)
    etf_symbols: tuple[str, ...]
    sectors: dict[str, str]
    earnings: tuple[EarningsAnnouncement, ...]
    strategy: StrategyConfig
    regime: RegimeConfig
    risk: RiskLevelConfig
    research_universe: ResearchUniverseConfig
    execution: ExecutionCosts

    @model_validator(mode="after")
    def supported_baseline(self) -> Self:
        if self.date_start > self.date_end:
            raise ValueError("invalid_research_range")
        if tuple(sorted(set(self.approved_symbols))) != self.approved_symbols:
            raise ValueError("approved_symbols must be sorted and unique")
        if any(s != s.upper() for s in (*self.approved_symbols, *self.etf_symbols)):
            raise ValueError("symbols must be uppercase")
        if not set(self.approved_symbols).issubset(self.sectors):
            raise ValueError("sector metadata required for each approved symbol")
        strategy = self.strategy
        if (
            strategy.trend_fast_ma,
            strategy.trend_slow_ma,
            strategy.volume_lookback_days,
            strategy.relative_strength_lookback_days,
            strategy.technical_exit_ema,
            self.regime.sma_fast,
            self.regime.sma_slow,
        ) != (50, 200, 20, 63, 10, 50, 200):
            raise ValueError("unsupported_feature_periods")
        if any(v not in (20, 55) for v in strategy.breakout_lookback_research_variants):
            raise ValueError("unsupported_breakout_period")

        def finite(value: object) -> bool:
            if isinstance(value, float):
                return math.isfinite(value)
            if isinstance(value, dict):
                return all(finite(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return all(finite(v) for v in value)
            return True

        if not finite(self.model_dump()):
            raise ValueError("nonfinite_configuration")
        return self


class ResearchDecision(ResearchModel):
    decision_id: str
    symbol: str
    action: Literal["buy", "sell"] = "buy"
    decision_session: date
    decision_at: datetime
    eligible_session: date | None
    accepted: bool
    quantity: int = Field(ge=0)
    reference_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    breakout_level: float | None = Field(default=None, gt=0)
    reason_codes: tuple[str, ...]

    @model_validator(mode="after")
    def causal_contract(self) -> Self:
        if self.decision_at.tzinfo is None:
            raise ValueError("decision_timestamp_requires_offset")
        if self.eligible_session is not None and self.eligible_session <= self.decision_session:
            raise ValueError("eligible_session_must_follow_decision")
        if self.accepted and (self.quantity < 1 or self.reference_price is None):
            raise ValueError("accepted_decision_requires_quantity_and_price")
        if self.accepted and self.action == "buy" and self.stop_price is None:
            raise ValueError("accepted_entry_requires_stop")
        return self


class ResearchSignalSet(ResearchModel):
    decisions: tuple[ResearchDecision, ...]

    @property
    def accepted_signals(self) -> tuple[ResearchDecision, ...]:
        return tuple(d for d in self.decisions if d.accepted)

    @property
    def rejected_decisions(self) -> tuple[ResearchDecision, ...]:
        return tuple(d for d in self.decisions if not d.accepted)

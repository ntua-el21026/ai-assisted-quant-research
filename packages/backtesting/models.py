"""Typed backtest input, output, and metrics models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.data.models import AdjustedDailyBar


class BacktestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SlippageAssumptions(BacktestModel):
    entry_slippage_bps: float = Field(default=0.0, ge=0)
    exit_slippage_bps: float = Field(default=0.0, ge=0)
    fee_bps_per_side: float = Field(default=0.0, ge=0)


class BacktestSignal(BacktestModel):
    symbol: str
    date: date
    action: Literal["buy", "sell"]
    quantity: int = Field(gt=0)


class BacktestInput(BacktestModel):
    name: str
    initial_cash: float = Field(gt=0)
    bars_by_symbol: dict[str, tuple[AdjustedDailyBar, ...]]
    signals: tuple[BacktestSignal, ...] = ()
    slippage: SlippageAssumptions = Field(default_factory=SlippageAssumptions)
    benchmark_returns: tuple[float, ...] = ()
    validation_note: str = "Backtests are validation tools, not proof of profitability."


class BacktestTrade(BacktestModel):
    symbol: str
    entry_date: date
    exit_date: date
    quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    exit_price: float = Field(gt=0)
    entry_fee: float = Field(ge=0)
    exit_fee: float = Field(ge=0)
    pnl: float
    return_pct: float


class EquityPoint(BacktestModel):
    date: date
    equity: float = Field(ge=0)
    cash: float
    gross_exposure: float = Field(ge=0)


class BacktestMetrics(BacktestModel):
    total_return: float | None
    max_drawdown: float | None
    average_exposure: float | None
    trade_count: int
    win_rate: float | None
    average_win: float | None
    average_loss: float | None
    profit_factor: float | None
    sharpe: float | None
    sortino: float | None


class OpenResearchPosition(BacktestModel):
    symbol: str
    entry_date: date
    quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    entry_fee: float = Field(ge=0)
    stop_price: float = Field(gt=0)
    mark_price: float = Field(gt=0)
    cost_basis: float = Field(gt=0)
    unrealized_pnl: float


class ResearchOrderEvent(BacktestModel):
    order_id: str
    symbol: str
    action: Literal["buy", "sell"]
    decision_session: date
    decision_at: datetime
    eligible_session: date | None
    session: date | None
    quantity: int = Field(ge=0)
    status: Literal["filled", "rejected", "unfilled"]
    reason: str
    base_price: float | None = None
    fill_price: float | None = None
    fee: float = Field(default=0, ge=0)
    slippage_cost: float = Field(default=0, ge=0)


class BacktestResult(BacktestModel):
    name: str
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    metrics: BacktestMetrics
    validation_note: str
    optimistic_universe_warning: bool = False
    open_positions: tuple[OpenResearchPosition, ...] = ()
    order_events: tuple[ResearchOrderEvent, ...] = ()
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_note(self) -> Self:
        if "not proof of profitability" not in self.validation_note:
            raise ValueError("validation note must state that backtests do not prove profitability")
        return self

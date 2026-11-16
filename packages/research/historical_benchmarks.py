"""Explicit single-security analytical return conventions on raw historical bars.

These frictionless comparators use exact rational arithmetic internally, separate
from the finite-Decimal portfolio action ledger. Reported Decimal amounts round to
50 significant digits, ROUND_HALF_EVEN; reported equity sums the reported cash,
receivable and marked value under that same context. Rational strings retain the
unrounded units and equity. No rounded output is described as exact.

A frozen initial allocation buys at the first selected open. Splits precede ex-date
entitlements based on prior-close holdings. Cash dividends are receivables on ex-date
and cash on the first calendar session on/after payment. Reinvestment assumes that
cash is available at that session's open, an explicit analytical payment-open rule,
not evidence of actual intraday payment availability. It never uses a future close.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from fractions import Fraction
from typing import Literal, Protocol

from packages.data.corporate_actions import (
    CashDividendAction,
    CorporateAction,
    SplitAction,
    validate_actions,
)

ReturnConvention = Literal["price_return", "total_return_cash", "total_return_reinvest"]
BENCHMARK_DECIMAL_PRECISION = 50


class _Session(Protocol):
    @property
    def date(self) -> date: ...
    @property
    def open_at(self) -> datetime: ...
    @property
    def close_at(self) -> datetime: ...


class _Security(Protocol):
    @property
    def security_id(self) -> str: ...


class _Manifest(Protocol):
    @property
    def execution_price_basis(self) -> str: ...
    @property
    def currency(self) -> str: ...
    @property
    def sessions(self) -> Sequence[_Session]: ...
    @property
    def securities(self) -> Sequence[_Security]: ...


class _Bar(Protocol):
    @property
    def security_id(self) -> str: ...
    @property
    def symbol(self) -> str: ...
    @property
    def date(self) -> date: ...
    @property
    def open(self) -> Decimal: ...
    @property
    def high(self) -> Decimal: ...
    @property
    def low(self) -> Decimal: ...
    @property
    def close(self) -> Decimal: ...
    @property
    def volume(self) -> Decimal: ...


class HistoricalBenchmarkSnapshot(Protocol):
    @property
    def manifest(self) -> _Manifest: ...
    @property
    def manifest_sha256(self) -> str: ...
    @property
    def raw_bars(self) -> Sequence[_Bar]: ...
    @property
    def actions(self) -> Sequence[CorporateAction]: ...


@dataclass(frozen=True)
class HistoricalBenchmarkConventions:
    return_convention: ReturnConvention
    currency: str = "USD"
    execution_price_basis: str = "raw"
    split_accounting: str = "explicit_ratio_before_open"
    dividend_recognition: str = "ex_date_prior_close_post_split_units"
    dividend_payment: str = "first_session_open_on_or_after_payment_date"
    dividend_reinvestment: str = "none"
    initial_allocation: str = "first_selected_session_open"
    fractional_units: str = "exact_rational_internal"
    decimal_reporting: str = "50_significant_digits_ROUND_HALF_EVEN"
    cash_return: str = "zero"


@dataclass(frozen=True)
class HistoricalBenchmarkPoint:
    date: date
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    cash: Decimal
    dividend_receivable: Decimal
    market_value: Decimal
    equity: Decimal
    reinvested_cash: Decimal
    quantity_rational: str
    equity_rational: str


@dataclass(frozen=True)
class HistoricalBenchmarkResult:
    security_id: str
    dataset_manifest_sha256: str
    initial_cash: Decimal
    conventions: HistoricalBenchmarkConventions
    points: tuple[HistoricalBenchmarkPoint, ...]
    total_return: Decimal
    total_return_rational: str
    warnings: tuple[str, ...] = (
        "analytical_fractional_benchmark_zero_fees_slippage_taxes_and_cash_yield",
        "payment_open_cash_availability_is_an_explicit_assumption",
        "reported_decimals_are_rounded_separately_from_exact_rational_provenance",
    )


def require_compatible_benchmark_conventions(
    left: HistoricalBenchmarkConventions, right: HistoricalBenchmarkConventions
) -> None:
    """Require declared return conventions to agree before comparing performance.

    Equal metadata does not establish calendar, universe or empirical comparability;
    those checks belong to the experiment. Strategy transaction costs may differ
    from a frictionless benchmark, but PR and either dividend policy cannot be
    silently substituted for each other.
    """
    if left != right:
        raise ValueError("incompatible_benchmark_return_conventions")


def _decimal(number: Fraction) -> Decimal:
    with localcontext(Context(prec=BENCHMARK_DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)):
        return Decimal(number.numerator) / Decimal(number.denominator)


def _rational(number: Fraction) -> str:
    return f"{number.numerator}/{number.denominator}"


def _validate(
    snapshot: HistoricalBenchmarkSnapshot, security_id: str, dates: tuple[date, ...] | None
) -> tuple[tuple[_Session, ...], dict[date, _Bar], tuple[CorporateAction, ...]]:
    manifest = snapshot.manifest
    if manifest.execution_price_basis != "raw":
        raise ValueError("benchmark_requires_raw_execution_prices_no_adjustment_double_count")
    if manifest.currency != "USD":
        raise ValueError("unsupported_benchmark_currency")
    securities = tuple(s.security_id for s in manifest.securities)
    if len(set(securities)) != len(securities) or security_id not in securities:
        raise ValueError("unknown_or_duplicate_benchmark_security")
    calendar = tuple(manifest.sessions)
    calendar_dates = tuple(s.date for s in calendar)
    if not calendar or calendar_dates != tuple(sorted(set(calendar_dates))):
        raise ValueError("invalid_benchmark_calendar")
    for session in calendar:
        if (
            session.open_at.utcoffset() is None or session.close_at.utcoffset() is None
            or session.open_at >= session.close_at
        ):
            raise ValueError("invalid_benchmark_session_timestamps")
    selected = calendar_dates if dates is None else dates
    if not selected or selected != tuple(
        d for d in calendar_dates if selected[0] <= d <= selected[-1]
    ):
        raise ValueError("benchmark_requested_calendar_gap_or_mismatch")
    bars: dict[tuple[str, date], _Bar] = {}
    for bar in snapshot.raw_bars:
        if getattr(bar, "adjusted", False):
            raise ValueError("benchmark_requires_raw_rows_no_adjusted_execution")
        key = (bar.security_id, bar.date)
        if bar.security_id not in securities or bar.date not in calendar_dates:
            raise ValueError("unknown_benchmark_price_mapping")
        if key in bars:
            raise ValueError("duplicate_benchmark_price")
        prices = (bar.open, bar.high, bar.low, bar.close)
        if (
            any(not isinstance(v, Decimal) or not v.is_finite() or v <= 0 for v in prices)
            or not isinstance(bar.volume, Decimal) or not bar.volume.is_finite()
            or bar.volume < 0 or bar.low > min(bar.open, bar.close)
            or bar.high < max(bar.open, bar.close) or bar.high < bar.low
        ):
            raise ValueError("invalid_benchmark_ohlcv")
        bars[key] = bar
    lookup = {}
    for d in selected:
        if (security_id, d) not in bars:
            raise ValueError(f"missing_benchmark_price:{security_id}:{d}")
        lookup[d] = bars[(security_id, d)]
    sessions = tuple(s for s in calendar if s.date in selected)
    session_by_date = {s.date: s for s in calendar}
    ordered = validate_actions(snapshot.actions)
    for action in ordered:
        if action.security_id not in securities:
            raise ValueError("unknown_benchmark_action_mapping")
        effective_session = session_by_date.get(action.ex_date)
        if effective_session is None:
            raise ValueError("benchmark_action_outside_calendar")
        action_bar = bars.get((action.security_id, action.ex_date))
        if action_bar is None or action_bar.symbol != action.symbol:
            raise ValueError("benchmark_action_symbol_mapping_mismatch")
        if (
            action.available_at.utcoffset() is None
            or action.available_at > effective_session.open_at
        ):
            raise ValueError("benchmark_action_unavailable_at_effective_open")
        if isinstance(action, CashDividendAction) and action.currency != "USD":
            raise ValueError("unsupported_benchmark_dividend_currency")
    # Past ex-dates have no entitlement: this portfolio begins at the selected open.
    actions = tuple(
        a for a in ordered
        if a.security_id == security_id and selected[0] <= a.ex_date <= selected[-1]
    )
    return sessions, lookup, actions


def evaluate_historical_benchmark(
    snapshot: HistoricalBenchmarkSnapshot,
    security_id: str,
    initial_cash: Decimal,
    *,
    convention: ReturnConvention,
    dates: tuple[date, ...] | None = None,
) -> HistoricalBenchmarkResult:
    """Evaluate one explicit raw-price return convention without network or trading I/O.

    Realized opens/closes determine analytical fills and marks; row acquisition time
    is not used to pretend an EOD bar was known at its open. There are no decisions
    based on same-session OHLC, and reinvestment uses only already payable cash.
    Selected dates must form one complete contiguous slice of the explicit calendar.
    """
    if convention not in ("price_return", "total_return_cash", "total_return_reinvest"):
        raise ValueError("unsupported_benchmark_return_convention")
    if not isinstance(initial_cash, Decimal) or not initial_cash.is_finite() or initial_cash <= 0:
        raise ValueError("invalid_benchmark_initial_cash")
    sessions, bars, actions = _validate(snapshot, security_id, dates)
    quantity = Fraction(0)
    cash = Fraction(initial_cash)
    cost = Fraction(0)
    receivables: dict[str, tuple[date, Fraction]] = {}
    points = []
    terminal = Fraction(initial_cash)
    for index, session in enumerate(sessions):
        bar = bars[session.date]
        for action in (a for a in actions if a.ex_date == session.date):
            if isinstance(action, SplitAction):
                quantity *= Fraction(action.numerator, action.denominator)
            elif convention != "price_return":
                receivables[action.action_id] = (
                    action.pay_date, quantity * Fraction(action.cash_per_share)
                )
        for action_id, (pay_date, amount) in tuple(receivables.items()):
            if pay_date <= session.date:
                cash += amount
                del receivables[action_id]
        reinvested = Fraction(0)
        if index == 0 or (convention == "total_return_reinvest" and cash):
            if index:
                reinvested = cash
            quantity += cash / Fraction(bar.open)
            cost += cash
            cash = Fraction(0)
        receivable = sum((amount for _, amount in receivables.values()), Fraction(0))
        market_value = quantity * Fraction(bar.close)
        terminal = cash + receivable + market_value
        reported_cash, reported_receivable, reported_value = map(
            _decimal, (cash, receivable, market_value)
        )
        with localcontext(Context(prec=BENCHMARK_DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)):
            reported_equity = reported_cash + reported_receivable + reported_value
        points.append(HistoricalBenchmarkPoint(
            session.date, bar.symbol, _decimal(quantity), _decimal(cost), reported_cash,
            reported_receivable, reported_value, reported_equity, _decimal(reinvested),
            _rational(quantity), _rational(terminal),
        ))
    total_return = terminal / Fraction(initial_cash) - 1
    return HistoricalBenchmarkResult(
        security_id, snapshot.manifest_sha256, initial_cash,
        HistoricalBenchmarkConventions(
            convention,
            dividend_recognition=(
                "ignored_for_price_return" if convention == "price_return"
                else "ex_date_prior_close_post_split_units"
            ),
            dividend_payment=(
                "ignored_for_price_return" if convention == "price_return"
                else "first_session_open_on_or_after_payment_date"
            ),
            dividend_reinvestment=(
                "payment_open_cash_availability_assumed"
                if convention == "total_return_reinvest" else "none"
            ),
        ), tuple(points), _decimal(total_return),
        _rational(total_return),
    )

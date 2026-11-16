"""Pure Decimal accounting for action-aware offline simulations.

Call once before each session's opening orders, with the previous close's holdings.
Splits adjust quantities and per-share order/stop prices while retaining total cost
basis. Dividends create an ex-date receivable and credit cash on the first processed
session on/after payment. Receivables must be included separately in portfolio equity.
There is no reinvestment, withholding, foreign exchange or cash-in-lieu convention.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import (
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DecimalException,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    localcontext,
)
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from packages.data.corporate_actions import (
    CashDividendAction,
    CorporateAction,
    CorporateActionModel,
    ExactDecimal,
    SplitAction,
    corporate_action_fingerprint,
    validate_actions,
)

FractionalPolicy = Literal["reject", "exact"]
ACCOUNTING_DECIMAL_PRECISION = 50
_MARKET_TIMEZONE = ZoneInfo("America/New_York")
_ACCOUNTING_CONTEXT = Context(
    prec=ACCOUNTING_DECIMAL_PRECISION,
    rounding=ROUND_HALF_EVEN,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    traps=[InvalidOperation, DivisionByZero, Overflow, Inexact],
)


class AccountingPosition(CorporateActionModel):
    security_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]*$")
    quantity: ExactDecimal = Field(ge=0)
    cost_basis: ExactDecimal = Field(ge=0)
    stop_price: ExactDecimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def empty_position_has_no_cost(self) -> Self:
        if self.quantity == 0 and self.cost_basis != 0:
            raise ValueError("zero_position_has_cost_basis")
        return self


class PendingOrder(CorporateActionModel):
    order_id: str = Field(min_length=1)
    security_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]*$")
    quantity: ExactDecimal = Field(ge=0)
    limit_price: ExactDecimal | None = Field(default=None, gt=0)
    stop_price: ExactDecimal | None = Field(default=None, gt=0)


class AppliedAction(CorporateActionModel):
    action_id: str = Field(min_length=1)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class DividendEntitlement(CorporateActionModel):
    action_id: str = Field(min_length=1)
    security_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]*$")
    ex_date: date
    pay_date: date
    quantity: ExactDecimal = Field(ge=0)
    cash_amount: ExactDecimal = Field(ge=0)
    paid: bool = False

    @model_validator(mode="after")
    def valid_payment_date(self) -> Self:
        if self.pay_date < self.ex_date:
            raise ValueError("dividend_payment_precedes_ex_date")
        return self


class PortfolioActionState(CorporateActionModel):
    cash: ExactDecimal = Field(ge=0)
    positions: tuple[AccountingPosition, ...] = ()
    pending_orders: tuple[PendingOrder, ...] = ()
    entitlements: tuple[DividendEntitlement, ...] = ()
    applied_actions: tuple[AppliedAction, ...] = ()
    last_session: date | None = None

    @model_validator(mode="after")
    def unique_ledger_keys(self) -> Self:
        keys = (
            ("position", [p.security_id for p in self.positions]),
            ("position_symbol", [p.symbol for p in self.positions]),
            ("order", [o.order_id for o in self.pending_orders]),
            ("entitlement", [e.action_id for e in self.entitlements]),
            ("applied_action", [a.action_id for a in self.applied_actions]),
        )
        for name, identifiers in keys:
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"duplicate_{name}")
        applied = {a.action_id for a in self.applied_actions}
        if any(e.action_id not in applied for e in self.entitlements):
            raise ValueError("entitlement_without_applied_action")
        return self


def _quantity(value: Decimal, action: SplitAction, policy: FractionalPolicy) -> Decimal:
    quantity = value * action.numerator / action.denominator
    if policy == "reject" and quantity != quantity.to_integral_value():
        raise ValueError(f"fractional_quantity:{action.action_id}")
    return quantity


def _price(value: Decimal | None, action: SplitAction) -> Decimal | None:
    return None if value is None else value * action.denominator / action.numerator


def apply_session_actions(
    state: PortfolioActionState,
    actions: Sequence[CorporateAction],
    *,
    session: date,
    as_of: datetime,
    fractional_policy: FractionalPolicy = "reject",
) -> PortfolioActionState:
    """Advance the pre-open action ledger without mutating the supplied state.

    An unavailable action due now, skipped unapplied ex-date, revised applied action
    or backwards transition fails explicitly. Replaying a completed session with
    identical action IDs is a no-op. Actions before the initial portfolio start
    must be excluded by the caller or processed with empty initial holdings.

    The fixed 50-significant-digit Decimal context traps inexact arithmetic: the
    exact-fractional policy never silently rounds a nonterminating decimal ratio.
    The supplied inventory must retain all actions previously applied to this
    portfolio. Restored entitlements are checked against those records before
    payment. The caller owns inventory completeness and the exact calendar open;
    this function also requires the cutoff to fall on the session's New York date.
    """
    if fractional_policy not in ("reject", "exact"):
        raise ValueError("unsupported_fractional_policy:cash_in_lieu_not_implemented")
    if as_of.utcoffset() is None:
        raise ValueError("action_cutoff_requires_offset")
    if as_of.astimezone(_MARKET_TIMEZONE).date() != session:
        raise ValueError("cutoff_session_mismatch")
    if state.last_session is not None and session < state.last_session:
        raise ValueError("backwards_session")
    ordered = validate_actions(actions)
    try:
        with localcontext(_ACCOUNTING_CONTEXT):
            _validate_restored_state(state, ordered)
            applied = {a.action_id: a for a in state.applied_actions}
            due: list[CorporateAction] = []
            for action in ordered:
                if action.action_id in applied:
                    continue
                if action.ex_date < session:
                    raise ValueError(f"missed_ex_date:{action.action_id}")
                if action.ex_date > session:
                    continue
                if state.last_session == session:
                    raise ValueError(f"session_already_processed:{action.action_id}")
                if action.available_at > as_of:
                    raise ValueError(f"action_unavailable:{action.action_id}")
                due.append(action)
            return _apply(state, due, applied, session, fractional_policy)
    except DecimalException as exc:
        raise ValueError("inexact_decimal_accounting") from exc


def _validate_restored_state(
    state: PortfolioActionState, actions: Sequence[CorporateAction]
) -> None:
    """Bind an exported ledger to the complete retained action inventory."""
    inventory = {a.action_id: a for a in actions}
    applied = {a.action_id: a for a in state.applied_actions}
    entitlements = {e.action_id: e for e in state.entitlements}
    if state.last_session is None and (applied or entitlements):
        raise ValueError("restored_state_timeline:missing_last_session")
    if any(action_id not in applied for action_id in entitlements):
        raise ValueError("orphan_entitlement")
    for record in state.applied_actions:
        action = inventory.get(record.action_id)
        if action is None:
            raise ValueError(f"missing_applied_action:{record.action_id}")
        if record.fingerprint != corporate_action_fingerprint(action):
            raise ValueError(f"applied_action_changed:{record.action_id}")
        if state.last_session is None or action.ex_date > state.last_session:
            raise ValueError(f"restored_state_timeline:{record.action_id}")
        if isinstance(action, CashDividendAction) and action.action_id not in entitlements:
            raise ValueError(f"missing_dividend_entitlement:{action.action_id}")
    for entitlement in state.entitlements:
        action = inventory[entitlement.action_id]
        if not isinstance(action, CashDividendAction):
            raise ValueError(f"non_dividend_entitlement:{entitlement.action_id}")
        if (
            entitlement.security_id != action.security_id
            or entitlement.symbol != action.symbol
            or entitlement.ex_date != action.ex_date
            or entitlement.pay_date != action.pay_date
            or entitlement.cash_amount != entitlement.quantity * action.cash_per_share
            or state.last_session is None
            or entitlement.paid != (entitlement.pay_date <= state.last_session)
        ):
            raise ValueError(f"invalid_entitlement:{entitlement.action_id}")


def _apply(
    state: PortfolioActionState,
    due: Sequence[CorporateAction],
    applied: dict[str, AppliedAction],
    session: date,
    fractional_policy: FractionalPolicy,
) -> PortfolioActionState:
    positions = {p.security_id: p for p in state.positions}
    orders = {o.order_id: o for o in state.pending_orders}
    entitlements = {e.action_id: e for e in state.entitlements}
    cash = state.cash
    for action in due:
        position = positions.get(action.security_id)
        matching_orders = tuple(o for o in orders.values() if o.security_id == action.security_id)
        identity_records: tuple[AccountingPosition | PendingOrder, ...] = (
            *positions.values(),
            *orders.values(),
        )
        if any(
            (record.security_id == action.security_id) != (record.symbol == action.symbol)
            for record in identity_records
        ):
            raise ValueError(f"security_symbol_mismatch:{action.security_id}")
        if isinstance(action, SplitAction):
            if position is not None:
                positions[action.security_id] = position.model_copy(
                    update={
                        "quantity": _quantity(position.quantity, action, fractional_policy),
                        "stop_price": _price(position.stop_price, action),
                    }
                )
            for order in matching_orders:
                orders[order.order_id] = order.model_copy(
                    update={
                        "quantity": _quantity(order.quantity, action, fractional_policy),
                        "limit_price": _price(order.limit_price, action),
                        "stop_price": _price(order.stop_price, action),
                    }
                )
        else:
            quantity = position.quantity if position is not None else Decimal(0)
            entitlements[action.action_id] = DividendEntitlement(
                action_id=action.action_id,
                security_id=action.security_id,
                symbol=action.symbol,
                ex_date=action.ex_date,
                pay_date=action.pay_date,
                quantity=quantity,
                cash_amount=quantity * action.cash_per_share,
            )
        applied[action.action_id] = AppliedAction(
            action_id=action.action_id, fingerprint=corporate_action_fingerprint(action)
        )
    for action_id, entitlement in sorted(entitlements.items()):
        if not entitlement.paid and entitlement.pay_date <= session:
            cash += entitlement.cash_amount
            entitlements[action_id] = entitlement.model_copy(update={"paid": True})
    return PortfolioActionState(
        cash=cash,
        positions=tuple(sorted(positions.values(), key=lambda p: (p.security_id, p.symbol))),
        pending_orders=tuple(sorted(orders.values(), key=lambda o: o.order_id)),
        entitlements=tuple(sorted(entitlements.values(), key=lambda e: (e.ex_date, e.action_id))),
        applied_actions=tuple(sorted(applied.values(), key=lambda a: a.action_id)),
        last_session=session,
    )

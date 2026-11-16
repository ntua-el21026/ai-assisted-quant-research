"""Validated corporate-action records for the isolated action-aware research path.

An availability timestamp is accompanied by its evidence basis. A provider's
process/ex date alone does not establish historically observed availability.
Cash dividends use post-split shares when both actions have the same ex-date.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

AvailabilityBasis = Literal["observed", "synthetic", "assumed"]


def _exact_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | str | int):
        raise ValueError("decimal_requires_exact_string_integer_or_decimal")
    try:
        number = Decimal(value)
    except ArithmeticError as exc:
        raise ValueError("invalid_decimal") from exc
    if not number.is_finite():
        raise ValueError("nonfinite_decimal")
    return number


ExactDecimal = Annotated[Decimal, BeforeValidator(_exact_decimal)]


class CorporateActionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class _Action(CorporateActionModel):
    action_id: str = Field(min_length=1)
    security_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]*$")
    ex_date: date
    available_at: datetime
    availability_basis: AvailabilityBasis
    declared_at: datetime | None = None

    @field_validator("action_id", "security_id")
    @classmethod
    def nonblank_identifier(cls, value: str) -> str:
        if value != value.strip() or not value.strip():
            raise ValueError("invalid_action_identifier")
        return value

    @field_validator("available_at", "declared_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("action_timestamp_requires_offset")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def declaration_precedes_availability(self) -> Self:
        if self.declared_at is not None and self.declared_at > self.available_at:
            raise ValueError("availability_precedes_declaration")
        return self


class SplitAction(_Action):
    kind: Literal["split"] = "split"
    numerator: int = Field(gt=0, strict=True)
    denominator: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def effective_ratio(self) -> Self:
        if self.numerator == self.denominator:
            raise ValueError("split_ratio_has_no_effect")
        return self


class CashDividendAction(_Action):
    kind: Literal["cash_dividend"] = "cash_dividend"
    pay_date: date
    cash_per_share: ExactDecimal = Field(gt=0)
    currency: Literal["USD"] = "USD"
    share_basis: Literal["post_split"] = "post_split"

    @model_validator(mode="after")
    def payment_after_entitlement(self) -> Self:
        if self.pay_date < self.ex_date:
            raise ValueError("dividend_payment_precedes_ex_date")
        return self


CorporateAction = Annotated[SplitAction | CashDividendAction, Field(discriminator="kind")]


def validate_actions(actions: Sequence[CorporateAction]) -> tuple[CorporateAction, ...]:
    """Reject duplicated or contradictory evidence and return the execution order.

    This version supports one split and one cash distribution per security/ex-date.
    Multiple same-kind distributions require explicit source reconciliation before
    import rather than allowing aliases to create duplicate cash credits.
    """
    seen_ids: set[str] = set()
    seen_effective: set[tuple[str, str, date]] = set()
    for action in actions:
        if not isinstance(action, SplitAction | CashDividendAction):
            raise ValueError("unsupported_corporate_action")
        if action.action_id in seen_ids:
            raise ValueError(f"duplicate_action_id:{action.action_id}")
        key = (action.kind, action.security_id, action.ex_date)
        if key in seen_effective:
            raise ValueError(f"conflicting_action_records:{action.security_id}:{action.ex_date}")
        seen_ids.add(action.action_id)
        seen_effective.add(key)
    return tuple(
        sorted(
            actions,
            key=lambda action: (
                action.ex_date,
                0 if action.kind == "split" else 1,
                action.security_id,
                action.action_id,
            ),
        )
    )


def corporate_action_fingerprint(action: CorporateAction) -> str:
    """Hash semantic action contents; decimal trailing zeros are insignificant."""
    payload = action.model_dump(mode="json")
    if isinstance(action, CashDividendAction):
        parts = action.cash_per_share.as_tuple()
        if not isinstance(parts.exponent, int):
            raise ValueError("nonfinite_decimal")
        digits = "".join(str(digit) for digit in parts.digits)
        coefficient = digits.rstrip("0")
        payload["cash_per_share"] = {
            "sign": parts.sign,
            "coefficient": coefficient,
            "exponent": parts.exponent + len(digits) - len(coefficient),
        }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

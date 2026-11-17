"""Explicit action applicability without rewriting source acquisition evidence.

Process dates establish query membership, not economic applicability. Prior cash
entitlements can be absent under a declared fresh flat opening contract even when
payment is later. Unknown opening ownership, adjusted dependencies and structural
events remain unresolved. No completeness or announcement-availability claim is made.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from fractions import Fraction
from typing import Literal, Self

from pydantic import Field, model_validator

from packages.data.alpaca_historical import (
    AcquiredPage,
    CorporateActionsRequest,
    HistoricalAcquisition,
    HistoricalAcquisitionError,
    decode_historical_page,
    historical_query,
    normalize_corporate_actions,
)
from packages.data.corporate_actions import CorporateAction, CorporateActionModel
from packages.data.historical_models import SHA_PATTERN, HistoricalModel
from packages.research.artifacts import canonical_json

Status = Literal["PASS", "RESTRICTED", "FAIL"]
Scope = Literal["applicable", "outside", "unverified"]
Support = Literal["supported", "unsupported", "unverified"]
_CASH = "cash_dividends"
_SPLITS = {"forward_splits", "reverse_splits"}


class ActionScopeContext(HistoricalModel):
    start: date
    end: date
    feature_history_start: date
    opening_state: Literal["flat_cash", "carry_in", "unknown"] = "unknown"
    raw_execution: bool = Field(default=False, strict=True)
    feature_basis: Literal["raw", "causal_split_asof", "provider_adjusted", "unknown"] = "unknown"
    opening_positions_empty: bool = Field(default=False, strict=True)
    opening_orders_empty: bool = Field(default=False, strict=True)
    opening_receivables_empty: bool = Field(default=False, strict=True)
    opening_balances_independent: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def valid_interval(self) -> Self:
        if not self.feature_history_start <= self.start <= self.end:
            raise ValueError("invalid_action_scope_interval")
        return self


class ScopedActionRecord(CorporateActionModel):
    category: str
    source_page_index: int = Field(ge=0)
    source_row_index: int = Field(ge=0)
    source_page_sha256: str = Field(pattern=SHA_PATTERN)
    record_sha256: str = Field(pattern=SHA_PATTERN)
    source_id: str | None
    symbol: str | None
    ex_date: date | None
    pay_date: date | None
    process_date: date | None
    foreign: bool | None
    special: bool | None
    currency: str | None
    scope: Scope
    support: Support
    reason: str = Field(pattern=r"^[a-z_]+$")


class ActionScopeFinding(HistoricalModel):
    code: str = Field(pattern=r"^[a-z_]+$")
    status: Status
    count: int = Field(ge=1)


class ActionScopeReport(HistoricalModel):
    schema_version: Literal["action-scope/v1"] = "action-scope/v1"
    context: ActionScopeContext
    context_sha256: str = Field(pattern=SHA_PATTERN)
    source_acquisition_sha256: str = Field(pattern=SHA_PATTERN)
    source_page_sha256: tuple[str, ...]
    records: tuple[ScopedActionRecord, ...]
    applicable_count: int = Field(ge=0)
    outside_count: int = Field(ge=0)
    unverified_count: int = Field(ge=0)
    findings: tuple[ActionScopeFinding, ...]
    blocked: bool
    status: Status
    inventory_completeness_established: Literal[False] = False
    announcement_availability_established: Literal[False] = False


def _hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _typed_json(value: object) -> object:
    """Type-tag private record identity so exact decimals and strings cannot collide."""
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["boolean", value]
    if isinstance(value, int):
        return ["integer", str(value)]
    if isinstance(value, Decimal):
        return ["decimal", str(value)]
    if isinstance(value, float):
        # The source decoder can retain invalid JSON constants as floats. Hash
        # their typed representation while row validation rejects their economics.
        return ["invalid_source_float", repr(value)]
    if isinstance(value, str):
        return ["string", value]
    if isinstance(value, list):
        return ["array", [_typed_json(item) for item in value]]
    if isinstance(value, dict):
        return ["object", [[key, _typed_json(item)] for key, item in sorted(value.items())]]
    raise ValueError("invalid_source_json_value")


def _source_hash(acquisition: HistoricalAcquisition) -> str:
    return _hash(
        {
            "request": acquisition.request.model_dump(mode="json"),
            "request_started_at": acquisition.request_started_at.isoformat(),
            "acquired_at": acquisition.acquired_at.isoformat(),
            "pages": [
                {
                    "endpoint": page.endpoint,
                    "query": page.query,
                    "received_at": page.received_at.isoformat(),
                    "sha256": page.sha256,
                }
                for page in acquisition.pages
            ],
        }
    )


def _date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
        return parsed if parsed.isoformat() == value else None
    except ValueError:
        return None


def _rate(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise ValueError
    if len(str(value)) > 64:
        raise ValueError
    number = Decimal(value)
    if (
        not number.is_finite()
        or len(number.as_tuple().digits) > 32
        or not Decimal("1e-9") <= number <= Decimal("1e9")
    ):
        raise ValueError
    return number


def _raw_only(context: ActionScopeContext) -> bool:
    return context.raw_execution and context.feature_basis == "raw"


def _fresh_flat(context: ActionScopeContext) -> bool:
    return (
        context.opening_state == "flat_cash"
        and context.opening_positions_empty
        and context.opening_orders_empty
        and context.opening_receivables_empty
        and context.opening_balances_independent
        and _raw_only(context)
    )


def _record(
    category: str,
    row: object,
    page_index: int,
    row_index: int,
    page_sha: str,
    request: CorporateActionsRequest,
    context: ActionScopeContext,
) -> ScopedActionRecord:
    raw = row if isinstance(row, dict) else {}
    symbol = raw.get("symbol")
    source_id = raw.get("id")
    ex_date, pay_date, process_date = (
        _date(raw.get(name)) for name in ("ex_date", "payable_date", "process_date")
    )
    foreign = raw.get("foreign") if isinstance(raw.get("foreign"), bool) else None
    special = raw.get("special") if isinstance(raw.get("special"), bool) else None
    currency = raw.get("currency") if isinstance(raw.get("currency"), str) else None
    fields = dict(
        category=category,
        source_page_index=page_index,
        source_row_index=row_index,
        source_page_sha256=page_sha,
        record_sha256=_hash(_typed_json(row)),
        source_id=source_id if isinstance(source_id, str) else None,
        symbol=symbol if isinstance(symbol, str) else None,
        ex_date=ex_date,
        pay_date=pay_date,
        process_date=process_date,
        foreign=foreign,
        special=special,
        currency=currency,
    )
    scope: Scope = "unverified"
    support: Support = "unverified"
    reason = "invalid_source_record"
    if not isinstance(row, dict):
        return ScopedActionRecord.model_validate(
            {**fields, "scope": scope, "support": support, "reason": reason}
        )
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or source_id != source_id.strip()
        or symbol not in request.symbols
        or ex_date is None
        or process_date is None
        or not request.start <= process_date <= request.end
    ):
        return ScopedActionRecord.model_validate(
            {
                **fields,
                "scope": scope,
                "support": support,
                "reason": "invalid_action_identity_or_dates",
            }
        )
    if category == _CASH:
        try:
            _rate(raw.get("rate"))
            if pay_date is None or pay_date < ex_date or foreign is None or special is None:
                raise ValueError
            if raw.get("currency") is not None and (
                currency is None or not currency.strip() or currency != currency.strip()
            ):
                raise ValueError
        except (ValueError, ArithmeticError):
            return ScopedActionRecord.model_validate(
                {**fields, "scope": scope, "support": support, "reason": "invalid_cash_record"}
            )
        support = (
            "unsupported"
            if foreign or special or currency not in {None, "USD"}
            else "unverified"
            if currency is None
            else "supported"
        )
        if context.start <= ex_date <= context.end:
            scope, reason = "applicable", "cash_effective_in_analysis_window"
        elif ex_date < context.feature_history_start and _fresh_flat(context):
            scope, reason = "outside", "prior_ex_date_no_opening_entitlement"
        elif ex_date > context.end and _raw_only(context):
            scope, reason = "outside", "future_cash_no_raw_input_effect"
        else:
            reason = "cash_scope_dependencies_unverified"
    elif category in _SPLITS:
        try:
            ratio = Fraction(_rate(raw.get("new_rate"))) / Fraction(_rate(raw.get("old_rate")))
            if (
                max(ratio.numerator, ratio.denominator) > 1_000_000_000
                or (category == "forward_splits" and ratio <= 1)
                or (category == "reverse_splits" and ratio >= 1)
            ):
                raise ValueError
        except (ValueError, ArithmeticError):
            return ScopedActionRecord.model_validate(
                {**fields, "scope": scope, "support": support, "reason": "invalid_split_ratio"}
            )
        support = "supported"
        if context.start <= ex_date <= context.end:
            scope, reason = "applicable", "split_effective_in_analysis_window"
        else:
            reason = "split_scope_dependencies_unverified"
    else:
        support, reason = "unsupported", "structural_action_requires_resolution"
    return ScopedActionRecord.model_validate(
        {**fields, "scope": scope, "support": support, "reason": reason}
    )


def classify_action_scope(
    acquisition: HistoricalAcquisition,
    context: ActionScopeContext,
) -> ActionScopeReport:
    """Retain every parsed source row; distinguish query membership from applicability.

    Source symbols are query-scoped references. Stable identity qualification remains
    independent and is required before normalization or downstream economic use.
    """
    records: list[ScopedActionRecord] = []
    issues: Counter[tuple[str, Status]] = Counter()
    request = acquisition.request
    if not isinstance(request, CorporateActionsRequest):
        issues[("invalid_action_request", "FAIL")] += 1
    else:
        endpoint, expected = historical_query(request)
        token: str | None = None
        seen_tokens: set[str] = set()
        previous = acquisition.request_started_at
        if (
            not acquisition.pages
            or len(acquisition.pages) > request.max_pages
            or previous.utcoffset() is None
            or acquisition.acquired_at.utcoffset() is None
            or acquisition.acquired_at < previous
        ):
            issues[("invalid_source_acquisition", "FAIL")] += 1
        if request.types != "all":
            issues[("source_action_inventory_filtered", "RESTRICTED")] += 1
        terminal_seen = False
        for page_index, page in enumerate(acquisition.pages):
            query = dict(expected)
            if token is not None:
                query["page_token"] = token
            if (
                terminal_seen
                or len(dict(page.query)) != len(page.query)
                or dict(page.query) != query
                or page.endpoint != endpoint
            ):
                issues[("invalid_source_query_chain", "FAIL")] += 1
            if (
                page.received_at.utcoffset() is None
                or previous.utcoffset() is None
                or acquisition.acquired_at.utcoffset() is None
            ):
                issues[("invalid_source_acquisition_time", "FAIL")] += 1
            elif not previous <= page.received_at <= acquisition.acquired_at:
                issues[("invalid_source_acquisition_time", "FAIL")] += 1
            previous = page.received_at
            try:
                payload = decode_historical_page(page.body)
                inventory = payload.get("corporate_actions")
                if not isinstance(inventory, dict):
                    raise ValueError
                for category, rows in inventory.items():
                    if not isinstance(rows, list):
                        issues[("invalid_source_category_container", "FAIL")] += 1
                        continue
                    for row_index, row in enumerate(rows):
                        records.append(
                            _record(
                                category, row, page_index, row_index, page.sha256, request, context
                            )
                        )
                if "next_page_token" not in payload:
                    raise ValueError
                next_token = payload["next_page_token"]
                if next_token is not None and (
                    not isinstance(next_token, str)
                    or not next_token
                    or len(next_token) > 4096
                    or next_token in seen_tokens
                ):
                    raise ValueError
                token = next_token
                if token is not None:
                    seen_tokens.add(token)
                terminal_seen = token is None
            except (HistoricalAcquisitionError, ValueError, UnicodeError, RecursionError):
                issues[("invalid_source_page", "FAIL")] += 1
        if token is not None or previous != acquisition.acquired_at:
            issues[("invalid_source_completion", "FAIL")] += 1
    ids: dict[str, list[int]] = defaultdict(list)
    effects: dict[tuple[str, str, date], list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if record.source_id is not None:
            ids[record.source_id].append(index)
        if record.symbol is not None and record.ex_date is not None:
            kind = "split" if record.category in _SPLITS else record.category
            effects[(kind, record.symbol, record.ex_date)].append(index)
    for groups, reason in (
        (ids.values(), "duplicate_source_action_id"),
        (effects.values(), "conflicting_effective_action"),
    ):
        for group in groups:
            if len(group) > 1:
                for index in group:
                    records[index] = records[index].model_copy(
                        update={"scope": "unverified", "support": "unverified", "reason": reason}
                    )
    for record in records:
        if record.scope == "applicable" and record.category == _CASH and record.currency is None:
            issues[("applicable_cash_currency_unverified", "RESTRICTED")] += 1
        status: Status = (
            "FAIL"
            if record.reason.startswith(("invalid_", "duplicate_", "conflicting_"))
            or (record.scope == "applicable" and record.support == "unsupported")
            else "RESTRICTED"
            if record.scope == "unverified"
            or (record.scope == "applicable" and record.support == "unverified")
            else "PASS"
        )
        issues[(record.reason, status)] += 1
    if not context.raw_execution:
        issues[("raw_execution_not_established", "RESTRICTED")] += 1
    if context.feature_basis in {"provider_adjusted", "unknown"}:
        issues[("feature_adjustment_dependencies_unverified", "RESTRICTED")] += 1
    status = max(
        (status for code, status in issues),
        key={"PASS": 0, "RESTRICTED": 1, "FAIL": 2}.__getitem__,
        default="PASS",
    )
    ordered = tuple(
        sorted(
            records,
            key=lambda row: (
                row.category,
                row.ex_date or date.min,
                row.symbol or "",
                row.record_sha256,
                row.source_page_sha256,
                row.source_page_index,
                row.source_row_index,
            ),
        )
    )
    return ActionScopeReport(
        context=context,
        context_sha256=_hash(context.model_dump(mode="json")),
        source_acquisition_sha256=_source_hash(acquisition),
        source_page_sha256=tuple(page.sha256 for page in acquisition.pages),
        records=ordered,
        applicable_count=sum(row.scope == "applicable" for row in records),
        outside_count=sum(row.scope == "outside" for row in records),
        unverified_count=sum(row.scope == "unverified" for row in records),
        findings=tuple(
            ActionScopeFinding(code=code, status=value, count=count)
            for (code, value), count in sorted(issues.items())
        ),
        blocked=status != "PASS",
        status=status,
    )


def _wire_json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _wire_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_wire_json(item) for item in value]
    return value


def normalize_applicable_actions(
    acquisition: HistoricalAcquisition,
    report: ActionScopeReport,
    *,
    security_ids: Mapping[str, str],
) -> tuple[CorporateAction, ...]:
    """Normalize a derived selected view internally; never return a provider receipt.

    The original acquisition remains the sole source for provider provenance. The
    temporary filtered body is derived data and must never be represented as wire
    evidence. Excluded special records are retained in the report, never relabeled.
    """
    if report != classify_action_scope(acquisition, report.context):
        raise ValueError("scope_report_mismatch")
    if report.blocked:
        raise ValueError("action_scope_blocked")
    selected: dict[str, list[object]] = defaultdict(list)
    for record in report.records:
        if record.scope == "applicable":
            payload = decode_historical_page(acquisition.pages[record.source_page_index].body)
            inventory = payload["corporate_actions"]
            assert isinstance(inventory, dict)
            rows = inventory[record.category]
            assert isinstance(rows, list)
            selected[record.category].append(rows[record.source_row_index])
    if not selected:
        return ()
    endpoint, query = historical_query(acquisition.request)
    derived_body = canonical_json(
        _wire_json(
            {
                "corporate_actions": dict(selected),
                "next_page_token": None,
            }
        )
    )
    derived = HistoricalAcquisition(
        acquisition.request,
        acquisition.request_started_at,
        acquisition.acquired_at,
        (
            AcquiredPage(
                endpoint, tuple(sorted(query.items())), derived_body, acquisition.acquired_at
            ),
        ),
    )
    return normalize_corporate_actions(derived, security_ids=security_ids)


def private_report_bytes(report: ActionScopeReport) -> bytes:
    return canonical_json(report.model_dump(mode="json"))


def public_scope_report_bytes(report: ActionScopeReport) -> bytes:
    """Publish only aggregate classification, closed codes and source/policy hashes."""
    return canonical_json(
        {
            "schema_version": "action-scope-summary/v1",
            "context_sha256": report.context_sha256,
            "source_acquisition_sha256": report.source_acquisition_sha256,
            "source_page_sha256": report.source_page_sha256,
            "record_count": len(report.records),
            "applicable_count": report.applicable_count,
            "outside_count": report.outside_count,
            "unverified_count": report.unverified_count,
            "blocked": report.blocked,
            "status": report.status,
            "inventory_completeness_established": False,
            "announcement_availability_established": False,
            "findings": [finding.model_dump(mode="json") for finding in report.findings],
        }
    )

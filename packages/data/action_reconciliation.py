"""Exact reconciliation against caller-normalized independent action evidence.

The caller owns source rights, stable security identity, source interpretation and
the explicit inventory-completeness attestation. Dates do not establish historical
announcement availability. Source references and economic values remain private;
reports contain aggregate counts, closed codes and immutable input fingerprints.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import date
from fractions import Fraction
from typing import Literal

from pydantic import Field

from packages.data.corporate_actions import (
    CashDividendAction,
    CorporateAction,
    ExactDecimal,
    SplitAction,
)
from packages.data.historical_models import SHA_PATTERN, HistoricalModel
from packages.research.artifacts import canonical_json

Status = Literal["PASS", "RESTRICTED", "FAIL"]
Key = tuple[str, str, date]


class IndependentActionRecord(HistoricalModel):
    """One independently interpreted record; unknown economic fields stay None.

    Multiple components on one identity/kind/ex-date remain separate records. This
    module neither aggregates distributions nor chooses between source revisions.
    """

    kind: Literal["split", "cash_dividend", "unsupported"]
    security_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]*$")
    ex_date: date
    pay_date: date | None = None
    amount: ExactDecimal | None = None
    currency: str | None = Field(default=None, min_length=1)
    numerator: int | None = Field(default=None, strict=True)
    denominator: int | None = Field(default=None, strict=True)
    source_reference: str = Field(min_length=1)
    source_sha256: str = Field(pattern=SHA_PATTERN)


class ReconciliationFinding(HistoricalModel):
    code: str = Field(pattern=r"^[a-z_]+$")
    status: Status
    count: int = Field(ge=1)


class ActionReconciliationReport(HistoricalModel):
    schema_version: Literal["action-reconciliation/v1"] = "action-reconciliation/v1"
    start: date
    end: date
    complete_independent_inventory: bool
    provider_count: int = Field(ge=0)
    independent_count: int = Field(ge=0)
    outside_provider_count: int = Field(ge=0)
    outside_independent_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    missing_provider_count: int = Field(ge=0)
    missing_independent_count: int = Field(ge=0)
    mismatched_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    unsupported_count: int = Field(ge=0)
    provider_input_sha256: str = Field(pattern=SHA_PATTERN)
    independent_input_sha256: str = Field(pattern=SHA_PATTERN)
    independent_source_sha256: tuple[str, ...]
    reconciliation_id: str = Field(pattern=SHA_PATTERN)
    announcement_availability_established: Literal[False] = False
    findings: tuple[ReconciliationFinding, ...]
    status: Status


def _fingerprint(records: list[dict[str, object]]) -> str:
    ordered = sorted(records, key=canonical_json)
    return hashlib.sha256(canonical_json(ordered)).hexdigest()


def _independent_issue(record: IndependentActionRecord) -> tuple[str, Status] | None:
    if record.kind == "unsupported":
        return "independent_unsupported_action", "RESTRICTED"
    if record.kind == "split":
        if any(value is not None for value in (record.amount, record.pay_date, record.currency)):
            return "independent_split_incompatible_fields", "FAIL"
        if any(
            value is not None and value <= 0 for value in (record.numerator, record.denominator)
        ):
            return "independent_split_invalid", "FAIL"
        if record.numerator is None or record.denominator is None:
            return "independent_split_fields_missing", "RESTRICTED"
        if record.numerator == record.denominator:
            return "independent_split_invalid", "FAIL"
    else:
        if record.numerator is not None or record.denominator is not None:
            return "independent_dividend_incompatible_fields", "FAIL"
        if record.amount is not None and record.amount <= 0:
            return "independent_dividend_amount_invalid", "FAIL"
        if record.pay_date is not None and record.pay_date < record.ex_date:
            return "independent_dividend_payment_invalid", "FAIL"
        if record.amount is None or record.pay_date is None or record.currency is None:
            return "independent_dividend_fields_missing", "RESTRICTED"
    return None


def _equal(provider: CorporateAction, other: IndependentActionRecord) -> bool:
    if isinstance(provider, SplitAction):
        assert other.numerator is not None and other.denominator is not None
        return Fraction(provider.numerator, provider.denominator) == Fraction(
            other.numerator, other.denominator
        )
    return (
        provider.cash_per_share == other.amount
        and provider.pay_date == other.pay_date
        and provider.currency == other.currency
    )


def reconcile_actions(
    provider_actions: Sequence[CorporateAction],
    independent: Sequence[IndependentActionRecord],
    *,
    start: date,
    end: date,
    complete_independent_inventory: bool = False,
) -> ActionReconciliationReport:
    """Compare unambiguous supported records inside the inclusive ex-date window.

    Counts for matching, missing, mismatched and ambiguous records use semantic
    groups (stable security ID, action kind, ex-date). Total/outside/unsupported
    counts use individual records. Conflicting components are never summed or
    selected. Completeness is a caller attestation, not inferred from matching.
    """
    if start > end:
        raise ValueError("invalid_reconciliation_interval")
    if any(not isinstance(action, SplitAction | CashDividendAction) for action in provider_actions):
        raise ValueError("unsupported_provider_action")
    providers: dict[Key, list[CorporateAction]] = defaultdict(list)
    others: dict[Key, list[IndependentActionRecord]] = defaultdict(list)
    for action in provider_actions:
        if start <= action.ex_date <= end:
            providers[(action.security_id, action.kind, action.ex_date)].append(action)
    for record in independent:
        if start <= record.ex_date <= end:
            others[(record.security_id, record.kind, record.ex_date)].append(record)
    counters: Counter[str] = Counter()
    codes: Counter[tuple[str, Status]] = Counter()
    identity_keys: dict[str, set[Key]] = defaultdict(set)
    for action in provider_actions:
        identity_keys[action.action_id].add((action.security_id, action.kind, action.ex_date))
    conflicts = [keys for keys in identity_keys.values() if len(keys) > 1]
    conflicting_keys = {key for keys in conflicts for key in keys}
    if conflicts:
        codes[("provider_action_identity_conflict", "FAIL")] = len(conflicts)
    if not complete_independent_inventory:
        codes[("independent_inventory_unverified", "RESTRICTED")] += 1
    for key in sorted(providers.keys() | others.keys()):
        provider_group = providers.get(key, [])
        other_group = others.get(key, [])
        if key in conflicting_keys:
            counters["ambiguous"] += 1
            continue
        if len(provider_group) > 1:
            counters["ambiguous"] += 1
            codes[("provider_component_ambiguity", "FAIL")] += 1
            continue
        if len(other_group) > 1:
            counters["ambiguous"] += 1
            codes[("independent_component_ambiguity", "RESTRICTED")] += 1
            continue
        if other_group:
            issue = _independent_issue(other_group[0])
            if issue is not None:
                code, status = issue
                counters["mismatched" if status == "FAIL" else "ambiguous"] += 1
                codes[(code, status)] += 1
                continue
        if not provider_group:
            counters["missing_provider"] += 1
            status = "FAIL" if complete_independent_inventory else "RESTRICTED"
            codes[("provider_record_missing", status)] += 1
        elif not other_group:
            counters["missing_independent"] += 1
            codes[("independent_record_missing", "RESTRICTED")] += 1
        elif _equal(provider_group[0], other_group[0]):
            counters["matched"] += 1
        else:
            counters["mismatched"] += 1
            codes[("action_fields_mismatch", "FAIL")] += 1
    findings = tuple(
        ReconciliationFinding(code=code, status=status, count=count)
        for (code, status), count in sorted(codes.items())
    )
    status = max(
        (finding.status for finding in findings),
        key={"PASS": 0, "RESTRICTED": 1, "FAIL": 2}.__getitem__,
        default="PASS",
    )
    provider_sha256 = _fingerprint([a.model_dump(mode="json") for a in provider_actions])
    independent_sha256 = _fingerprint([a.model_dump(mode="json") for a in independent])
    identity = {
        "schema_version": "action-reconciliation/v1",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "complete_independent_inventory": complete_independent_inventory,
        "provider_input_sha256": provider_sha256,
        "independent_input_sha256": independent_sha256,
    }
    return ActionReconciliationReport(
        start=start,
        end=end,
        complete_independent_inventory=complete_independent_inventory,
        provider_count=len(provider_actions),
        independent_count=len(independent),
        outside_provider_count=sum(not start <= a.ex_date <= end for a in provider_actions),
        outside_independent_count=sum(not start <= a.ex_date <= end for a in independent),
        matched_count=counters["matched"],
        missing_provider_count=counters["missing_provider"],
        missing_independent_count=counters["missing_independent"],
        mismatched_count=counters["mismatched"],
        ambiguous_count=counters["ambiguous"],
        unsupported_count=sum(a.kind == "unsupported" for a in independent),
        provider_input_sha256=provider_sha256,
        independent_input_sha256=independent_sha256,
        independent_source_sha256=tuple(sorted({a.source_sha256 for a in independent})),
        reconciliation_id=hashlib.sha256(canonical_json(identity)).hexdigest(),
        findings=findings,
        status=status,
    )

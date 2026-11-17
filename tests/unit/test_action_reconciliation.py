"""Literal action comparisons using original synthetic evidence exclusively."""

from __future__ import annotations

import hashlib
import importlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from packages.data.corporate_actions import CashDividendAction, SplitAction

START = date(2024, 1, 1)
END = date(2024, 12, 31)
EX = date(2024, 3, 11)
PAY = date(2024, 3, 15)


def _module():
    return importlib.import_module("packages.data.action_reconciliation")


def _split(numerator: int = 4, denominator: int = 1, **changes):
    fields = {
        "action_id": "private-provider-split",
        "security_id": "synthetic:001",
        "symbol": "SYN",
        "ex_date": EX,
        "available_at": datetime(2024, 3, 1, tzinfo=UTC),
        "availability_basis": "synthetic",
        "numerator": numerator,
        "denominator": denominator,
    }
    return SplitAction(**(fields | changes))


def _dividend(**changes):
    fields = {
        "action_id": "private-provider-cash",
        "security_id": "synthetic:001",
        "symbol": "SYN",
        "ex_date": EX,
        "available_at": datetime(2024, 3, 1, tzinfo=UTC),
        "availability_basis": "synthetic",
        "pay_date": PAY,
        "cash_per_share": Decimal("1.25"),
    }
    return CashDividendAction(**(fields | changes))


def _independent(kind: str = "split", **changes):
    values = {
        "kind": kind,
        "security_id": "synthetic:001",
        "symbol": "SYN",
        "ex_date": EX,
        "source_reference": "private-original-issuer-source",
        "source_sha256": "a" * 64,
    }
    if kind == "split":
        values.update(numerator=4, denominator=1)
    elif kind == "cash_dividend":
        values.update(pay_date=PAY, amount=Decimal("1.25"), currency="USD")
    return _module().IndependentActionRecord(**(values | changes))


def _reconcile(provider, independent, *, complete: bool = True):
    return _module().reconcile_actions(
        provider, independent, start=START, end=END, complete_independent_inventory=complete
    )


def _codes(report):
    return {finding.code for finding in report.findings}


@pytest.mark.parametrize(
    "numerator,denominator,other_n,other_d",
    [
        (4, 1, 8, 2),
        (10, 1, 100, 10),
        (1, 4, 2, 8),
    ],
)
def test_exact_forward_and_reverse_split_fractions_match(
    numerator: int,
    denominator: int,
    other_n: int,
    other_d: int,
) -> None:
    report = _reconcile(
        [_split(numerator, denominator)], [_independent(numerator=other_n, denominator=other_d)]
    )
    assert report.status == "PASS"
    assert report.matched_count == 1
    assert report.mismatched_count == report.ambiguous_count == 0


def test_ordinary_cash_distribution_matches_only_with_complete_exact_fields() -> None:
    report = _reconcile([_dividend()], [_independent("cash_dividend")])
    assert report.status == "PASS"
    assert report.matched_count == 1
    assert not report.announcement_availability_established


def test_matching_observed_records_do_not_prove_an_incomplete_inventory_complete() -> None:
    report = _reconcile([_split()], [_independent()], complete=False)
    assert report.status == "RESTRICTED"
    assert report.matched_count == 1
    assert "independent_inventory_unverified" in _codes(report)


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount", Decimal("1.2500000000000000000000000001")),
        ("pay_date", date(2024, 3, 18)),
        ("currency", "EUR"),
    ],
)
def test_known_dividend_contradictions_fail_without_tolerance(field, value) -> None:
    with localcontext() as context:
        context.prec = 2
        report = _reconcile([_dividend()], [_independent("cash_dividend", **{field: value})])
    assert report.status == "FAIL"
    assert report.mismatched_count == 1
    assert report.matched_count == 0


@pytest.mark.parametrize("field", ["pay_date", "amount", "currency"])
def test_unknown_dividend_fields_are_not_filled_or_defaulted(field: str) -> None:
    record = _independent("cash_dividend", **{field: None})
    assert getattr(record, field) is None
    report = _reconcile([_dividend()], [record])
    assert report.status == "RESTRICTED"
    assert report.ambiguous_count == 1
    assert report.matched_count == report.mismatched_count == 0
    assert "independent_dividend_fields_missing" in _codes(report)


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), float("nan"), 0.1])
def test_nonfinite_or_inexact_input_amount_cannot_enter_the_exact_contract(amount) -> None:
    with pytest.raises(ValidationError):
        _independent("cash_dividend", amount=amount)


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"numerator": None}, "independent_split_fields_missing"),
        ({"denominator": None}, "independent_split_fields_missing"),
    ],
)
def test_missing_split_terms_remain_unverified(changes, code: str) -> None:
    report = _reconcile([_split()], [_independent(**changes)])
    assert report.status == "RESTRICTED"
    assert report.ambiguous_count == 1
    assert code in _codes(report)


@pytest.mark.parametrize(
    "changes",
    [
        {"denominator": 0},
        {"numerator": -4},
        {"numerator": 1, "denominator": 1},
    ],
)
def test_invalid_independent_split_terms_are_explicit_contradictions(changes) -> None:
    report = _reconcile([_split()], [_independent(**changes)])
    assert report.status == "FAIL"
    assert report.mismatched_count == 1
    assert "independent_split_invalid" in _codes(report)


def test_opposite_split_direction_is_a_mismatch() -> None:
    report = _reconcile([_split()], [_independent(numerator=1, denominator=4)])
    assert report.status == "FAIL"
    assert report.mismatched_count == 1


def test_missing_provider_record_is_a_failure_only_for_known_complete_independent_inventory() -> (
    None
):
    complete = _reconcile([], [_independent()], complete=True)
    incomplete = _reconcile([], [_independent()], complete=False)
    assert complete.status == "FAIL"
    assert incomplete.status == "RESTRICTED"
    assert complete.missing_provider_count == incomplete.missing_provider_count == 1


def test_missing_independent_evidence_stays_restricted() -> None:
    report = _reconcile([_split()], [])
    assert report.status == "RESTRICTED"
    assert report.missing_independent_count == 1
    assert report.missing_provider_count == report.matched_count == 0


def test_multiple_independent_components_are_not_added_or_silently_selected() -> None:
    report = _reconcile(
        [_dividend()],
        [
            _independent("cash_dividend", amount=Decimal("0.5")),
            _independent(
                "cash_dividend", amount=Decimal("0.75"), source_reference="second-component"
            ),
        ],
    )
    assert report.status == "RESTRICTED"
    assert report.ambiguous_count == 1
    assert report.matched_count == report.mismatched_count == 0
    assert "independent_component_ambiguity" in _codes(report)


def test_duplicate_provider_actions_are_not_double_counted_as_confirmed() -> None:
    report = _reconcile([_split(), _split(action_id="second-id")], [_independent()])
    assert report.status == "FAIL"
    assert report.ambiguous_count == 1
    assert report.matched_count == 0
    assert "provider_component_ambiguity" in _codes(report)


def test_unsupported_independent_actions_remain_explicitly_unverified() -> None:
    report = _reconcile([], [_independent("unsupported")])
    assert report.status == "RESTRICTED"
    assert report.unsupported_count == report.ambiguous_count == 1
    assert report.matched_count == 0


def test_stable_identity_is_required_even_when_the_ticker_and_dates_agree() -> None:
    report = _reconcile([_split()], [_independent(security_id="synthetic:002")])
    assert report.matched_count == 0
    assert report.missing_provider_count == report.missing_independent_count == 1


def test_outside_coverage_records_are_counted_and_fingerprinted_without_affecting_comparisons() -> (
    None
):
    report = _reconcile(
        [_split(), _split(ex_date=date(2025, 1, 2), action_id="outside-provider")],
        [_independent(), _independent(ex_date=date(2023, 12, 29), numerator=10)],
    )
    assert report.status == "PASS"
    assert report.matched_count == 1
    assert report.provider_count == report.independent_count == 2
    assert report.outside_provider_count == report.outside_independent_count == 1


def test_different_immutable_correction_inputs_have_different_identity_and_preserve_original() -> (
    None
):
    original = _independent("cash_dividend")
    corrected = _independent("cash_dividend", amount=Decimal("1.26"), source_sha256="b" * 64)
    before = original.model_dump_json()
    first = _reconcile([_dividend()], [original])
    second = _reconcile([_dividend()], [corrected])
    assert first.status == "PASS" and second.status == "FAIL"
    assert first.independent_input_sha256 != second.independent_input_sha256
    assert first.reconciliation_id != second.reconciliation_id
    assert original.model_dump_json() == before


def test_report_is_order_independent_and_does_not_publish_rates_source_refs_or_opaque_ids() -> None:
    providers = [_split(), _dividend(ex_date=date(2024, 4, 1), pay_date=date(2024, 4, 5))]
    others = [
        _independent(),
        _independent("cash_dividend", ex_date=date(2024, 4, 1), pay_date=date(2024, 4, 5)),
    ]
    first = _reconcile(providers, others)
    second = _reconcile(list(reversed(providers)), list(reversed(others)))
    assert first.model_dump_json() == second.model_dump_json()
    public = first.model_dump_json()
    for value in ("1.25", "private-provider", "private-original-issuer-source", "synthetic:001"):
        assert value not in public
    assert "available_at" not in public
    assert json.loads(public)["schema_version"] == "action-reconciliation/v1"


def test_invalid_comparison_window_is_rejected_without_source_details() -> None:
    with pytest.raises(ValueError, match="invalid_reconciliation_interval"):
        _module().reconcile_actions([_split()], [_independent()], start=END, end=START)


def test_reused_provider_action_id_cannot_certify_two_distinct_events() -> None:
    other_date = date(2024, 4, 1)
    report = _reconcile(
        [_split(), _split(ex_date=other_date)],
        [_independent(), _independent(ex_date=other_date)],
    )
    assert report.status == "FAIL"
    assert report.ambiguous_count == 2
    assert report.matched_count == 0
    assert "provider_action_identity_conflict" in _codes(report)
    assert "private-provider-split" not in report.model_dump_json()


def _currency_proof(record=None, **changes):
    from packages.research.artifacts import canonical_json

    record = record or _independent("cash_dividend", currency=None)
    values = {
        "record_sha256": hashlib.sha256(canonical_json(record.model_dump(mode="json"))).hexdigest(),
        "currency": "USD",
        "policy_source_sha256": hashlib.sha256(
            b"invented explicit distribution policy"
        ).hexdigest(),
        "policy_reference": "synthetic currency policy, section 2",
        "policy_publication_date": "2024-01-02",
        "coverage_start": "2024-01-02",
        "coverage_end": "2024-12-31",
        "observed_at": "2026-11-17T12:00:00Z",
        "interpretation": "Invented policy explicitly applies to this synthetic security.",
    }
    return _module().IndependentCurrencyResolution(**(values | changes))


def _currency_documents(record):
    return {
        record.source_sha256: b"invented issuer event",
        hashlib.sha256(
            b"invented explicit distribution policy"
        ).hexdigest(): b"invented explicit distribution policy",
    }


def _currency_record(**changes):
    return _independent(
        "cash_dividend",
        currency=None,
        source_sha256=hashlib.sha256(b"invented issuer event").hexdigest(),
        **changes,
    )


def test_currency_resolution_is_exact_record_bound_immutable_and_not_admission() -> None:
    record = _currency_record()
    before = record.model_dump_json()
    proof = _currency_proof(record)
    resolve = _module().resolve_independent_currency
    derived, receipt = resolve(record, proof, evidence_documents=_currency_documents(record))
    repeated, repeated_receipt = resolve(
        record, proof, evidence_documents=dict(reversed(list(_currency_documents(record).items())))
    )
    assert receipt == repeated_receipt
    assert derived == repeated
    assert record.model_dump_json() == before
    assert record.currency is None and derived.currency == "USD"
    assert derived.amount == record.amount and derived.pay_date == record.pay_date
    assert derived.ex_date == record.ex_date and derived.security_id == record.security_id
    assert derived.source_sha256 == hashlib.sha256(receipt).hexdigest()
    assert derived.source_reference == "independent-currency-resolution/v1:" + derived.source_sha256
    body = json.loads(receipt)
    assert body["schema_version"] == "independent-currency-resolution/v1"
    assert body["original_record"] == record.model_dump(mode="json")
    assert body["admitted_v2"] is False
    assert body["historical_availability_established"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("symbol", "OTHER"),
        ("security_id", "synthetic:002"),
        ("ex_date", date(2024, 3, 12)),
        ("pay_date", date(2024, 3, 18)),
        ("amount", Decimal("1.25000000000000000001")),
    ],
)
def test_currency_resolution_cannot_apply_to_a_different_event_or_revision(field, value) -> None:
    record = _currency_record()
    changed = record.model_copy(update={field: value})
    with pytest.raises(ValueError, match="currency_resolution_record_mismatch"):
        _module().resolve_independent_currency(
            changed, _currency_proof(record), evidence_documents=_currency_documents(record)
        )


@pytest.mark.parametrize(
    "which,mutation",
    [
        ("policy", "missing"),
        ("policy", "corrupt"),
        ("event", "missing"),
        ("event", "corrupt"),
    ],
)
def test_currency_resolution_requires_original_event_and_exact_policy_bytes(
    which, mutation
) -> None:
    record = _currency_record()
    proof = _currency_proof(record)
    documents = _currency_documents(record)
    key = proof.policy_source_sha256 if which == "policy" else record.source_sha256
    if mutation == "missing":
        del documents[key]
    else:
        documents[key] = b"changed evidence"
    with pytest.raises(ValueError, match="currency_resolution_evidence_invalid"):
        _module().resolve_independent_currency(record, proof, evidence_documents=documents)


@pytest.mark.parametrize(
    "changes",
    [
        {"coverage_start": "2024-03-12"},
        {"coverage_end": "2024-03-14"},
        {"policy_publication_date": "2024-03-12"},
    ],
)
def test_currency_resolution_requires_event_and_payment_inside_contemporaneous_policy(changes):
    record = _currency_record()
    with pytest.raises(ValueError, match="currency_resolution_policy_not_applicable"):
        _module().resolve_independent_currency(
            record,
            _currency_proof(record, **changes),
            evidence_documents=_currency_documents(record),
        )


@pytest.mark.parametrize("currency", ["USD", "EUR"])
def test_currency_resolution_never_overwrites_an_existing_currency(currency):
    record = _currency_record().model_copy(update={"currency": currency})
    with pytest.raises(ValueError, match="currency_resolution_requires_unknown_cash_currency"):
        _module().resolve_independent_currency(
            record, _currency_proof(record), evidence_documents=_currency_documents(record)
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"currency": "usd"},
        {"currency": ""},
        {"currency": "US"},
        {"observed_at": "2026-11-17T12:00:00"},
        {"observed_at": "2023-01-01T00:00:00Z"},
        {"coverage_start": "2025-01-01"},
        {"record_sha256": "invalid"},
        {"pay_date": "2024-03-18"},
        {"special": False},
        {"amount_tolerance": "0.01"},
    ],
)
def test_currency_resolution_rejects_invalid_provenance_or_unregistered_field_overrides(changes):
    with pytest.raises(ValidationError):
        _currency_proof(_currency_record(), **changes)


def test_currency_resolution_preserves_exact_amount_and_requires_payment_and_cash_kind():
    record = _currency_record(amount=Decimal("1.250000000000000000000000001"))
    derived, _ = _module().resolve_independent_currency(
        record, _currency_proof(record), evidence_documents=_currency_documents(record)
    )
    assert derived.amount.as_tuple() == record.amount.as_tuple()
    for changed in [record.model_copy(update={"pay_date": None}), _independent("split")]:
        with pytest.raises(ValueError, match="currency_resolution_requires_unknown_cash_currency"):
            _module().resolve_independent_currency(
                changed, _currency_proof(changed), evidence_documents=_currency_documents(record)
            )

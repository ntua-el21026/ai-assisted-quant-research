"""Original invented action rows exercise explicit economic applicability only."""

from __future__ import annotations

import hashlib
import importlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from packages.data.alpaca_historical import (
    AcquiredPage,
    CorporateActionsRequest,
    HistoricalAcquisition,
    historical_query,
)


def _module():
    return importlib.import_module("packages.data.action_scope")


def _context(**changes):
    values = {
        "start": date(2024, 2, 1),
        "end": date(2024, 12, 31),
        "feature_history_start": date(2024, 1, 1),
        "opening_state": "flat_cash",
        "raw_execution": True,
        "feature_basis": "raw",
        "opening_positions_empty": True,
        "opening_orders_empty": True,
        "opening_receivables_empty": True,
        "opening_balances_independent": True,
    }
    return _module().ActionScopeContext(**(values | changes))


def _cash(**changes):
    return {
        "id": "synthetic-private-event",
        "symbol": "SYN",
        "foreign": False,
        "special": False,
        "rate": "0.73",
        "currency": "USD",
        "ex_date": "2024-03-11",
        "payable_date": "2024-03-22",
        "process_date": "2024-03-01",
    } | changes


def _split(**changes):
    return {
        "id": "synthetic-private-split",
        "symbol": "SYN",
        "new_rate": "4",
        "old_rate": "1",
        "ex_date": "2024-03-11",
        "process_date": "2024-03-01",
    } | changes


def _acquisition(categories=None, *, body: bytes | None = None):
    request = CorporateActionsRequest(
        provider="alpaca",
        symbols=("SYN",),
        start=date(2024, 1, 1),
        end=date(2024, 3, 31),
        types="all",
        data_quality="all",
    )
    endpoint, query = historical_query(request)
    raw = (
        body
        or json.dumps(
            {
                "corporate_actions": {"cash_dividends": [_cash()]}
                if categories is None
                else categories,
                "next_page_token": None,
            }
        ).encode()
    )
    page = AcquiredPage(
        endpoint, tuple(sorted(query.items())), raw, datetime(2024, 4, 1, 12, 1, tzinfo=UTC)
    )
    return HistoricalAcquisition(
        request, datetime(2024, 4, 1, 12, tzinfo=UTC), page.received_at, (page,)
    )


def _classify(categories=None, *, context=None, acquisition=None):
    return _module().classify_action_scope(
        acquisition or _acquisition(categories), context or _context()
    )


def test_current_ordinary_cash_is_applicable_but_proves_no_historical_announcement_time() -> None:
    acquisition = _acquisition()
    report = _classify(acquisition=acquisition)
    (record,) = report.records
    assert (record.scope, record.support) == ("applicable", "supported")
    assert report.status == "PASS" and not report.blocked
    assert report.applicable_count == 1
    assert record.source_page_sha256 == hashlib.sha256(acquisition.pages[0].body).hexdigest()
    assert not report.inventory_completeness_established
    assert not report.announcement_availability_established


def test_applicable_missing_currency_has_an_explicit_validation_finding():
    report = _classify({"cash_dividends": [_cash(currency=None)]})
    findings = {finding.code: finding for finding in report.findings}
    assert findings["applicable_cash_currency_unverified"].count == 1
    assert findings["applicable_cash_currency_unverified"].status == "RESTRICTED"
    assert report.blocked


@pytest.mark.parametrize("pay_date", ["2023-12-22", "2024-04-12", "2025-01-17"])
def test_prior_cash_has_no_inherited_entitlement_under_explicit_fresh_flat_raw_contract(pay_date):
    report = _classify(
        {"cash_dividends": [_cash(special=True, ex_date="2023-12-11", payable_date=pay_date)]}
    )
    (record,) = report.records
    assert record.scope == "outside"
    assert record.support == "unsupported"
    assert record.special is True
    assert record.reason == "prior_ex_date_no_opening_entitlement"
    assert report.outside_count == 1
    assert report.status == "PASS" and not report.blocked


@pytest.mark.parametrize(
    "changes",
    [
        {"opening_state": "carry_in"},
        {"opening_state": "unknown"},
        {"opening_positions_empty": False},
        {"opening_orders_empty": False},
        {"opening_receivables_empty": False},
        {"opening_balances_independent": False},
        {"raw_execution": False},
        {"feature_basis": "provider_adjusted"},
        {"feature_basis": "unknown"},
        {"feature_basis": "causal_split_asof"},
    ],
)
def test_any_missing_fresh_raw_proof_blocks_automatic_prior_cash_exclusion(changes):
    report = _classify(
        {"cash_dividends": [_cash(ex_date="2023-12-11", payable_date="2024-04-12")]},
        context=_context(**changes),
    )
    assert report.records[0].scope == "unverified"
    assert report.blocked and report.status != "PASS"


def test_prior_cash_with_zero_current_quantity_but_inherited_receivable_is_not_dropped() -> None:
    report = _classify(
        {"cash_dividends": [_cash(ex_date="2023-12-11", payable_date="2024-04-12")]},
        context=_context(
            opening_state="carry_in", opening_positions_empty=True, opening_receivables_empty=False
        ),
    )
    assert report.records[0].scope == "unverified" and report.blocked


def test_prior_cash_inside_feature_warmup_is_conservatively_unverified() -> None:
    report = _classify({"cash_dividends": [_cash(ex_date="2024-01-15", payable_date="2024-03-22")]})
    assert report.records[0].scope == "unverified" and report.blocked


@pytest.mark.parametrize("special,foreign", [(True, False), (False, True)])
def test_relevant_special_or_foreign_cash_stays_unsupported_even_with_zero_opening_positions(
    special,
    foreign,
) -> None:
    report = _classify({"cash_dividends": [_cash(special=special, foreign=foreign)]})
    assert report.records[0].scope == "applicable"
    assert report.records[0].support == "unsupported"
    assert report.status == "FAIL" and report.blocked


@pytest.mark.parametrize(
    "category,row",
    [
        ("forward_splits", _split(ex_date="2023-12-11")),
        ("mergers", _cash(ex_date="2023-12-11")),
        ("symbol_changes", _cash(ex_date="2023-12-11")),
    ],
)
def test_old_splits_and_identity_structural_records_are_never_automatically_excluded(category, row):
    report = _classify({category: [row]})
    assert report.records[0].scope == "unverified" and report.blocked


@pytest.mark.parametrize(
    "changes",
    [
        {"ex_date": None},
        {"payable_date": None},
        {"ex_date": "invalid"},
        {"payable_date": "2023-11-01", "ex_date": "2023-12-11"},
        {"process_date": "2025-01-01"},
        {"process_date": None},
        {"symbol": "OTHER"},
        {"rate": "NaN"},
        {"rate": "0"},
        {"special": "false"},
        {"foreign": None},
        {"id": None},
    ],
)
def test_malformed_cash_cannot_be_excluded_or_normalized(changes) -> None:
    row = _cash(**({"ex_date": "2023-12-11", "payable_date": "2024-04-12"} | changes))
    report = _classify({"cash_dividends": [row]})
    assert report.records[0].scope == "unverified"
    assert report.blocked and report.status == "FAIL"


@pytest.mark.parametrize(
    "changes",
    [
        {"new_rate": "0"},
        {"old_rate": "0"},
        {"new_rate": "NaN"},
        {"new_rate": "1", "old_rate": "4"},
    ],
)
def test_invalid_or_contradictory_split_ratios_block(changes):
    report = _classify({"forward_splits": [_split(**changes)]})
    assert report.records[0].scope == "unverified"
    assert report.status == "FAIL" and report.blocked


def test_duplicate_source_ids_and_conflicting_same_effective_kind_remain_in_inventory() -> None:
    for rows in (
        [_cash(), _cash(ex_date="2024-03-12")],
        [_cash(), _cash(id="different-private-id")],
    ):
        report = _classify({"cash_dividends": rows})
        assert len(report.records) == 2
        assert all(record.scope == "unverified" for record in report.records)
        assert report.status == "FAIL" and report.blocked


def test_every_row_is_retained_even_if_an_unknown_category_or_nonobject_row_is_invalid() -> None:
    report = _classify({"cash_dividends": [_cash(), 7], "spin_offs": [_cash(id="structural")]})
    assert len(report.records) == 3
    assert report.applicable_count == 1 and report.unverified_count == 2
    assert report.blocked


def test_future_raw_cash_is_outside_but_adjusted_dependencies_stay_unverified() -> None:
    rows = {"cash_dividends": [_cash(ex_date="2025-03-11", payable_date="2025-03-22")]}
    raw = _classify(rows)
    adjusted = _classify(rows, context=_context(feature_basis="provider_adjusted"))
    assert raw.records[0].scope == "outside" and not raw.blocked
    assert adjusted.records[0].scope == "unverified" and adjusted.blocked


def test_applicable_normalization_uses_derived_selection_and_keeps_original_source_unchanged() -> (
    None
):
    acquisition = _acquisition(
        {
            "cash_dividends": [
                _cash(
                    id="old-special", special=True, ex_date="2023-12-11", payable_date="2024-04-12"
                ),
                _cash(id="current-ordinary"),
            ]
        }
    )
    before = acquisition.pages[0].body
    report = _classify(acquisition=acquisition)
    actions = _module().normalize_applicable_actions(
        acquisition, report, security_ids={"SYN": "synthetic:001"}
    )
    assert len(actions) == 1 and actions[0].cash_per_share == Decimal("0.73")
    assert actions[0].action_id == "current-ordinary"
    assert acquisition.pages[0].body == before
    assert actions[0].available_at == acquisition.acquired_at


def test_empty_applicable_inventory_never_normalizes_the_excluded_special_as_ordinary() -> None:
    acquisition = _acquisition(
        {"cash_dividends": [_cash(special=True, ex_date="2023-12-11", payable_date="2024-04-12")]}
    )
    report = _classify(acquisition=acquisition)
    assert (
        _module().normalize_applicable_actions(
            acquisition, report, security_ids={"SYN": "synthetic:001"}
        )
        == ()
    )


def test_source_and_context_fingerprints_prevent_reusing_a_report_for_changed_inputs() -> None:
    first = _acquisition()
    report = _classify(acquisition=first)
    changed = _acquisition({"cash_dividends": [_cash(rate="0.74")]})
    with pytest.raises(ValueError, match="scope_report_mismatch"):
        _module().normalize_applicable_actions(
            changed, report, security_ids={"SYN": "synthetic:001"}
        )


def test_blocked_scope_cannot_be_normalized_and_forged_report_fields_are_detected() -> None:
    acquisition = _acquisition({"cash_dividends": [_cash(special=True)]})
    report = _classify(acquisition=acquisition)
    with pytest.raises(ValueError, match="action_scope_blocked"):
        _module().normalize_applicable_actions(
            acquisition, report, security_ids={"SYN": "synthetic:001"}
        )
    forged = report.model_copy(update={"blocked": False, "status": "PASS"})
    with pytest.raises(ValueError, match="scope_report_mismatch"):
        _module().normalize_applicable_actions(
            acquisition, forged, security_ids={"SYN": "synthetic:001"}
        )


def test_private_and_public_reports_are_deterministic_without_publishing_raw_fields() -> None:
    report = _classify()
    module = _module()
    assert module.private_report_bytes(report) == module.private_report_bytes(_classify())
    public = module.public_scope_report_bytes(report)
    for secret in (b"synthetic-private-event", b"0.73", b'"rate"', b'"source_id"', b'"ex_date"'):
        assert secret not in public
    assert json.loads(public)["record_count"] == 1


def test_invalid_pagination_metadata_does_not_erase_otherwise_readable_raw_rows() -> None:
    raw = json.dumps(
        {"corporate_actions": {"cash_dividends": [_cash()]}, "next_page_token": 123}
    ).encode()
    report = _classify(acquisition=_acquisition(body=raw))
    assert len(report.records) == 1
    assert report.status == "FAIL" and report.blocked


def test_report_context_cannot_be_replaced_without_reclassification() -> None:
    acquisition = _acquisition()
    report = _classify(acquisition=acquisition)
    altered = report.model_copy(update={"context": _context(feature_basis="provider_adjusted")})
    with pytest.raises(ValueError, match="scope_report_mismatch"):
        _module().normalize_applicable_actions(
            acquisition, altered, security_ids={"SYN": "synthetic:001"}
        )


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_invalid_numeric_constant_cannot_erase_itself_or_later_valid_rows(invalid) -> None:
    acquisition = _acquisition(
        {
            "cash_dividends": [
                _cash(id="invalid-private-id", rate=invalid, ex_date="2023-12-11"),
                _cash(id="valid-private-id"),
            ]
        }
    )
    report = _classify(acquisition=acquisition)
    assert len(report.records) == 2
    assert report.unverified_count == report.applicable_count == 1
    assert report.status == "FAIL" and report.blocked
    assert _module().private_report_bytes(report) == _module().private_report_bytes(
        _classify(acquisition=acquisition)
    )


def test_unknown_currency_can_be_irrelevant_without_becoming_a_usd_normalization_claim() -> None:
    prior = _classify(
        {"cash_dividends": [_cash(currency=None, ex_date="2023-12-11", payable_date="2024-04-12")]}
    )
    assert prior.records[0].scope == "outside"
    assert prior.records[0].support == "unverified"
    assert not prior.blocked
    current = _classify({"cash_dividends": [_cash(currency=None)]})
    assert current.records[0].scope == "applicable"
    assert current.records[0].support == "unverified" and current.blocked

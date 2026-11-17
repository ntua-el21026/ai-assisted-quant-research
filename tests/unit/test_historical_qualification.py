"""Deterministic quality decisions over original invented candidate bytes."""

from __future__ import annotations

import hashlib
import importlib
import json
import socket
from datetime import date
from pathlib import Path

import pytest
from test_historical_candidates import candidate_fixture, replace_page, rewrite_manifest


def _report(path: Path):
    candidates = importlib.import_module("packages.data.historical_candidates")
    quality = importlib.import_module("packages.data.historical_qualification")
    return quality.qualify_historical_candidate(candidates.load_historical_candidate(path))


def _codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


def test_correct_invented_bars_pass_technical_checks_without_a_research_release(
    tmp_path: Path,
) -> None:
    path = candidate_fixture(tmp_path)
    report = _report(path)
    assert report.technical_status == "PASS"
    assert report.status == "RESTRICTED"
    assert report.next_phase == "BLOCKED"
    (coverage,) = report.feed_coverage
    assert (
        coverage.feed,
        coverage.adjustment,
        coverage.expected_pairs,
        coverage.observed_rows,
        coverage.observed_pairs,
    ) == ("iex", "raw", 2, 2, 2)
    assert coverage.missing_pairs == ()
    assert report.candidate_manifest_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert {"synthetic_input", "iex_venue_limited"} <= _codes(report)


@pytest.mark.parametrize(
    "mode,code",
    [
        ("missing", "missing_sessions"),
        ("duplicate", "duplicate_sessions"),
        ("ohlc", "invalid_ohlcv"),
        ("negative_volume", "invalid_ohlcv"),
        ("fractional_volume", "fractional_volume"),
        ("unknown_symbol", "unexpected_symbol"),
        ("weekend", "unexpected_session"),
        ("timestamp", "invalid_bar_timestamp"),
        ("nonfinite", "invalid_ohlcv"),
    ],
)
def test_source_quality_failures_remain_visible_without_changing_the_input(
    tmp_path: Path,
    mode: str,
    code: str,
) -> None:
    path = candidate_fixture(tmp_path)
    payload = json.loads((path.parent / "page.json").read_bytes())
    rows = payload["bars"]["SYN"]
    if mode == "missing":
        rows.pop()
    elif mode == "duplicate":
        rows.append(rows[0])
    elif mode == "ohlc":
        rows[0]["h"] = "1"
    elif mode == "negative_volume":
        rows[0]["v"] = -1
    elif mode == "fractional_volume":
        rows[0]["v"] = "1.5"
    elif mode == "unknown_symbol":
        payload["bars"]["OTHER"] = payload["bars"].pop("SYN")
    elif mode == "weekend":
        rows[0]["t"] = "2024-03-10T05:00:00Z"
    elif mode == "timestamp":
        rows[0]["t"] = "2024-03-11T12:00:00Z"
    else:
        rows[0]["c"] = "NaN"
    replace_page(path, payload)
    before = (path.parent / "page.json").read_bytes()
    report = _report(path)
    assert (report.status, report.technical_status, report.next_phase) == (
        "FAIL",
        "FAIL",
        "BLOCKED",
    )
    assert code in _codes(report)
    assert (path.parent / "page.json").read_bytes() == before


def test_zero_volume_is_counted_and_restricted_without_filling_prices(tmp_path: Path) -> None:
    path = candidate_fixture(tmp_path)
    payload = json.loads((path.parent / "page.json").read_bytes())
    payload["bars"]["SYN"][0]["v"] = 0
    replace_page(path, payload)
    report = _report(path)
    assert report.feed_coverage[0].zero_volume_rows == 1
    assert "zero_volume" in _codes(report)
    assert report.technical_status == "RESTRICTED"


@pytest.mark.parametrize("raw", [b'{"bars":', b'{"bars":{},"bars":{}}', b"[]", b'{"bars": NaN}'])
def test_malformed_source_json_is_a_sanitized_failure(tmp_path: Path, raw: bytes) -> None:
    path = candidate_fixture(tmp_path)
    (path.parent / "page.json").write_bytes(raw)
    rewrite_manifest(
        path,
        lambda d: d["files"][0].update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
    )
    report = _report(path)
    assert report.technical_status == "FAIL"
    assert "invalid_source_page" in _codes(report)


@pytest.mark.parametrize(
    "mode,code",
    [
        ("query", "acquisition_query_mismatch"),
        ("unfinished", "acquisition_pagination_incomplete"),
        ("forged_token", "acquisition_query_mismatch"),
    ],
)
def test_complete_query_claims_are_checked_against_retained_pages(
    tmp_path: Path,
    mode: str,
    code: str,
) -> None:
    path = candidate_fixture(tmp_path)
    if mode == "unfinished":
        payload = json.loads((path.parent / "page.json").read_bytes())
        payload["next_page_token"] = "private-opaque-token"
        replace_page(path, payload)
    else:

        def change(data):
            query = data["acquisitions"][0]["pages"][0]["query"]
            query.append(["page_token" if mode == "forged_token" else "unexpected", "opaque"])

        rewrite_manifest(path, change)
    report = _report(path)
    assert report.technical_status == "FAIL"
    assert code in _codes(report)


@pytest.mark.parametrize(
    "mode,code",
    [
        ("calendar", "calendar_unverified"),
        ("actions", "action_inventory_unverified"),
        ("reconciliation", "reconciliation_unverified"),
        ("identity", "identity_uncertain"),
        ("rights", "retention_requires_clarification"),
    ],
)
def test_unresolved_evidence_is_retained_and_blocks_the_next_research_phase(
    tmp_path: Path,
    mode: str,
    code: str,
) -> None:
    path = candidate_fixture(tmp_path, kind="historical")

    def change(data):
        if mode == "rights":
            data["license"]["retention"] = "requires_clarification"
        elif mode == "identity":
            data["identities"][0]["mappings"][0]["point_in_time_status"] = "uncertain"
        else:
            field = {
                "calendar": "calendar_evidence",
                "actions": "action_inventory",
                "reconciliation": "reconciliation",
            }[mode]
            data[field]["status"] = "unverified"

    rewrite_manifest(path, change)
    report = _report(path)
    assert report.status == "RESTRICTED"
    assert report.technical_status == "PASS"
    assert report.next_phase == "BLOCKED"
    assert code in _codes(report)


@pytest.mark.parametrize("field", ["entitlement", "storage", "retention"])
def test_prohibited_private_use_is_a_failure(tmp_path: Path, field: str) -> None:
    path = candidate_fixture(tmp_path, kind="historical")
    rewrite_manifest(path, lambda d: d["license"].update({field: "prohibited"}))
    report = _report(path)
    assert (report.status, report.next_phase) == ("FAIL", "BLOCKED")


def test_unknown_actions_are_counted_before_normalization_and_outside_ex_dates_are_retained(
    tmp_path: Path,
) -> None:
    path = candidate_fixture(tmp_path)
    body = json.dumps(
        {
            "corporate_actions": {
                "cash_dividends": [
                    {
                        "id": "private-action-1",
                        "symbol": "SYN",
                        "ex_date": "2024-03-12",
                        "process_date": "2024-03-11",
                    }
                ],
                "spin_offs": [
                    {
                        "id": "private-action-2",
                        "symbol": "SYN",
                        "ex_date": "2025-01-01",
                        "process_date": "2024-03-12",
                    }
                ],
            },
            "next_page_token": None,
        }
    ).encode()
    (path.parent / "actions.json").write_bytes(body)
    from packages.data.alpaca_historical import CorporateActionsRequest, historical_query

    request = CorporateActionsRequest(
        provider="alpaca", symbols=("SYN",), start="2024-03-11", end="2024-03-12", types="all"
    )
    _, query = historical_query(request)

    def change(data):
        data["files"].append(
            {
                "path": "actions.json",
                "role": "raw_page",
                "acquisition_id": "actions-1",
                "size_bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
        data["acquisitions"].append(
            {
                "acquisition_id": "actions-1",
                "role": "candidate",
                "request_kind": "actions",
                "request": request.model_dump(mode="json"),
                "request_started_at": "2024-03-13T12:00:00Z",
                "acquired_at": "2024-03-13T12:01:00Z",
                "complete": True,
                "normalization_error_code": "unsupported_corporate_action",
                "pages": [
                    {
                        "file_path": "actions.json",
                        "query": sorted(query.items()),
                        "received_at": "2024-03-13T12:01:00Z",
                        "http_status": 200,
                    }
                ],
            }
        )

    rewrite_manifest(path, change)
    report = _report(path)
    assert report.action_inventory.observed_records == 2
    assert report.action_inventory.unsupported_records == 1
    assert report.action_inventory.outside_candidate_ex_dates == 1
    assert report.action_inventory.status == "FAIL"
    assert "unsupported_corporate_actions" in _codes(report)
    quality = importlib.import_module("packages.data.historical_qualification")
    public = quality.qualification_report_bytes(report)
    assert b"private-action" not in public


def test_error_body_and_opaque_receipts_never_enter_public_report(tmp_path: Path) -> None:
    path = candidate_fixture(tmp_path)
    replace_page(path, {"message": "RAW-PRIVATE-ERROR-KEY", "next_page_token": "OPAQUE-TOKEN"})

    def change(data):
        data["acquisitions"][0].update(complete=False, error_code="forbidden")
        data["acquisitions"][0]["pages"][0]["http_status"] = 403

    rewrite_manifest(path, change)
    report = _report(path)
    quality = importlib.import_module("packages.data.historical_qualification")
    public = quality.qualification_report_bytes(report)
    assert b"RAW-PRIVATE" not in public and b"OPAQUE" not in public
    assert report.status == "FAIL"
    assert "acquisition_forbidden" in _codes(report)


def test_qualification_is_deterministic_offline_and_does_not_modify_candidate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = candidate_fixture(tmp_path)
    before = {p.name: p.read_bytes() for p in path.parent.iterdir()}

    def forbidden(*args, **kwargs):
        pytest.fail("network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    quality = importlib.import_module("packages.data.historical_qualification")
    first = quality.qualification_report_bytes(_report(path))
    second = quality.qualification_report_bytes(_report(path))
    assert first == second
    assert before == {p.name: p.read_bytes() for p in path.parent.iterdir()}
    assert b'"o":' not in first and b'"rate":' not in first
    assert json.loads(first)["schema_version"] == "historical-candidate-quality/v1"


@pytest.mark.parametrize("mode", ["feed", "symbols", "dates"])
def test_primary_request_must_match_the_declared_candidate_scope(tmp_path: Path, mode: str) -> None:
    path = candidate_fixture(tmp_path)

    def change(data):
        if mode == "feed":
            data["feed"] = "sip"
        elif mode == "symbols":
            data["symbols"].append("ZZZ")
        else:
            data["end"] = "2024-03-13"

    rewrite_manifest(path, change)
    report = _report(path)
    assert report.technical_status == "FAIL"
    assert report.status == "FAIL"
    assert "primary_request_scope_mismatch" in _codes(report)


@pytest.mark.parametrize("last_status", [200, 403])
def test_terminal_page_cannot_be_followed_by_a_new_query_chain(
    tmp_path: Path,
    last_status: int,
) -> None:
    path = candidate_fixture(tmp_path)
    original = json.loads((path.parent / "page.json").read_bytes())
    second_row = original["bars"]["SYN"].pop()
    replace_page(path, original)
    second = json.dumps({"bars": {"SYN": [second_row]}, "next_page_token": None}).encode()
    (path.parent / "second.json").write_bytes(second)

    def change(data):
        data["files"].append(
            {
                "path": "second.json",
                "role": "raw_page",
                "acquisition_id": "bars-1",
                "size_bytes": len(second),
                "sha256": hashlib.sha256(second).hexdigest(),
            }
        )
        data["acquisitions"][0]["pages"].append(
            {
                **data["acquisitions"][0]["pages"][0],
                "file_path": "second.json",
                "http_status": last_status,
            }
        )

    rewrite_manifest(path, change)
    report = _report(path)
    assert report.technical_status == "FAIL"
    assert "acquisition_pagination_incomplete" in _codes(report)


def test_denied_sip_preflight_is_restricted_when_explicit_iex_primary_is_valid(
    tmp_path: Path,
) -> None:
    path = candidate_fixture(tmp_path)
    raw = b'{"message":"private forbidden SIP detail"}'
    (path.parent / "preflight.json").write_bytes(raw)

    def change(data):
        request = dict(data["acquisitions"][0]["request"], feed="sip")
        query = [
            [k, "sip" if k == "feed" else v]
            for k, v in data["acquisitions"][0]["pages"][0]["query"]
        ]
        data["acquisitions"].append(
            {
                "acquisition_id": "preflight",
                "role": "preflight",
                "request_kind": "bars",
                "request": request,
                "request_started_at": "2024-03-13T12:00:00Z",
                "acquired_at": "2024-03-13T12:01:00Z",
                "complete": False,
                "error_code": "forbidden",
                "pages": [
                    {
                        "file_path": "preflight.json",
                        "query": query,
                        "received_at": "2024-03-13T12:01:00Z",
                        "http_status": 403,
                    }
                ],
            }
        )
        data["files"].append(
            {
                "path": "preflight.json",
                "role": "raw_page",
                "acquisition_id": "preflight",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    rewrite_manifest(path, change)
    report = _report(path)
    assert report.technical_status == "PASS"
    assert report.status == "RESTRICTED"
    denied = next(item for item in report.feed_coverage if item.role == "preflight")
    assert denied.status == "RESTRICTED"
    assert "acquisition_forbidden" in _codes(report)


def test_complete_receipt_requires_final_success_time_to_equal_completion(tmp_path: Path) -> None:
    path = candidate_fixture(tmp_path)
    rewrite_manifest(
        path, lambda d: d["acquisitions"][0].update(acquired_at="2024-03-13T12:02:00Z")
    )
    report = _report(path)
    assert report.technical_status == "FAIL"
    assert "acquisition_completion_time_mismatch" in _codes(report)


def test_acquisition_page_limit_is_checked_independently_of_claimed_completion(
    tmp_path: Path,
) -> None:
    path = candidate_fixture(tmp_path)
    payload = json.loads((path.parent / "page.json").read_bytes())
    second_row = payload["bars"]["SYN"].pop()
    payload["next_page_token"] = "private-token"
    replace_page(path, payload)
    raw = json.dumps({"bars": {"SYN": [second_row]}, "next_page_token": None}).encode()
    (path.parent / "second.json").write_bytes(raw)

    def change(data):
        record = data["acquisitions"][0]
        record["request"]["max_pages"] = 1
        record["pages"].append(
            {
                **record["pages"][0],
                "file_path": "second.json",
                "query": [*record["pages"][0]["query"], ["page_token", "private-token"]],
            }
        )
        data["files"].append(
            {
                "path": "second.json",
                "role": "raw_page",
                "acquisition_id": "bars-1",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    rewrite_manifest(path, change)
    report = _report(path)
    assert report.technical_status == "FAIL"
    assert "acquisition_page_limit_exceeded" in _codes(report)


def test_early_diagnostic_counts_facts_without_claiming_a_qualified_calendar(
    tmp_path: Path,
) -> None:
    path = candidate_fixture(tmp_path)
    from packages.data.alpaca_historical import HistoricalBarsRequest, historical_query

    request = HistoricalBarsRequest(
        provider="alpaca",
        symbols=("OTHER",),
        start="2016-01-04",
        end="2016-01-05",
        feed="iex",
        adjustment="raw",
        timeframe="1Day",
    )
    _, query = historical_query(request)
    raw = json.dumps(
        {
            "bars": {
                "OTHER": [
                    {"t": "2016-01-04T05:00:00Z", "o": "3", "h": "4", "l": "2", "c": "3", "v": 1}
                ]
            },
            "next_page_token": None,
        }
    ).encode()
    (path.parent / "diagnostic.json").write_bytes(raw)

    def change(data):
        data["acquisitions"].append(
            {
                "acquisition_id": "early",
                "role": "diagnostic",
                "request_kind": "bars",
                "request": request.model_dump(mode="json"),
                "request_started_at": "2024-03-13T12:00:00Z",
                "acquired_at": "2024-03-13T12:01:00Z",
                "complete": True,
                "pages": [
                    {
                        "file_path": "diagnostic.json",
                        "query": sorted(query.items()),
                        "received_at": "2024-03-13T12:01:00Z",
                        "http_status": 200,
                    }
                ],
            }
        )
        data["files"].append(
            {
                "path": "diagnostic.json",
                "role": "raw_page",
                "acquisition_id": "early",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    rewrite_manifest(path, change)
    report = _report(path)
    diagnostic = next(item for item in report.feed_coverage if item.role == "diagnostic")
    assert diagnostic.status == "RESTRICTED"
    assert diagnostic.expected_pairs is None
    assert not diagnostic.calendar_qualified
    assert diagnostic.observed_rows == diagnostic.observed_pairs == 1
    assert diagnostic.observed_session_dates == (date(2016, 1, 4),)
    assert diagnostic.missing_pairs == diagnostic.unexpected_pairs == ()
    assert report.technical_status == "PASS"
    assert "diagnostic_calendar_unqualified" in _codes(report)


def test_reused_ticker_is_not_silently_assigned_one_security_for_all_actions(
    tmp_path: Path,
) -> None:
    path = candidate_fixture(tmp_path)
    from packages.data.alpaca_historical import CorporateActionsRequest, historical_query

    request = CorporateActionsRequest(
        provider="alpaca", symbols=("SYN",), start="2024-03-11", end="2024-03-12", types="all"
    )
    _, query = historical_query(request)
    raw = json.dumps(
        {
            "corporate_actions": {
                "forward_splits": [
                    {
                        "id": "private-split",
                        "symbol": "SYN",
                        "process_date": "2024-03-11",
                        "ex_date": "2024-03-11",
                        "new_rate": "2",
                        "old_rate": "1",
                    }
                ]
            },
            "next_page_token": None,
        }
    ).encode()
    (path.parent / "action.json").write_bytes(raw)

    def change(data):
        identity = data["identities"][0]
        identity["mappings"][0]["end"] = "2024-03-11"
        data["identities"].append(
            {
                "security_id": "synthetic:002",
                "mappings": [
                    {**identity["mappings"][0], "start": "2024-03-12", "end": "2024-03-12"}
                ],
            }
        )
        data["acquisitions"].append(
            {
                "acquisition_id": "actions",
                "role": "candidate",
                "request_kind": "actions",
                "request": request.model_dump(mode="json"),
                "request_started_at": "2024-03-13T12:00:00Z",
                "acquired_at": "2024-03-13T12:01:00Z",
                "complete": True,
                "pages": [
                    {
                        "file_path": "action.json",
                        "query": sorted(query.items()),
                        "received_at": "2024-03-13T12:01:00Z",
                        "http_status": 200,
                    }
                ],
            }
        )
        data["files"].append(
            {
                "path": "action.json",
                "role": "raw_page",
                "acquisition_id": "actions",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    rewrite_manifest(path, change)
    report = _report(path)
    assert report.action_inventory.observed_records == 1
    assert report.action_inventory.status == "RESTRICTED"
    assert "action_identity_requires_date_resolution" in _codes(report)

"""Exact synthetic wire-to-v2 conversion; every HTTP response is injected."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from packages.data.alpaca_historical import (
    AlpacaHistoricalAcquirer,
    BarAvailabilityPolicy,
    CorporateActionsRequest,
    HistoricalBarsRequest,
    HttpResponse,
    normalize_historical_bars,
)
from packages.data.snapshots import MarketSession

NOW = datetime(2025, 4, 1, 12, tzinfo=UTC)
EXACT_BODY = (
    b'{"bars":{"AAPL":[{"t":"2025-03-10T04:00:00Z",'
    b'"o":100.1234567890123456789012345,"h":101,"l":99,'
    b'"c":100.2345678901234567890123456,"v":1200}]},"next_page_token":null}'
)


class Transport:
    def __init__(self, *bodies: bytes) -> None:
        self.bodies = iter(bodies)

    def get(self, endpoint: str, params: Mapping[str, str], timeout_seconds: float) -> HttpResponse:
        return HttpResponse(200, {}, next(self.bodies))


def bridge() -> Any:
    return importlib.import_module("packages.data.historical_normalization")


def request(**changes: object) -> HistoricalBarsRequest:
    return HistoricalBarsRequest.model_validate(
        {
            "provider": "alpaca",
            "symbols": ["AAPL"],
            "start": "2025-03-10",
            "end": "2025-03-10",
            "feed": "sip",
            "timeframe": "1Day",
            "adjustment": "raw",
            **changes,
        }
    )


def acquire(body: bytes = EXACT_BODY, **changes: object) -> Any:
    return AlpacaHistoricalAcquirer(transport=Transport(body), clock=lambda: NOW).fetch_bars(
        request(**changes)
    )


def normalized(acquisition: Any, **changes: Any) -> Any:
    return normalize_historical_bars(
        acquisition,
        sessions=(
            MarketSession(
                date="2025-03-10",
                open_at="2025-03-10T13:30Z",
                close_at="2025-03-10T20:00Z",
            ),
        ),
        missing_policy="error",
        **changes,
    ).bars[0]


def test_exact_wire_prices_survive_legacy_float_and_v2_conversion() -> None:
    observation = normalized(acquire())
    assert observation.exact_ohlcv.open == Decimal("100.1234567890123456789012345")
    assert observation.exact_ohlcv.close == Decimal("100.2345678901234567890123456")
    converted = bridge().to_snapshot_bar(
        observation,
        security_id="synthetic:001",
        acquisition_id="synthetic-bars",
        mocked=True,
    )
    assert converted.open == Decimal("100.1234567890123456789012345")
    assert converted.close == Decimal("100.2345678901234567890123456")
    assert converted.volume == Decimal(1200)
    assert converted.availability_basis == "synthetic"
    assert converted.security_id == "synthetic:001"
    assert converted.acquisition_id == "synthetic-bars"
    assert converted.date.isoformat() == "2025-03-10"


@pytest.mark.parametrize("assumed", [False, True])
def test_nonmocked_conversion_preserves_availability_evidence(assumed: bool) -> None:
    policy = (
        BarAvailabilityPolicy(
            mode="assumed_close_plus_delay",
            delay_seconds=60,
            rationale="Original synthetic branch test",
        )
        if assumed
        else None
    )
    observation = normalized(acquire(), availability=policy)
    converted = bridge().to_snapshot_bar(
        observation,
        security_id="test:001",
        acquisition_id="test-bars",
        mocked=False,
    )
    assert converted.availability_basis == ("assumed" if assumed else "observed")
    assert converted.available_at == observation.available_at


def test_receipt_keeps_exact_query_hashes_and_disabled_symbol_mapping_marker() -> None:
    acquisition = acquire()
    receipt = bridge().to_acquisition_provenance(
        acquisition,
        acquisition_id="synthetic-bars",
        mocked=True,
    )
    assert receipt.provider == "synthetic" and receipt.mocked
    assert receipt.asof == "-"
    assert receipt.feed == "sip" and receipt.currency == "USD"
    assert receipt.adjustment == "raw" and receipt.timeframe == "1Day"
    assert receipt.page_sha256 == (hashlib.sha256(EXACT_BODY).hexdigest(),)
    expected_query = {
        "adjustment": "raw",
        "asof": "-",
        "currency": "USD",
        "feed": "sip",
        "end": "2025-03-11T03:59:59.999999Z",
        "limit": "10000",
        "sort": "asc",
        "start": "2025-03-10T04:00:00Z",
        "symbols": "AAPL",
        "timeframe": "1Day",
    }
    assert dict(receipt.query_parameters) == expected_query
    literal_hash = hashlib.sha256(
        json.dumps(expected_query, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert receipt.page_query_sha256 == (literal_hash,)
    real_branch = bridge().to_acquisition_provenance(
        acquisition,
        acquisition_id="test-bars",
        mocked=False,
    )
    assert real_branch.provider == "alpaca" and not real_branch.mocked


def test_iex_receipt_preserves_feed_and_rejects_sip_query_substitution() -> None:
    acquisition = acquire(feed="iex")
    receipt = bridge().to_acquisition_provenance(
        acquisition, acquisition_id="test-iex", mocked=False
    )
    assert receipt.feed == "iex"
    assert dict(receipt.query_parameters)["feed"] == "iex"
    changed = receipt.model_dump()
    changed["feed"] = "sip"
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="query_parameter_mismatch"):
        type(receipt).model_validate(changed)


def test_action_receipt_does_not_invent_feed_currency_or_symbol_mapping_query() -> None:
    acquisition = AlpacaHistoricalAcquirer(
        transport=Transport(
            b'{"corporate_actions":{},"next_page_token":null}',
        ),
        clock=lambda: NOW,
    ).fetch_actions(
        CorporateActionsRequest(
            provider="alpaca",
            symbols=("AAPL",),
            start="2025-03-01",
            end="2025-03-31",
            types="all",
        )
    )
    receipt = bridge().to_acquisition_provenance(
        acquisition,
        acquisition_id="synthetic-actions",
        mocked=True,
    )
    assert receipt.feed is None and receipt.currency is None and receipt.asof is None
    assert receipt.action_scope == "all"
    assert dict(receipt.query_parameters) == {
        "data_quality": "complete",
        "end": "2025-03-31",
        "limit": "1000",
        "region": "us",
        "sort": "asc",
        "start": "2025-03-01",
        "symbols": "AAPL",
    }


def test_action_receipt_preserves_explicit_all_quality_inventory() -> None:
    acquisition = AlpacaHistoricalAcquirer(
        transport=Transport(b'{"corporate_actions":{},"next_page_token":null}'),
        clock=lambda: NOW,
    ).fetch_actions(
        CorporateActionsRequest(
            provider="alpaca", symbols=("AAPL",), start="2025-03-01", end="2025-03-31",
            types="all", data_quality="all",
        )
    )
    receipt = bridge().to_acquisition_provenance(
        acquisition, acquisition_id="all-quality-actions", mocked=False,
    )
    assert dict(receipt.query_parameters)["data_quality"] == "all"
    assert receipt.action_scope == "all"


def test_filtered_action_receipt_cannot_certify_complete_inventory() -> None:
    acquisition = AlpacaHistoricalAcquirer(
        transport=Transport(
            b'{"corporate_actions":{},"next_page_token":null}',
        ),
        clock=lambda: NOW,
    ).fetch_actions(
        CorporateActionsRequest(
            provider="alpaca",
            symbols=("AAPL",),
            start="2025-03-01",
            end="2025-03-31",
            types=("cash_dividend",),
        )
    )
    with pytest.raises(bridge().HistoricalNormalizationError, match="filtered_action_inventory"):
        bridge().to_acquisition_provenance(acquisition, acquisition_id="test", mocked=True)


@pytest.mark.parametrize("mutation", ["unfinished", "wrong_query", "extra_page", "empty"])
def test_manually_constructed_acquisition_must_prove_query_and_completed_chain(
    mutation: str,
) -> None:
    acquisition = acquire()
    first = acquisition.pages[0]
    if mutation == "unfinished":
        page = replace(
            first, body=EXACT_BODY.replace(b'"next_page_token":null', b'"next_page_token":"next"')
        )
        changed = replace(acquisition, pages=(page,))
    elif mutation == "wrong_query":
        changed = replace(
            acquisition,
            pages=(
                replace(
                    first, query=tuple((k, "iex" if k == "feed" else v) for k, v in first.query)
                ),
            ),
        )
    elif mutation == "extra_page":
        changed = replace(acquisition, pages=(first, first))
    else:
        changed = replace(acquisition, pages=())
    with pytest.raises(bridge().HistoricalNormalizationError):
        bridge().to_acquisition_provenance(changed, acquisition_id="test", mocked=True)


def test_paginated_query_chain_hashes_tokens_without_storing_them_in_base_query() -> None:
    page1 = b'{"bars":{},"next_page_token":"opaque-next"}'
    acquisition = AlpacaHistoricalAcquirer(
        transport=Transport(page1, EXACT_BODY), clock=lambda: NOW
    ).fetch_bars(request())
    receipt = bridge().to_acquisition_provenance(
        acquisition,
        acquisition_id="synthetic-bars",
        mocked=True,
    )
    assert len(receipt.page_query_sha256) == 2
    assert receipt.page_query_sha256[0] != receipt.page_query_sha256[1]
    assert "page_token" not in dict(receipt.query_parameters)
    broken = replace(
        acquisition.pages[1],
        query=tuple(
            (k, "other-token" if k == "page_token" else v) for k, v in acquisition.pages[1].query
        ),
    )
    with pytest.raises(bridge().HistoricalNormalizationError, match="invalid_pagination_chain"):
        bridge().to_acquisition_provenance(
            replace(acquisition, pages=(acquisition.pages[0], broken)),
            acquisition_id="test",
            mocked=True,
        )


def test_bridge_values_do_not_depend_on_provider_page_boundaries_or_row_order() -> None:
    first_row = {"t": "2025-03-10T04:00:00Z", "o": 10, "h": 11, "l": 9, "c": 10, "v": 100}
    combined = json.dumps(
        {"bars": {"SPY": [first_row], "AAPL": [first_row]}, "next_page_token": None}
    ).encode()
    pages = (
        json.dumps({"bars": {"AAPL": [first_row]}, "next_page_token": "next"}).encode(),
        json.dumps({"bars": {"SPY": [first_row]}, "next_page_token": None}).encode(),
    )
    acquisitions = [
        AlpacaHistoricalAcquirer(transport=Transport(*bodies), clock=lambda: NOW).fetch_bars(
            request(symbols=["SPY", "AAPL"])
        )
        for bodies in ((combined,), pages)
    ]
    converted = []
    for acquisition in acquisitions:
        observations = normalize_historical_bars(
            acquisition,
            sessions=(
                MarketSession(
                    date="2025-03-10",
                    open_at="2025-03-10T13:30Z",
                    close_at="2025-03-10T20:00Z",
                ),
            ),
            missing_policy="error",
        ).bars
        converted.append(
            tuple(
                bridge().to_snapshot_bar(
                    row,
                    security_id="synthetic:" + row.bar.symbol,
                    acquisition_id="same-id",
                    mocked=True,
                )
                for row in observations
            )
        )
    assert converted[0] == converted[1]


def test_adjusted_provider_values_cannot_become_raw_execution_records() -> None:
    acquisition = acquire(adjustment="all")
    with pytest.raises(bridge().HistoricalNormalizationError, match="raw_execution_required"):
        bridge().to_snapshot_bar(
            normalized(acquisition), security_id="test", acquisition_id="test", mocked=True
        )
    with pytest.raises(bridge().HistoricalNormalizationError, match="raw_execution_required"):
        bridge().to_acquisition_provenance(acquisition, acquisition_id="test", mocked=True)


def test_exact_ohlc_rejects_invalid_range_hidden_by_binary_float_rounding() -> None:
    body = (
        b'{"bars":{"AAPL":[{"t":"2025-03-10T04:00:00Z",'
        b'"o":100.0000000000000000002,"h":100.0000000000000000001,"l":99,'
        b'"c":100,"v":1200}]},"next_page_token":null}'
    )
    from packages.data.alpaca_historical import HistoricalAcquisitionError

    with pytest.raises(HistoricalAcquisitionError, match="invalid_ohlcv"):
        normalized(acquire(body))


@pytest.mark.parametrize("change", ["future", "before_request", "naive", "unfinished_clock"])
def test_receipt_checks_page_observation_times_before_discarding_them(change: str) -> None:
    from datetime import timedelta

    first_body = b'{"bars":{},"next_page_token":"next"}'
    acquisition = AlpacaHistoricalAcquirer(
        transport=Transport(first_body, EXACT_BODY),
        clock=lambda: NOW,
    ).fetch_bars(request())
    first, last = acquisition.pages
    first = replace(first, received_at=NOW - timedelta(seconds=1))
    started = NOW - timedelta(seconds=2)
    if change == "future":
        first = replace(first, received_at=NOW + timedelta(seconds=1))
    elif change == "before_request":
        first = replace(first, received_at=NOW - timedelta(seconds=3))
    elif change == "naive":
        first = replace(first, received_at=NOW.replace(tzinfo=None))
    else:
        last = replace(last, received_at=NOW - timedelta(seconds=1))
    changed = replace(acquisition, request_started_at=started, pages=(first, last))
    with pytest.raises(bridge().HistoricalNormalizationError, match="invalid_acquisition_times"):
        bridge().to_acquisition_provenance(changed, acquisition_id="test", mocked=True)


def test_receipt_rejects_page_clock_regression_inside_valid_acquisition_bounds() -> None:
    from datetime import timedelta

    acquisition = AlpacaHistoricalAcquirer(
        transport=Transport(
            b'{"bars":{},"next_page_token":"one"}',
            b'{"bars":{},"next_page_token":"two"}',
            EXACT_BODY,
        ),
        clock=lambda: NOW,
    ).fetch_bars(request())
    pages = (
        replace(acquisition.pages[0], received_at=NOW - timedelta(seconds=2)),
        replace(acquisition.pages[1], received_at=NOW - timedelta(seconds=3)),
        acquisition.pages[2],
    )
    with pytest.raises(bridge().HistoricalNormalizationError, match="invalid_acquisition_times"):
        bridge().to_acquisition_provenance(
            replace(acquisition, request_started_at=NOW - timedelta(seconds=10), pages=pages),
            acquisition_id="test",
            mocked=True,
        )


def test_receipt_rejects_ambiguous_duplicate_json_pagination_keys() -> None:
    acquisition = acquire()
    changed = replace(
        acquisition,
        pages=(
            replace(
                acquisition.pages[0],
                body=(b'{"bars":{},"next_page_token":"more","next_page_token":null}'),
            ),
        ),
    )
    with pytest.raises(bridge().HistoricalNormalizationError, match="invalid_pagination_chain"):
        bridge().to_acquisition_provenance(changed, acquisition_id="test", mocked=True)

"""Synthetic HTTP fixtures for the explicit historical-only acquisition boundary."""

from __future__ import annotations

import hashlib
import importlib
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from packages.data.snapshots import MarketSession

NOW = datetime(2025, 4, 1, 12, tzinfo=UTC)


def api() -> Any:
    return importlib.import_module("packages.data.alpaca_historical")


def request(**changes: object) -> Any:
    return api().HistoricalBarsRequest.model_validate(
        {
            "provider": "alpaca",
            "feed": "sip",
            "adjustment": "raw",
            "timeframe": "1Day",
            "symbols": ["SPY", "AAPL"],
            "start": "2025-03-07",
            "end": "2025-03-10",
            **changes,
        }
    )


def response(payload: object, status: int = 200, **headers: str) -> Any:
    return api().HttpResponse(status, headers, json.dumps(payload).encode())


class Transport:
    def __init__(self, *responses: Any) -> None:
        self.responses = iter(responses)
        self.requests: list[tuple[str, dict[str, str], float]] = []

    def get(self, endpoint: str, params: Mapping[str, str], timeout_seconds: float) -> Any:
        self.requests.append((endpoint, dict(params), timeout_seconds))
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item


def acquire(transport: Transport, **changes: object) -> Any:
    return (
        api()
        .AlpacaHistoricalAcquirer(transport=transport, clock=lambda: NOW)
        .fetch_bars(request(**changes))
    )


def bar(timestamp: str, **changes: object) -> dict[str, object]:
    return {
        "t": timestamp,
        "o": 100,
        "h": 110,
        "l": 90,
        "c": 105,
        "v": 1200,
        "n": 100,
        "vw": 102.5,
        **changes,
    }


def sessions() -> tuple[MarketSession, ...]:
    return (
        MarketSession(date="2025-03-07", open_at="2025-03-07T14:30Z", close_at="2025-03-07T21:00Z"),
        MarketSession(date="2025-03-10", open_at="2025-03-10T13:30Z", close_at="2025-03-10T20:00Z"),
    )


def test_multi_symbol_global_pagination_and_new_york_date_boundaries() -> None:
    transport = Transport(
        response({"bars": {"AAPL": [bar("2025-03-07T05:00:00Z")]}, "next_page_token": "next"}),
        response({"bars": {}, "next_page_token": "last"}),
        response({"bars": {"SPY": [bar("2025-03-10T04:00:00Z")]}, "next_page_token": None}),
    )
    result = acquire(transport)
    assert len(result.pages) == 3
    assert result.request_started_at == NOW == result.acquired_at
    endpoint, params, timeout = transport.requests[0]
    assert endpoint == "https://data.alpaca.markets/v2/stocks/bars"
    assert params == {
        "symbols": "AAPL,SPY",
        "feed": "sip",
        "adjustment": "raw",
        "timeframe": "1Day",
        "start": "2025-03-07T05:00:00Z",
        "end": "2025-03-11T03:59:59.999999Z",
        "limit": "10000",
        "sort": "asc",
        "currency": "USD",
        "asof": "-",
    }
    assert timeout > 0
    assert [r[1].get("page_token") for r in transport.requests] == [None, "next", "last"]
    assert result.pages[0].sha256 == hashlib.sha256(result.pages[0].body).hexdigest()
    assert dict(result.pages[1].query)["page_token"] == "next"


@pytest.mark.parametrize(
    "changes",
    [
        {"feed": "boats"},
        {"feed": None},
        {"provider": "other"},
        {"timeframe": "1Min"},
        {"adjustment": None},
        {"symbols": []},
        {"symbols": ["SPY", "SPY"]},
        {"symbols": ["spy"]},
        {"symbols": ["SPY&feed=iex"]},
        {"end": "2025-03-06"},
    ],
)
def test_explicit_supported_requests_reject_ambiguous_inputs(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        request(**changes)


def test_iex_is_explicit_and_preserved_through_query_and_observation() -> None:
    transport = Transport(
        response({"bars": {"AAPL": [bar("2025-03-07T05:00:00Z")]}, "next_page_token": None})
    )
    acquisition = acquire(transport, feed="iex")
    observation = api().normalize_historical_bars(
        acquisition, sessions=sessions(), missing_policy="exclude"
    ).bars[0]
    assert acquisition.request.feed == "iex"
    assert transport.requests[0][1]["feed"] == "iex"
    assert observation.feed == "iex"


def test_iex_entitlement_failure_never_substitutes_sip() -> None:
    transport = Transport(response({"message": "private account"}, 403))
    with pytest.raises(api().HistoricalAcquisitionError, match="forbidden"):
        acquire(transport, feed="iex")
    assert [item[1]["feed"] for item in transport.requests] == ["iex"]


def test_successful_rate_header_and_retry_after_are_honored() -> None:
    transport = Transport(
        response({}, 429, **{"Retry-After": "2"}),
        response(
            {"bars": {}, "next_page_token": "a"},
            **{"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(NOW.timestamp()) + 3)},
        ),
        response({"bars": {}, "next_page_token": None}),
    )
    waits: list[float] = []
    result = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=transport,
            clock=lambda: NOW,
            sleep=waits.append,
        )
        .fetch_bars(request())
    )
    assert len(result.pages) == 2
    assert waits == [2, 3]


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "authentication_failed"),
        (403, "forbidden"),
        (400, "invalid_request"),
        (302, "redirect_rejected"),
    ],
)
def test_provider_failures_are_sanitized_without_feed_fallback(status: int, code: str) -> None:
    transport = Transport(response({"message": "SECRET private account", "code": 123}, status))
    with pytest.raises(api().HistoricalAcquisitionError) as error:
        acquire(transport)
    assert error.value.code == code
    assert "SECRET" not in str(error.value)
    assert len(transport.requests) == 1
    assert transport.requests[0][1]["feed"] == "sip"


def test_transport_failures_retry_boundedly_and_do_not_echo_credentials() -> None:
    waits: list[float] = []
    transport = Transport(*(OSError("SECRET private URL") for _ in range(3)))
    with pytest.raises(api().HistoricalAcquisitionError) as error:
        api().AlpacaHistoricalAcquirer(
            transport=transport,
            clock=lambda: NOW,
            sleep=waits.append,
            retry=api().RetryPolicy(max_attempts=3),
        ).fetch_bars(request())
    assert error.value.code == "transport_failed"
    assert waits == [1, 2]
    assert len(transport.requests) == 3
    assert "SECRET" not in str(error.value)
    assert error.value.__suppress_context__


def test_server_retry_hint_exceeding_budget_fails_without_early_retry() -> None:
    waits: list[float] = []
    transport = Transport(response({}, 429, **{"Retry-After": "99999"}))
    with pytest.raises(api().HistoricalAcquisitionError, match="retry_budget_exceeded"):
        api().AlpacaHistoricalAcquirer(
            transport=transport,
            clock=lambda: NOW,
            sleep=waits.append,
        ).fetch_bars(request())
    assert waits == []
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"bars": {}, "next_page_token": "repeat"}, "pagination_cycle"),
        ({"bars": {}, "next_page_token": 1}, "invalid_page"),
    ],
)
def test_invalid_pagination_fails_closed(payload: object, code: str) -> None:
    transport = Transport(response(payload), response(payload))
    with pytest.raises(api().HistoricalAcquisitionError, match=code):
        acquire(transport)


def test_normalization_sorts_sessions_and_preserves_observed_availability() -> None:
    result = acquire(
        Transport(
            response(
                {
                    "bars": {
                        "SPY": [bar("2025-03-10T04:00:00Z"), bar("2025-03-07T05:00:00Z")],
                        "AAPL": [bar("2025-03-10T04:00:00Z"), bar("2025-03-07T05:00:00Z")],
                    },
                    "next_page_token": None,
                }
            )
        )
    )
    normalized = api().normalize_historical_bars(
        result, sessions=sessions(), missing_policy="error"
    )
    assert [(x.bar.symbol, x.bar.date.isoformat()) for x in normalized.bars] == [
        ("AAPL", "2025-03-07"),
        ("AAPL", "2025-03-10"),
        ("SPY", "2025-03-07"),
        ("SPY", "2025-03-10"),
    ]
    assert all(x.available_at == NOW == x.acquired_at for x in normalized.bars)
    assert all(
        x.availability_basis == "observed" and x.adjustment == "raw" and not x.bar.adjusted
        for x in normalized.bars
    )
    assert normalized.bars[0].provider_timestamp == datetime(2025, 3, 7, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    "record,code",
    [
        (bar("2025-03-07T00:00:00Z"), "invalid_bar_timestamp"),
        (bar("2025-03-07T05:00:00"), "invalid_bar_timestamp"),
        (bar("2025-03-07T05:00:00Z", c=float("nan")), "invalid_ohlcv"),
        (bar("2025-03-07T05:00:00Z", v=1.5), "invalid_ohlcv"),
        (bar("2025-03-07T05:00:00Z", l=120), "invalid_ohlcv"),
        (bar("2025-03-08T05:00:00Z"), "unexpected_session"),
    ],
)
def test_bad_daily_bars_are_rejected(record: object, code: str) -> None:
    result = acquire(Transport(response({"bars": {"AAPL": [record]}, "next_page_token": None})))
    with pytest.raises(api().HistoricalAcquisitionError, match=code):
        api().normalize_historical_bars(result, sessions=sessions(), missing_policy="error")


def test_duplicate_and_missing_sessions_are_not_silently_filled() -> None:
    result = acquire(
        Transport(
            response({"bars": {"AAPL": [bar("2025-03-07T05:00:00Z")]}, "next_page_token": None})
        )
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="missing_sessions"):
        api().normalize_historical_bars(result, sessions=sessions(), missing_policy="error")
    normalized = api().normalize_historical_bars(
        result, sessions=sessions(), missing_policy="exclude"
    )
    assert [(x.symbol, x.session_date.isoformat()) for x in normalized.exclusions] == [
        ("AAPL", "2025-03-10"),
        ("SPY", "2025-03-07"),
        ("SPY", "2025-03-10"),
    ]
    duplicate = acquire(
        Transport(
            response({"bars": {"AAPL": [bar("2025-03-07T05:00:00Z")] * 2}, "next_page_token": None})
        )
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="duplicate_session"):
        api().normalize_historical_bars(duplicate, sessions=sessions(), missing_policy="exclude")


def test_reconstructed_availability_is_explicit_and_never_before_close() -> None:
    result = acquire(
        Transport(
            response({"bars": {"AAPL": [bar("2025-03-07T05:00:00Z")]}, "next_page_token": None})
        ),
        adjustment="all",
    )
    normalized = api().normalize_historical_bars(
        result,
        sessions=sessions(),
        missing_policy="exclude",
        availability=api().BarAvailabilityPolicy(
            mode="assumed_close_plus_delay",
            delay_seconds=60,
            rationale="Synthetic test assumption, not provider first-publication evidence",
        ),
    )
    row = normalized.bars[0]
    assert row.available_at == datetime(2025, 3, 7, 21, 1, tzinfo=UTC)
    assert row.availability_basis == "assumed"
    assert row.adjustment == "all" and row.bar.adjusted
    assert "adjusted_prices_are_not_point_in_time" in normalized.warnings


class Opened(BytesIO):
    status = 200
    headers: Mapping[str, str] = {"content-type": "application/json"}


def test_concrete_transport_uses_allowlisted_get_with_no_proxy_or_redirects() -> None:
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.return_value = Opened(b'{"bars":{},"next_page_token":null}')
        transport = api().UrllibHistoricalTransport(api_key="FAKE_KEY", secret_key="FAKE_SECRET")
        result = transport.get("https://data.alpaca.markets/v2/stocks/bars", {"feed": "sip"}, 5)
        assert result.status_code == 200
        sent = build.return_value.open.call_args.args[0]
        assert sent.get_method() == "GET"
        assert sent.full_url == "https://data.alpaca.markets/v2/stocks/bars?feed=sip"
        assert sent.get_header("Apca-api-key-id") == "FAKE_KEY"
        assert build.return_value.open.call_args.kwargs == {"timeout": 5}
        handlers = build.call_args.args
        assert any(isinstance(h, urllib.request.ProxyHandler) and h.proxies == {} for h in handlers)
        redirect = next(h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
        with pytest.raises(api().HistoricalAcquisitionError, match="redirect_rejected"):
            redirect.redirect_request(sent, None, 302, "", {}, "https://evil.example")
    assert "FAKE_SECRET" not in repr(transport)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://data.alpaca.markets/v2/stocks/bars",
        "https://evil.example/v2/stocks/bars",
        "https://data.alpaca.markets/v2/orders",
        "https://data.alpaca.markets/v2/stocks/bars?bad=1",
    ],
)
def test_concrete_transport_rejects_nonallowlisted_endpoints(endpoint: str) -> None:
    with patch("urllib.request.build_opener") as build:
        transport = api().UrllibHistoricalTransport(api_key="FAKE_KEY", secret_key="FAKE_SECRET")
        with pytest.raises(api().HistoricalAcquisitionError, match="endpoint_rejected"):
            transport.get(endpoint, {}, 5)
        build.return_value.open.assert_not_called()


def test_concrete_transport_caps_success_and_error_bodies() -> None:
    with patch("urllib.request.build_opener") as build:
        transport = api().UrllibHistoricalTransport(
            api_key="FAKE_KEY",
            secret_key="FAKE_SECRET",
            max_body_bytes=10,
        )
        build.return_value.open.return_value = Opened(b"x" * 11)
        with pytest.raises(api().HistoricalAcquisitionError, match="body_limit_exceeded"):
            transport.get("https://data.alpaca.markets/v2/stocks/bars", {}, 5)
        build.return_value.open.side_effect = urllib.error.HTTPError(
            "https://data.alpaca.markets/v2/stocks/bars",
            403,
            "SECRET",
            {},
            BytesIO(b"private"),
        )
        error_response = transport.get("https://data.alpaca.markets/v2/stocks/bars", {}, 5)
        assert error_response.status_code == 403
        assert error_response.body == b"private"


def action_request(**changes: object) -> Any:
    return api().CorporateActionsRequest.model_validate(
        {
            "provider": "alpaca",
            "symbols": ["AAPL"],
            "start": "2025-03-01",
            "end": "2025-03-31",
            "types": ["forward_split", "reverse_split", "cash_dividend"],
            **changes,
        }
    )


def test_all_quality_action_inventory_is_explicit_and_preserved_in_wire_query() -> None:
    transport = Transport(response({"corporate_actions": {}, "next_page_token": None}))
    acquired = api().AlpacaHistoricalAcquirer(transport=transport, clock=lambda: NOW).fetch_actions(
        action_request(types="all", data_quality="all")
    )
    assert acquired.request.data_quality == "all"
    assert transport.requests[0][1]["data_quality"] == "all"
    assert "types" not in transport.requests[0][1]


def test_corporate_action_process_window_and_exact_cash_and_split_normalization() -> None:
    transport = Transport(
        response(
            {
                "corporate_actions": {
                    "forward_splits": [
                        {
                            "id": "split-1",
                            "symbol": "AAPL",
                            "cusip": "synthetic",
                            "new_rate": 3.0,
                            "old_rate": 2.0,
                            "process_date": "2025-03-11",
                            "ex_date": "2025-03-10",
                        }
                    ],
                    "cash_dividends": [
                        {
                            "id": "cash-1",
                            "symbol": "AAPL",
                            "cusip": "synthetic",
                            "rate": 0.12,
                            "special": False,
                            "foreign": False,
                            "process_date": "2025-03-12",
                            "ex_date": "2025-03-11",
                            "payable_date": "2025-03-20",
                        }
                    ],
                },
                "next_page_token": None,
            }
        )
    )
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(transport=transport, clock=lambda: NOW)
        .fetch_actions(action_request())
    )
    assert transport.requests[0][0] == "https://data.alpaca.markets/v1/corporate-actions"
    params = transport.requests[0][1]
    assert params["start"] == "2025-03-01" and params["end"] == "2025-03-31"
    assert "feed" not in params and params["data_quality"] == "complete"
    actions = api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})
    assert [(x.kind, x.security_id) for x in actions] == [
        ("split", "US-AAPL"),
        ("cash_dividend", "US-AAPL"),
    ]
    assert (actions[0].numerator, actions[0].denominator) == (3, 2)
    assert actions[1].cash_per_share == Decimal("0.12")
    assert actions[1].pay_date == date(2025, 3, 20)
    assert all(x.available_at == NOW and x.availability_basis == "observed" for x in actions)


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"payable_date": None}, "invalid_corporate_action"),
        ({"foreign": True}, "unsupported_corporate_action"),
        ({"process_date": "2025-04-01"}, "action_outside_process_window"),
    ],
)
def test_incomplete_or_unsupported_corporate_actions_fail(
    changes: dict[str, object], code: str
) -> None:
    record = {
        "id": "cash",
        "symbol": "AAPL",
        "cusip": "synthetic",
        "rate": 1,
        "special": False,
        "foreign": False,
        "process_date": "2025-03-12",
        "ex_date": "2025-03-10",
        "payable_date": "2025-03-20",
        **changes,
    }
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {"cash_dividends": [record]},
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    with pytest.raises(api().HistoricalAcquisitionError, match=code):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


@pytest.mark.parametrize("new_rate,old_rate", [(-3, -2), (3, -2), (0, 2), (3, 0)])
def test_split_rates_must_be_positive_before_forming_ratio(new_rate: int, old_rate: int) -> None:
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {
                            "forward_splits": [
                                {
                                    "id": "split-1",
                                    "symbol": "AAPL",
                                    "new_rate": new_rate,
                                    "old_rate": old_rate,
                                    "process_date": "2025-03-11",
                                    "ex_date": "2025-03-10",
                                }
                            ]
                        },
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="invalid_corporate_action"):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


def test_http_error_body_limit_does_not_expose_chained_provider_messages() -> None:
    import traceback

    with patch("urllib.request.build_opener") as build:
        transport = api().UrllibHistoricalTransport(
            api_key="FAKE_KEY",
            secret_key="FAKE_SECRET",
            max_body_bytes=2,
        )
        build.return_value.open.side_effect = urllib.error.HTTPError(
            "https://data.alpaca.markets/v2/stocks/bars",
            403,
            "SECRET_MESSAGE",
            {},
            BytesIO(b"private body"),
        )
        with pytest.raises(api().HistoricalAcquisitionError, match="body_limit_exceeded") as error:
            transport.get("https://data.alpaca.markets/v2/stocks/bars", {}, 5)
    rendered = "".join(traceback.format_exception(error.value))
    assert "HTTP Error 403: SECRET_MESSAGE" not in rendered


def test_server_errors_exhaust_retry_and_http_date_wait_is_bounded() -> None:
    transport = Transport(
        response({}, 503, **{"Retry-After": "Tue, 01 Apr 2025 12:00:03 GMT"}),
        response({}, 503),
        response({}, 503),
    )
    waits: list[float] = []
    with pytest.raises(api().HistoricalAcquisitionError, match="provider_failed"):
        api().AlpacaHistoricalAcquirer(
            transport=transport,
            clock=lambda: NOW,
            sleep=waits.append,
        ).fetch_bars(request())
    assert waits == [3, 2]
    assert len(transport.requests) == 3


def test_page_limit_and_total_wait_limits_stop_further_requests() -> None:
    transport = Transport(response({"bars": {}, "next_page_token": "a"}))
    with pytest.raises(api().HistoricalAcquisitionError, match="page_limit_exceeded"):
        api().AlpacaHistoricalAcquirer(transport=transport, clock=lambda: NOW).fetch_bars(
            request(max_pages=1)
        )
    limited = Transport(response({}, 429), response({}, 429))
    with pytest.raises(api().HistoricalAcquisitionError, match="retry_budget_exceeded"):
        api().AlpacaHistoricalAcquirer(
            transport=limited,
            clock=lambda: NOW,
            sleep=lambda _: None,
            retry=api().RetryPolicy(max_total_wait_seconds=1),
        ).fetch_bars(request())
    assert len(limited.requests) == 2


def test_action_pagination_and_missing_identity_are_explicit() -> None:
    transport = Transport(
        response({"corporate_actions": {}, "next_page_token": "ca-next"}),
        response(
            {
                "corporate_actions": {
                    "reverse_splits": [
                        {
                            "id": "rev",
                            "symbol": "AAPL",
                            "new_rate": 1,
                            "old_rate": 10,
                            "process_date": "2025-03-11",
                            "ex_date": "2025-03-10",
                        }
                    ]
                },
                "next_page_token": None,
            }
        ),
    )
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(transport=transport, clock=lambda: NOW)
        .fetch_actions(action_request())
    )
    assert transport.requests[1][1]["page_token"] == "ca-next"
    with pytest.raises(api().HistoricalAcquisitionError, match="unknown_security_identity"):
        api().normalize_corporate_actions(acquired, security_ids={})
    actions = api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})
    assert (actions[0].numerator, actions[0].denominator) == (1, 10)


def test_invalid_json_and_unexpected_symbols_fail_without_provider_payload() -> None:
    transport = Transport(api().HttpResponse(200, {}, b"not-json SECRET"))
    with pytest.raises(api().HistoricalAcquisitionError, match="invalid_json"):
        acquire(transport)
    acquired = acquire(Transport(response({"bars": {"OTHER": []}, "next_page_token": None})))
    with pytest.raises(api().HistoricalAcquisitionError, match="unexpected_symbol"):
        api().normalize_historical_bars(acquired, sessions=sessions(), missing_policy="exclude")


def test_error_stream_read_failure_is_sanitized() -> None:
    class BrokenStream(BytesIO):
        def read(self, size: int = -1) -> bytes:
            raise OSError("SECRET_STREAM_FAILURE")

    with patch("urllib.request.build_opener") as build:
        transport = api().UrllibHistoricalTransport(api_key="FAKE_KEY", secret_key="FAKE_SECRET")
        build.return_value.open.side_effect = urllib.error.HTTPError(
            "https://data.alpaca.markets/v2/stocks/bars",
            503,
            "SECRET_HTTP_ERROR",
            {},
            BrokenStream(),
        )
        with pytest.raises(api().HistoricalAcquisitionError, match="transport_failed") as error:
            transport.get("https://data.alpaca.markets/v2/stocks/bars", {}, 5)
        assert "SECRET" not in str(error.value)
        assert error.value.__suppress_context__


def test_deep_invalid_json_is_reported_as_sanitized_provider_failure() -> None:
    transport = Transport(api().HttpResponse(200, {}, ("[" * 2000 + "0" + "]" * 1999).encode()))
    with pytest.raises(api().HistoricalAcquisitionError, match="invalid_json"):
        acquire(transport)


def test_split_ratio_numeric_size_is_bounded_before_fraction_conversion() -> None:
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {
                            "forward_splits": [
                                {
                                    "id": "split-1",
                                    "symbol": "AAPL",
                                    "new_rate": "1e10000",
                                    "old_rate": "1",
                                    "process_date": "2025-03-11",
                                    "ex_date": "2025-03-10",
                                }
                            ]
                        },
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="invalid_corporate_action"):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


def test_all_action_inventory_query_omits_filter_and_rejects_unsupported_events() -> None:
    transport = Transport(
        response(
            {
                "corporate_actions": {
                    "spin_offs": [
                        {
                            "id": "spin-1",
                            "source_symbol": "AAPL",
                            "new_symbol": "OTHER",
                            "process_date": "2025-03-11",
                            "ex_date": "2025-03-10",
                        }
                    ]
                },
                "next_page_token": None,
            }
        )
    )
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(transport=transport, clock=lambda: NOW)
        .fetch_actions(action_request(types="all"))
    )
    assert "types" not in transport.requests[0][1]
    assert "corporate_action_inventory_filtered" not in acquired.warnings
    assert "process_date_window_does_not_certify_ex_date_coverage" in acquired.warnings
    with pytest.raises(api().HistoricalAcquisitionError, match="unsupported_corporate_action"):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


def test_filtered_actions_explicitly_warn_inventory_is_incomplete() -> None:
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {},
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    assert "corporate_action_inventory_filtered" in acquired.warnings


def test_http_error_close_failure_is_sanitized_and_close_attempted_once() -> None:
    class FailingClose(BytesIO):
        close_calls = 0

        def close(self) -> None:
            if self.closed:
                return
            self.close_calls += 1
            super().close()
            raise OSError("SECRET_CLOSE_ERROR")

    stream = FailingClose(b"provider failure")
    with patch("urllib.request.build_opener") as build:
        transport = api().UrllibHistoricalTransport(api_key="FAKE_KEY", secret_key="FAKE_SECRET")
        build.return_value.open.side_effect = urllib.error.HTTPError(
            "https://data.alpaca.markets/v2/stocks/bars",
            403,
            "SECRET_PROVIDER_ERROR",
            {},
            stream,
        )
        with pytest.raises(api().HistoricalAcquisitionError, match="transport_failed") as error:
            transport.get("https://data.alpaca.markets/v2/stocks/bars", {}, 5)
    assert "SECRET" not in str(error.value)
    assert error.value.__suppress_context__
    assert stream.close_calls == 1


@pytest.mark.parametrize(
    "category,new_rate,old_rate",
    [
        ("forward_splits", 1, 10),
        ("reverse_splits", 10, 1),
    ],
)
def test_split_category_must_match_ratio_direction(
    category: str,
    new_rate: int,
    old_rate: int,
) -> None:
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {
                            category: [
                                {
                                    "id": "split-1",
                                    "symbol": "AAPL",
                                    "new_rate": new_rate,
                                    "old_rate": old_rate,
                                    "process_date": "2025-03-11",
                                    "ex_date": "2025-03-10",
                                }
                            ]
                        },
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="invalid_corporate_action"):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


def test_cash_currency_must_not_override_explicit_non_usd_provider_value() -> None:
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {
                            "cash_dividends": [
                                {
                                    "id": "cash-1",
                                    "symbol": "AAPL",
                                    "rate": 1,
                                    "special": False,
                                    "foreign": False,
                                    "currency": "EUR",
                                    "process_date": "2025-03-12",
                                    "ex_date": "2025-03-10",
                                    "payable_date": "2025-03-20",
                                }
                            ]
                        },
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="unsupported_corporate_action"):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


def test_same_day_split_and_dividend_require_unavailable_share_basis_evidence() -> None:
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {
                            "forward_splits": [
                                {
                                    "id": "split-1",
                                    "symbol": "AAPL",
                                    "new_rate": 3,
                                    "old_rate": 2,
                                    "process_date": "2025-03-11",
                                    "ex_date": "2025-03-10",
                                }
                            ],
                            "cash_dividends": [
                                {
                                    "id": "cash-1",
                                    "symbol": "AAPL",
                                    "rate": 1,
                                    "special": False,
                                    "foreign": False,
                                    "process_date": "2025-03-12",
                                    "ex_date": "2025-03-10",
                                    "payable_date": "2025-03-20",
                                }
                            ],
                        },
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="ambiguous_dividend_share_basis"):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


@pytest.mark.parametrize("rate", ["1e10000", "0.0000000001", "1." + "0" * 100])
def test_provider_cash_rate_has_bounded_exact_decimal_representation(rate: str) -> None:
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {
                            "cash_dividends": [
                                {
                                    "id": "cash-1",
                                    "symbol": "AAPL",
                                    "rate": rate,
                                    "special": False,
                                    "foreign": False,
                                    "process_date": "2025-03-12",
                                    "ex_date": "2025-03-10",
                                    "payable_date": "2025-03-20",
                                }
                            ]
                        },
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="invalid_corporate_action"):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


def test_split_rate_significant_precision_is_bounded_before_fraction_conversion() -> None:
    acquired = (
        api()
        .AlpacaHistoricalAcquirer(
            transport=Transport(
                response(
                    {
                        "corporate_actions": {
                            "forward_splits": [
                                {
                                    "id": "split-1",
                                    "symbol": "AAPL",
                                    "new_rate": "3." + "0" * 100,
                                    "old_rate": "1",
                                    "process_date": "2025-03-11",
                                    "ex_date": "2025-03-10",
                                }
                            ]
                        },
                        "next_page_token": None,
                    }
                )
            ),
            clock=lambda: NOW,
        )
        .fetch_actions(action_request())
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="invalid_corporate_action"):
        api().normalize_corporate_actions(acquired, security_ids={"AAPL": "US-AAPL"})


def test_total_retained_body_budget_bounds_multi_page_acquisition() -> None:
    body = b'{"bars":{},"next_page_token":"next"}'
    transport = Transport(
        api().HttpResponse(200, {}, body),
        response(
            {
                "bars": {},
                "next_page_token": None,
            }
        ),
    )
    with pytest.raises(api().HistoricalAcquisitionError, match="total_body_limit_exceeded"):
        api().AlpacaHistoricalAcquirer(
            transport=transport, clock=lambda: NOW, max_total_body_bytes=len(body)
        ).fetch_bars(request())
    assert len(transport.requests) == 2


@pytest.mark.parametrize(
    "body",
    [
        b'{"bars":{},"next_page_token":"more","next_page_token":null}',
        b'{"bars":{"AAPL":[],"AAPL":[]},"next_page_token":null}',
    ],
)
def test_duplicate_provider_json_keys_are_ambiguous_evidence(body: bytes) -> None:
    with pytest.raises(api().HistoricalAcquisitionError, match="invalid_json"):
        acquire(Transport(api().HttpResponse(200, {}, body)))

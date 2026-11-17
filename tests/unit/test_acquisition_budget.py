"""Session-wide limits using real HTTP readers and original synthetic bodies."""

from __future__ import annotations

import importlib
import urllib.error
from collections.abc import Mapping
from io import BytesIO
from typing import Any
from unittest.mock import patch

import pytest

from packages.data.alpaca_historical import (
    BARS_ENDPOINT,
    AlpacaHistoricalAcquirer,
    HistoricalAcquisitionError,
    HistoricalBarsRequest,
    UrllibHistoricalTransport,
)


def api() -> Any:
    return importlib.import_module("packages.data.acquisition_budget")


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class Opened(BytesIO):
    status = 200

    def __init__(self, body: bytes, *, known_size: bool = True) -> None:
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body))} if known_size else {}
        self.read_sizes: list[int] = []
        self.received = 0

    def read1(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        body = super().read1(size)
        self.received += len(body)
        return body


def make_budget(**changes: Any) -> Any:
    clock = changes.pop("clock", Clock())
    return api().HistoricalSessionBudget(
        monotonic=clock, sleep=clock.sleep, **changes
    )


def concrete(budget: Any, **changes: Any) -> Any:
    return api().BudgetedHistoricalTransport(
        transport=UrllibHistoricalTransport(api_key="FAKE_KEY", secret_key="FAKE_SECRET"),
        budget=budget,
        **changes,
    )


def test_session_records_safe_reservation_before_get_and_accounts_http_status() -> None:
    events: list[Mapping[str, object]] = []
    budget = make_budget(event_callback=events.append)
    opened = Opened(b"hello")
    with patch("urllib.request.build_opener") as build:
        def open_response(*args: object, **kwargs: object) -> Opened:
            assert events[-1]["event"] == "attempt_reserved"
            assert events[-1]["attempt_id"] == 1
            return opened

        build.return_value.open.side_effect = open_response
        transport = concrete(budget)
        response = transport.get(BARS_ENDPOINT, {"page_token": "PRIVATE_TOKEN"}, 10)
    assert response.body == b"hello"
    assert budget.attempts == 1
    assert budget.received_body_bytes == budget.successful_body_bytes == 5
    assert events[0]["endpoint_path"] == "/v2/stocks/bars"
    assert events[0]["request_body_budget"] == 16 * 1024 * 1024
    assert len(str(events[0]["query_sha256"])) == 64
    assert events[-1]["event"] == "attempt_finished"
    assert events[-1]["status_code"] == 200
    assert events[-1]["error_code"] is None
    assert "PRIVATE_TOKEN" not in repr(events)
    assert "FAKE" not in repr(events)


def test_session_counts_retry_error_payloads_and_stops_before_third_actual_get() -> None:
    budget = make_budget(max_attempts=2)
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.side_effect = [
            urllib.error.HTTPError(BARS_ENDPOINT, 503, "PRIVATE", {}, BytesIO(b"bad-one")),
            urllib.error.HTTPError(BARS_ENDPOINT, 503, "PRIVATE", {}, BytesIO(b"bad-two")),
        ]
        transport = concrete(budget)
        request = HistoricalBarsRequest(
            provider="alpaca", feed="iex", adjustment="raw", timeframe="1Day",
            symbols=("SPY",), start="2025-03-10", end="2025-03-10",
        )
        with pytest.raises(HistoricalAcquisitionError, match="session_attempt_limit"):
            AlpacaHistoricalAcquirer(transport=transport, sleep=lambda _: None).fetch_bars(request)
        assert build.return_value.open.call_count == 2
    assert budget.attempts == 2
    assert budget.received_body_bytes == 14
    assert budget.successful_body_bytes == 0


def test_unknown_length_reader_never_reads_probe_byte_beyond_remaining_session_bytes() -> None:
    budget = make_budget(max_received_body_bytes=10)
    opened = Opened(b"x" * 11, known_size=False)
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.return_value = opened
        with pytest.raises(HistoricalAcquisitionError, match="body_limit_exceeded"):
            concrete(budget).get(BARS_ENDPOINT, {}, 10)
    assert opened.read_sizes == [10]
    assert opened.received == 10
    assert budget.received_body_bytes == budget.successful_body_bytes == 10


def test_exact_known_size_can_use_remaining_budget_then_blocks_new_get() -> None:
    budget = make_budget(max_received_body_bytes=10)
    first, second = Opened(b"1234"), Opened(b"567890")
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.side_effect = [first, second]
        transport = concrete(budget)
        assert transport.get(BARS_ENDPOINT, {}, 10).body == b"1234"
        assert transport.get(BARS_ENDPOINT, {}, 10).body == b"567890"
        with pytest.raises(HistoricalAcquisitionError, match="session_byte_limit"):
            transport.get(BARS_ENDPOINT, {}, 10)
        assert build.return_value.open.call_count == 2
    assert second.read_sizes == [6]
    assert budget.received_body_bytes == 10


def test_declared_oversized_body_is_rejected_before_reading_any_payload() -> None:
    budget = make_budget(max_received_body_bytes=10)
    opened = Opened(b"x" * 11)
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.return_value = opened
        with pytest.raises(HistoricalAcquisitionError, match="body_limit_exceeded"):
            concrete(budget).get(BARS_ENDPOINT, {}, 10)
    assert opened.read_sizes == []
    assert budget.attempts == 1 and budget.received_body_bytes == 0


def test_partial_read_failure_retains_bytes_and_status_without_private_error_text() -> None:
    class Partial(Opened):
        def read1(self, size: int = -1) -> bytes:
            if self.received:
                raise OSError("PRIVATE_FAILURE")
            return super().read1(min(size, 4))

    events: list[Mapping[str, object]] = []
    budget = make_budget(event_callback=events.append)
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.return_value = Partial(b"12345678", known_size=False)
        with pytest.raises(HistoricalAcquisitionError, match="transport_failed") as error:
            concrete(budget).get(BARS_ENDPOINT, {}, 10)
    assert budget.received_body_bytes == budget.successful_body_bytes == 4
    assert events[-1]["status_code"] == 200
    assert events[-1]["error_code"] == "transport_failed"
    assert "PRIVATE" not in repr(events)
    assert error.value.__suppress_context__


def test_rate_limit_and_remaining_deadline_clamp_actual_transport_timeout() -> None:
    clock = Clock()
    budget = make_budget(clock=clock, max_elapsed_seconds=1)
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.side_effect = [Opened(b"a"), Opened(b"b")]
        transport = concrete(budget)
        transport.get(BARS_ENDPOINT, {}, 20)
        transport.get(BARS_ENDPOINT, {}, 20)
        assert clock.now == pytest.approx(.35)
        assert build.return_value.open.call_args_list[0].kwargs["timeout"] == 1
        assert build.return_value.open.call_args_list[1].kwargs["timeout"] == pytest.approx(.65)
        clock.now = 1
        with pytest.raises(HistoricalAcquisitionError, match="session_deadline_exceeded"):
            transport.get(BARS_ENDPOINT, {}, 20)
        assert build.return_value.open.call_count == 2


def test_rate_spacing_starts_after_durable_reservation_observer_returns() -> None:
    clock = Clock()
    actual_get_times: list[float] = []

    def observer(event: Mapping[str, object]) -> None:
        if event["event"] == "attempt_reserved" and event["attempt_id"] == 1:
            clock.now += .5

    budget = make_budget(clock=clock, event_callback=observer)
    with patch("urllib.request.build_opener") as build:
        def open_response(*args: object, **kwargs: object) -> Opened:
            actual_get_times.append(clock.now)
            return Opened(b"ok")

        build.return_value.open.side_effect = open_response
        transport = concrete(budget)
        transport.get(BARS_ENDPOINT, {}, 10)
        transport.get(BARS_ENDPOINT, {}, 10)
    assert actual_get_times == pytest.approx([.5, .85])


def test_rate_spacing_is_enforced_at_actual_opener_after_request_preparation() -> None:
    clock = Clock()
    times: list[float] = []
    original_request = __import__("urllib.request", fromlist=["Request"]).Request

    def prepare(*args: object, **kwargs: object) -> object:
        if not times:
            clock.now += .5
        return original_request(*args, **kwargs)

    def open_response(*args: object, **kwargs: object) -> Opened:
        times.append(clock.now)
        return Opened(b"ok")

    budget = make_budget(clock=clock)
    with patch("urllib.request.build_opener") as build, patch("urllib.request.Request", prepare):
        build.return_value.open.side_effect = open_response
        transport = concrete(budget)
        transport.get(BARS_ENDPOINT, {}, 10)
        transport.get(BARS_ENDPOINT, {}, 10)
    assert times == pytest.approx([.5, .85])


@pytest.mark.parametrize("when", ["attempt_reserved", "body_received", "attempt_finished"])
def test_journal_observer_failure_stops_session_without_later_get(when: str) -> None:
    def observer(event: Mapping[str, object]) -> None:
        if event["event"] == when:
            raise OSError("PRIVATE_JOURNAL")

    budget = make_budget(event_callback=observer)
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.return_value = Opened(b"hello")
        transport = concrete(budget)
        with pytest.raises(HistoricalAcquisitionError, match="session_journal_failed"):
            transport.get(BARS_ENDPOINT, {}, 10)
        calls = build.return_value.open.call_count
        with pytest.raises(HistoricalAcquisitionError, match="session_journal_failed"):
            transport.get(BARS_ENDPOINT, {}, 10)
        assert build.return_value.open.call_count == calls
        assert calls == (0 if when == "attempt_reserved" else 1)


@pytest.mark.parametrize("clock_value", [float("nan"), float("inf"), -1])
def test_invalid_or_regressing_monotonic_clock_blocks_get(clock_value: float) -> None:
    clock = Clock()
    budget = make_budget(clock=clock)
    clock.now = clock_value
    with patch("urllib.request.build_opener") as build:
        with pytest.raises(HistoricalAcquisitionError, match="session_clock_invalid"):
            concrete(budget).get(BARS_ENDPOINT, {}, 10)
        build.return_value.open.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"max_attempts": 101}, {"max_attempts": True},
        {"max_received_body_bytes": 250 * 1024 * 1024 + 1},
        {"max_elapsed_seconds": 901}, {"max_elapsed_seconds": float("nan")},
        {"min_interval_seconds": 0},
    ],
)
def test_session_limits_cannot_relax_authorized_ceilings(change: dict[str, object]) -> None:
    with pytest.raises(HistoricalAcquisitionError, match="invalid_session_budget"):
        make_budget(**change)


def test_bounded_reader_checks_deadline_between_chunks() -> None:
    clock = Clock()
    budget = make_budget(clock=clock, max_elapsed_seconds=1)

    class Slow(Opened):
        def read1(self, size: int = -1) -> bytes:
            body = super().read1(min(size, 1))
            clock.now += .6
            return body

    opened = Slow(b"123", known_size=False)
    with patch("urllib.request.build_opener") as build:
        build.return_value.open.return_value = opened
        with pytest.raises(HistoricalAcquisitionError, match="session_deadline_exceeded"):
            concrete(budget).get(BARS_ENDPOINT, {}, 10)
    assert opened.received == 2
    assert budget.received_body_bytes == 2


def test_bounded_transport_rejects_unbounded_injected_transport() -> None:
    class Unbounded:
        def get(self, *args: object) -> object:
            raise AssertionError("must never call unbounded transport")

    with pytest.raises(HistoricalAcquisitionError, match="bounded_transport_required"):
        api().BudgetedHistoricalTransport(transport=Unbounded(), budget=make_budget())

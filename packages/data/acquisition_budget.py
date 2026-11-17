"""Sequential session limits for explicitly authorized historical data GETs.

The caller owns durable event storage and refuses existing/interrupted sessions.
Payload bytes include all HTTP statuses and partial reads, excluding HTTP headers,
TLS framing and OS buffers. Process supervision supplies a strict wall deadline.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.parse
from collections.abc import Callable, Mapping
from typing import Protocol

from packages.data.alpaca_historical import (
    ACTIONS_ENDPOINT,
    BARS_ENDPOINT,
    HistoricalAcquisitionError,
    HttpResponse,
)


class BoundedHistoricalTransport(Protocol):
    def get_bounded(
        self,
        endpoint: str,
        params: Mapping[str, str],
        timeout_seconds: float,
        *,
        max_body_bytes: int,
        body_received: Callable[[int], None],
        response_started: Callable[[int], None],
        request_started: Callable[[], None],
        remaining_seconds: Callable[[], float],
    ) -> HttpResponse: ...


class HistoricalSessionBudget:
    """One in-process, sequential budget shared by preflight and every acquisition.

    The event callback must durably persist each event before returning. Callback
    failures permanently close this budget. An outstanding reservation after a
    crash must never be reset or automatically resumed by the caller.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 100,
        max_received_body_bytes: int = 250 * 1024 * 1024,
        max_elapsed_seconds: float = 900,
        min_interval_seconds: float = .35,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        event_callback: Callable[[Mapping[str, object]], None] = lambda _: None,
        initial_attempts: int = 0,
        initial_received_body_bytes: int = 0,
        initial_successful_body_bytes: int = 0,
    ) -> None:
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or not 1 <= max_attempts <= 100
            or isinstance(max_received_body_bytes, bool)
            or not isinstance(max_received_body_bytes, int)
            or not 1 <= max_received_body_bytes <= 250 * 1024 * 1024
            or isinstance(max_elapsed_seconds, bool)
            or not math.isfinite(max_elapsed_seconds)
            or not 0 < max_elapsed_seconds <= 900
            or isinstance(min_interval_seconds, bool)
            or not math.isfinite(min_interval_seconds)
            or not .35 <= min_interval_seconds <= 60
        ):
            raise HistoricalAcquisitionError("invalid_session_budget")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= limit
            for value, limit in (
                (initial_attempts, max_attempts),
                (initial_received_body_bytes, max_received_body_bytes),
                (initial_successful_body_bytes, initial_received_body_bytes),
            )
        ):
            raise HistoricalAcquisitionError("invalid_session_budget")
        self.max_attempts = max_attempts
        self.max_received_body_bytes = max_received_body_bytes
        self.max_elapsed_seconds = max_elapsed_seconds
        self.min_interval_seconds = min_interval_seconds
        self._clock = monotonic
        self._sleep = sleep
        self._observer = event_callback
        self._attempts = initial_attempts
        self._received_body_bytes = initial_received_body_bytes
        self._successful_body_bytes = initial_successful_body_bytes
        self._active = False
        self._journal_failed = False
        self._last_attempt: float | None = None
        self._started = float(monotonic())
        if not math.isfinite(self._started):
            raise HistoricalAcquisitionError("session_clock_invalid")
        self._last_clock = self._started

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def received_body_bytes(self) -> int:
        return self._received_body_bytes

    @property
    def successful_body_bytes(self) -> int:
        """All bytes read under HTTP 200, including a subsequently failed body."""
        return self._successful_body_bytes

    def _now(self) -> float:
        now = float(self._clock())
        if not math.isfinite(now) or now < self._last_clock:
            raise HistoricalAcquisitionError("session_clock_invalid")
        self._last_clock = now
        return now

    def remaining_seconds(self) -> float:
        if self._journal_failed:
            raise HistoricalAcquisitionError("session_journal_failed")
        remaining = self.max_elapsed_seconds - (self._now() - self._started)
        if remaining <= 0:
            raise HistoricalAcquisitionError("session_deadline_exceeded")
        return remaining

    def snapshot(self) -> dict[str, object]:
        return {
            "attempts": self.attempts,
            "received_body_bytes": self.received_body_bytes,
            "successful_body_bytes": self.successful_body_bytes,
            "max_attempts": self.max_attempts,
            "max_received_body_bytes": self.max_received_body_bytes,
            "max_elapsed_seconds": self.max_elapsed_seconds,
            "min_interval_seconds": self.min_interval_seconds,
            "elapsed_seconds": self._now() - self._started,
        }

    def _emit(self, event: str, **fields: object) -> None:
        if self._journal_failed:
            raise HistoricalAcquisitionError("session_journal_failed")
        value = {"event": event, "attempt_id": self.attempts, **self.snapshot(), **fields}
        try:
            self._observer(value)
        except Exception:
            self._journal_failed = True
            raise HistoricalAcquisitionError("session_journal_failed") from None

    def _reserve(self, endpoint: str, params: Mapping[str, str], limit: int) -> int:
        self.remaining_seconds()
        if self._active:
            raise HistoricalAcquisitionError("session_request_inflight")
        if self.attempts >= self.max_attempts:
            raise HistoricalAcquisitionError("session_attempt_limit")
        allowance = min(limit, self.max_received_body_bytes - self.received_body_bytes)
        if allowance <= 0:
            raise HistoricalAcquisitionError("session_byte_limit")
        query_hash = hashlib.sha256(
            json.dumps(dict(params), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self._attempts += 1
        self._active = True
        self._emit(
            "attempt_reserved",
            endpoint_path=urllib.parse.urlsplit(endpoint).path,
            query_sha256=query_hash,
            request_body_budget=allowance,
        )
        return allowance

    def _before_get(self) -> None:
        remaining = self.remaining_seconds()
        if self._last_attempt is not None:
            delay = self.min_interval_seconds - (self._now() - self._last_attempt)
            if delay > 0:
                if delay >= remaining:
                    raise HistoricalAcquisitionError("session_deadline_exceeded")
                self._sleep(delay)
                self.remaining_seconds()
                if self._now() - self._last_attempt < self.min_interval_seconds - 1e-9:
                    raise HistoricalAcquisitionError("session_rate_wait_incomplete")
        self._last_attempt = self._now()

    def _record_bytes(self, count: int, status: int | None) -> None:
        if not self._active or count <= 0:
            raise HistoricalAcquisitionError("invalid_session_accounting")
        self._received_body_bytes += count
        if status == 200:
            self._successful_body_bytes += count
        self._emit("body_received", chunk_bytes=count, status_code=status)
        if self.received_body_bytes > self.max_received_body_bytes:
            raise HistoricalAcquisitionError("session_byte_limit")

    def _finish(self, status: int | None, error: str | None) -> None:
        self._active = False
        self._emit("attempt_finished", status_code=status, error_code=error)


class BudgetedHistoricalTransport:
    """Apply a shared budget before every actual GET, including acquirer retries."""

    def __init__(
        self,
        *,
        transport: BoundedHistoricalTransport,
        budget: HistoricalSessionBudget,
        max_body_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        if not callable(getattr(transport, "get_bounded", None)):
            raise HistoricalAcquisitionError("bounded_transport_required")
        if (
            isinstance(max_body_bytes, bool)
            or not isinstance(max_body_bytes, int)
            or not 1 <= max_body_bytes <= 16 * 1024 * 1024
        ):
            raise HistoricalAcquisitionError("invalid_body_limit")
        self.transport = transport
        self.budget = budget
        self.max_body_bytes = max_body_bytes

    def get(
        self, endpoint: str, params: Mapping[str, str], timeout_seconds: float
    ) -> HttpResponse:
        if endpoint not in {BARS_ENDPOINT, ACTIONS_ENDPOINT}:
            raise HistoricalAcquisitionError("endpoint_rejected")
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
            raise HistoricalAcquisitionError("invalid_timeout")
        allowance = self.budget._reserve(endpoint, params, self.max_body_bytes)
        status: int | None = None

        def started(value: int) -> None:
            nonlocal status
            status = value

        try:
            response = self.transport.get_bounded(
                endpoint,
                params,
                min(timeout_seconds, self.budget.remaining_seconds()),
                max_body_bytes=allowance,
                body_received=lambda size: self.budget._record_bytes(size, status),
                response_started=started,
                request_started=self.budget._before_get,
                remaining_seconds=self.budget.remaining_seconds,
            )
            self.budget.remaining_seconds()
        except HistoricalAcquisitionError as exc:
            self.budget._finish(status, exc.code)
            raise
        except Exception:
            self.budget._finish(status, "transport_failed")
            raise HistoricalAcquisitionError("transport_failed") from None
        self.budget._finish(status, None)
        return response

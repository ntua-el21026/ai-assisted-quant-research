"""Explicit read-only Alpaca acquisition, isolated from canonical offline research.

The transport never discovers credentials. Historical availability and adjustment
revision histories are not supplied by these endpoints; reconstruction is tagged
as an assumption. Corporate-action windows filter process dates, not ex-dates.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from decimal import Decimal
from email.utils import parsedate_to_datetime
from fractions import Fraction
from typing import Literal, Protocol, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from packages.data.corporate_actions import (
    CashDividendAction,
    CorporateAction,
    SplitAction,
    validate_actions,
)
from packages.data.models import AdjustedDailyBar
from packages.data.snapshots import MarketSession

BARS_ENDPOINT = "https://data.alpaca.markets/v2/stocks/bars"
ACTIONS_ENDPOINT = "https://data.alpaca.markets/v1/corporate-actions"
NEW_YORK = ZoneInfo("America/New_York")
Adjustment = Literal["raw", "split", "dividend", "all"]
ActionType = Literal["forward_split", "reverse_split", "cash_dividend"]


class HistoricalAcquisitionError(RuntimeError):
    """Safe closed error codes; provider bodies, keys and URLs are never echoed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AcquisitionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class HistoricalRequest(AcquisitionModel):
    provider: Literal["alpaca"]
    symbols: tuple[str, ...] = Field(min_length=1)
    start: date
    end: date
    max_pages: int = Field(default=1000, ge=1, le=10000)

    @field_validator("symbols")
    @classmethod
    def canonical_symbols(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values) or any(
            re.fullmatch(r"[A-Z][A-Z0-9.-]{0,19}", value) is None for value in values
        ):
            raise ValueError("symbols require unique uppercase ticker identifiers")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.start > self.end:
            raise ValueError("start must not exceed end")
        return self


class HistoricalBarsRequest(HistoricalRequest):
    feed: Literal["iex", "sip"]
    adjustment: Adjustment
    timeframe: Literal["1Day"]
    limit: int = Field(default=10000, ge=1, le=10000)
    asof: date | Literal["-"] = "-"


class CorporateActionsRequest(HistoricalRequest):
    """The inclusive start/end window refers to provider process_date."""

    types: tuple[ActionType, ...] | Literal["all"]
    data_quality: Literal["complete", "all"] = "complete"
    limit: int = Field(default=1000, ge=1, le=1000)

    @field_validator("types")
    @classmethod
    def canonical_types(
        cls,
        values: tuple[ActionType, ...] | Literal["all"],
    ) -> tuple[ActionType, ...] | Literal["all"]:
        if values == "all":
            return values
        if not values or len(set(values)) != len(values):
            raise ValueError("action types must be unique")
        return tuple(sorted(values))


class RetryPolicy(AcquisitionModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    initial_delay_seconds: float = Field(default=1, gt=0, le=60)
    max_delay_seconds: float = Field(default=60, gt=0, le=300)
    max_total_wait_seconds: float = Field(default=300, ge=0, le=3600)


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def get(
        self,
        endpoint: str,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse: ...


class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: object,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        raise HistoricalAcquisitionError("redirect_rejected")


@dataclass(repr=False)
class UrllibHistoricalTransport:
    """Optional concrete transport; construction makes no network requests.

    Caller supplies credentials. No environment/file access, ambient proxies,
    redirect following, custom hosts, or broker endpoints are accepted.
    """

    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    max_body_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        if not self.api_key.strip() or not self.secret_key.strip():
            raise HistoricalAcquisitionError("missing_credentials")
        if not 1 <= self.max_body_bytes <= 64 * 1024 * 1024:
            raise HistoricalAcquisitionError("invalid_body_limit")
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _RejectRedirect(),
        )

    def get(
        self,
        endpoint: str,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        if endpoint not in {BARS_ENDPOINT, ACTIONS_ENDPOINT}:
            raise HistoricalAcquisitionError("endpoint_rejected")
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
            raise HistoricalAcquisitionError("invalid_timeout")
        query = urllib.parse.urlencode(sorted(params.items()))
        request = urllib.request.Request(
            endpoint + ("?" + query if query else ""),
            method="GET",
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(request, timeout=timeout_seconds) as opened:
                return HttpResponse(opened.status, dict(opened.headers), self._body(opened))
        except urllib.error.HTTPError as exc:
            try:
                return HttpResponse(exc.code, dict(exc.headers), self._body(exc))
            except HistoricalAcquisitionError:
                raise
            except Exception:
                raise HistoricalAcquisitionError("transport_failed") from None
            finally:
                try:
                    exc.close()
                except Exception:
                    raise HistoricalAcquisitionError("transport_failed") from None
        except HistoricalAcquisitionError:
            raise
        except Exception:
            raise HistoricalAcquisitionError("transport_failed") from None

    def _body(self, opened: object) -> bytes:
        # Both HTTPResponse and HTTPError have read(); keep raw bytes for provenance.
        body = opened.read(self.max_body_bytes + 1)  # type: ignore[attr-defined]
        if len(body) > self.max_body_bytes:
            raise HistoricalAcquisitionError("body_limit_exceeded") from None
        return bytes(body)

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
    ) -> HttpResponse:
        """Read within a caller's remaining payload allowance, including HTTP errors.

        This path never consumes an extra probe byte. An unknown-length response
        reaching its allowance is conservatively rejected, even if exactly full.
        Deadline checks bound application-controlled work; OS/DNS blocking still
        needs the caller's process watchdog for a strict wall-clock limit.
        """
        if endpoint not in {BARS_ENDPOINT, ACTIONS_ENDPOINT}:
            raise HistoricalAcquisitionError("endpoint_rejected")
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
            raise HistoricalAcquisitionError("invalid_timeout")
        if (
            isinstance(max_body_bytes, bool)
            or not isinstance(max_body_bytes, int)
            or not 1 <= max_body_bytes <= 16 * 1024 * 1024
        ):
            raise HistoricalAcquisitionError("invalid_body_limit")
        cap = min(max_body_bytes, self.max_body_bytes)
        query = urllib.parse.urlencode(sorted(params.items()))
        request = urllib.request.Request(
            endpoint + ("?" + query if query else ""),
            method="GET",
            headers={
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key,
                "Accept": "application/json",
            },
        )

        def receive(opened: object, status: int, headers: Mapping[str, str]) -> HttpResponse:
            response_started(status)
            body = self._bounded_body(opened, headers, cap, body_received, remaining_seconds)
            return HttpResponse(status, dict(headers), body)

        try:
            request_started()
            timeout = min(timeout_seconds, remaining_seconds())
            with self._opener.open(request, timeout=timeout) as opened:
                return receive(opened, opened.status, dict(opened.headers))
        except urllib.error.HTTPError as exc:
            try:
                return receive(exc, exc.code, dict(exc.headers))
            except HistoricalAcquisitionError:
                raise
            except Exception:
                raise HistoricalAcquisitionError("transport_failed") from None
            finally:
                try:
                    exc.close()
                except Exception:
                    raise HistoricalAcquisitionError("transport_failed") from None
        except HistoricalAcquisitionError:
            raise
        except Exception:
            raise HistoricalAcquisitionError("transport_failed") from None

    @staticmethod
    def _bounded_body(
        opened: object,
        headers: Mapping[str, str],
        limit: int,
        body_received: Callable[[int], None],
        remaining_seconds: Callable[[], float],
    ) -> bytes:
        normalized = {key.lower(): value for key, value in headers.items()}
        expected: int | None = None
        if "content-length" in normalized:
            value = normalized["content-length"]
            if not value.isascii() or not value.isdigit() or len(value) > 20:
                raise HistoricalAcquisitionError("invalid_body_length")
            if "transfer-encoding" in normalized:
                raise HistoricalAcquisitionError("invalid_body_length")
            expected = int(value)
            if expected > limit:
                raise HistoricalAcquisitionError("body_limit_exceeded")
        chunks: list[bytes] = []
        received = 0
        reader = getattr(opened, "read1", None) or opened.read  # type: ignore[attr-defined]
        while True:
            remaining_seconds()
            if expected is not None and received == expected:
                return b"".join(chunks)
            allowance = limit - received
            if not allowance:
                raise HistoricalAcquisitionError("body_limit_exceeded")
            size = min(64 * 1024, allowance)
            if expected is not None:
                size = min(size, expected - received)
            chunk = bytes(reader(size))
            if not chunk:
                if expected is not None and received != expected:
                    raise HistoricalAcquisitionError("incomplete_body")
                return b"".join(chunks)
            body_received(len(chunk))
            received += len(chunk)
            chunks.append(chunk)


@dataclass(frozen=True)
class AcquiredPage:
    endpoint: str
    query: tuple[tuple[str, str], ...]
    body: bytes
    received_at: datetime

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


@dataclass(frozen=True)
class HistoricalAcquisition:
    request: HistoricalBarsRequest | CorporateActionsRequest
    request_started_at: datetime
    acquired_at: datetime
    pages: tuple[AcquiredPage, ...]

    @property
    def warnings(self) -> tuple[str, ...]:
        if isinstance(self.request, CorporateActionsRequest):
            warnings = [
                "provider_creation_time_unverified",
                "process_date_window_does_not_certify_ex_date_coverage",
            ]
            if self.request.types != "all":
                warnings.append("corporate_action_inventory_filtered")
            return tuple(warnings)
        return ("historical_first_publication_unverified",)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalAcquisitionError("naive_clock")
    return value.astimezone(UTC)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode_historical_page(body: bytes) -> dict[str, object]:
    """Decode exact numbers and reject ambiguous duplicate keys at every depth."""
    try:
        value = json.loads(body, parse_float=Decimal, object_pairs_hook=_unique_json_object)
    except (ValueError, UnicodeError, RecursionError):
        raise HistoricalAcquisitionError("invalid_json") from None
    if not isinstance(value, dict):
        raise HistoricalAcquisitionError("invalid_page")
    return value


def historical_query(
    request: HistoricalBarsRequest | CorporateActionsRequest,
) -> tuple[str, dict[str, str]]:
    """Construct the complete first-page wire query without transport or state."""
    if isinstance(request, HistoricalBarsRequest):
        begin = datetime.combine(request.start, day_time.min, NEW_YORK)
        finish = datetime.combine(request.end + timedelta(days=1), day_time.min, NEW_YORK)
        return BARS_ENDPOINT, {
            "symbols": ",".join(request.symbols),
            "feed": request.feed,
            "adjustment": request.adjustment,
            "timeframe": request.timeframe,
            "start": _rfc3339(begin),
            "end": _rfc3339(finish - timedelta(microseconds=1)),
            "limit": str(request.limit),
            "sort": "asc",
            "currency": "USD",
            "asof": str(request.asof),
        }
    params = {
        "symbols": ",".join(request.symbols),
        "start": request.start.isoformat(),
        "end": request.end.isoformat(),
        "limit": str(request.limit),
        "sort": "asc",
        "region": "us",
        "data_quality": request.data_quality,
    }
    if request.types != "all":
        params["types"] = ",".join(request.types)
    return ACTIONS_ENDPOINT, params


class AlpacaHistoricalAcquirer:
    def __init__(
        self,
        *,
        transport: HttpTransport,
        retry: RetryPolicy | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], None] = time.sleep,
        timeout_seconds: float = 20,
        max_total_body_bytes: int = 128 * 1024 * 1024,
    ) -> None:
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
            raise HistoricalAcquisitionError("invalid_timeout")
        if (
            isinstance(max_total_body_bytes, bool)
            or not isinstance(max_total_body_bytes, int)
            or not 1 <= max_total_body_bytes <= 1024 * 1024 * 1024
        ):
            raise HistoricalAcquisitionError("invalid_total_body_limit")
        self.max_total_body_bytes = max_total_body_bytes
        self.transport = transport
        self.retry = retry or RetryPolicy()
        self.clock = clock
        self.sleep = sleep
        self.timeout_seconds = timeout_seconds

    def fetch_bars(self, request: HistoricalBarsRequest) -> HistoricalAcquisition:
        endpoint, params = historical_query(request)
        return self._fetch(request, endpoint, params, "bars")

    def fetch_actions(self, request: CorporateActionsRequest) -> HistoricalAcquisition:
        endpoint, params = historical_query(request)
        return self._fetch(request, endpoint, params, "corporate_actions")

    def _fetch(
        self,
        request: HistoricalBarsRequest | CorporateActionsRequest,
        endpoint: str,
        params: dict[str, str],
        data_key: str,
    ) -> HistoricalAcquisition:
        started = _utc(self.clock())
        pages: list[AcquiredPage] = []
        seen_tokens: set[str] = set()
        waited = 0.0
        retained_bytes = 0
        for _ in range(request.max_pages):
            for attempt in range(self.retry.max_attempts):
                response: HttpResponse | None = None
                try:
                    response = self.transport.get(endpoint, params, self.timeout_seconds)
                except HistoricalAcquisitionError as exc:
                    if exc.code != "transport_failed":
                        raise
                except Exception:
                    pass
                if response is not None and response.status_code == 200:
                    break
                code = self._error_code(response)
                retryable = response is None or response.status_code in {429, 500, 502, 503, 504}
                if not retryable or attempt + 1 >= self.retry.max_attempts:
                    raise HistoricalAcquisitionError(code) from None
                delay = self._delay(response, attempt)
                waited = self._wait(delay, waited)
            if response is None:
                raise HistoricalAcquisitionError("transport_failed")
            retained_bytes += len(response.body)
            if retained_bytes > self.max_total_body_bytes:
                raise HistoricalAcquisitionError("total_body_limit_exceeded")
            received = _utc(self.clock())
            if received < started or (pages and received < pages[-1].received_at):
                raise HistoricalAcquisitionError("clock_regressed")
            payload = decode_historical_page(response.body)
            if not isinstance(payload.get(data_key), dict) or "next_page_token" not in payload:
                raise HistoricalAcquisitionError("invalid_page")
            token = payload["next_page_token"]
            if token is not None and (not isinstance(token, str) or not token or len(token) > 4096):
                raise HistoricalAcquisitionError("invalid_page")
            pages.append(
                AcquiredPage(endpoint, tuple(sorted(params.items())), response.body, received)
            )
            if token is None:
                return HistoricalAcquisition(request, started, received, tuple(pages))
            if token in seen_tokens:
                raise HistoricalAcquisitionError("pagination_cycle")
            seen_tokens.add(token)
            params["page_token"] = token
            headers = {k.lower(): v for k, v in response.headers.items()}
            if headers.get("x-ratelimit-remaining") == "0":
                waited = self._wait(self._delay(response, 0), waited)
        raise HistoricalAcquisitionError("page_limit_exceeded")

    @staticmethod
    def _error_code(response: HttpResponse | None) -> str:
        if response is None:
            return "transport_failed"
        if response.status_code == 401:
            return "authentication_failed"
        if response.status_code == 403:
            # The HTTP status alone cannot distinguish a key/account problem from entitlement.
            return "forbidden"
        if 300 <= response.status_code < 400:
            return "redirect_rejected"
        if response.status_code == 400:
            return "invalid_request"
        if response.status_code == 429:
            return "rate_limited"
        return "provider_failed"

    def _delay(self, response: HttpResponse | None, attempt: int) -> float:
        base: float = float(
            min(
                self.retry.max_delay_seconds,
                self.retry.initial_delay_seconds * 2**attempt,
            )
        )
        if response is None:
            return base
        headers = {k.lower(): v for k, v in response.headers.items()}
        try:
            if "retry-after" in headers:
                try:
                    delay = float(headers["retry-after"])
                except ValueError:
                    delay = (
                        _utc(parsedate_to_datetime(headers["retry-after"])) - _utc(self.clock())
                    ).total_seconds()
            elif "x-ratelimit-reset" in headers:
                delay = float(headers["x-ratelimit-reset"]) - _utc(self.clock()).timestamp()
            else:
                return base
        except (ValueError, TypeError, OverflowError):
            raise HistoricalAcquisitionError("invalid_retry_header") from None
        if not math.isfinite(delay):
            raise HistoricalAcquisitionError("invalid_retry_header")
        return float(max(base, delay))

    def _wait(self, delay: float, waited: float) -> float:
        if (
            delay > self.retry.max_delay_seconds
            or waited + delay > self.retry.max_total_wait_seconds
        ):
            raise HistoricalAcquisitionError("retry_budget_exceeded")
        self.sleep(delay)
        return waited + delay


class BarAvailabilityPolicy(AcquisitionModel):
    mode: Literal["observed", "assumed_close_plus_delay"] = "observed"
    delay_seconds: int = Field(default=0, ge=0, le=86400)
    rationale: str | None = None

    @model_validator(mode="after")
    def check_assumption(self) -> Self:
        if self.mode == "assumed_close_plus_delay" and not (self.rationale or "").strip():
            raise ValueError("historical availability reconstruction requires a rationale")
        if self.mode == "observed" and (self.delay_seconds != 0 or self.rationale is not None):
            raise ValueError("observed availability has no reconstruction parameters")
        return self


class ExactOHLCV(AcquisitionModel):
    """Source decimals retained before the compatible legacy float projection."""

    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if not self.low <= self.open <= self.high or not self.low <= self.close <= self.high:
            raise ValueError("invalid exact OHLC range")
        return self


@dataclass(frozen=True)
class HistoricalBar:
    bar: AdjustedDailyBar
    provider_timestamp: datetime
    acquired_at: datetime
    available_at: datetime
    availability_basis: Literal["observed", "assumed"]
    adjustment: Adjustment
    feed: Literal["iex", "sip"]
    exact_ohlcv: ExactOHLCV


@dataclass(frozen=True)
class MissingBar:
    symbol: str
    session_date: date
    reason: Literal["missing_session"] = "missing_session"


@dataclass(frozen=True)
class NormalizedHistoricalBars:
    bars: tuple[HistoricalBar, ...]
    exclusions: tuple[MissingBar, ...]
    warnings: tuple[str, ...]
    availability_policy: BarAvailabilityPolicy


def normalize_historical_bars(
    acquisition: HistoricalAcquisition,
    *,
    sessions: Sequence[MarketSession],
    missing_policy: Literal["error", "exclude"],
    availability: BarAvailabilityPolicy | None = None,
) -> NormalizedHistoricalBars:
    """Normalize daily NY-midnight bars against a caller-supplied real calendar.

    Acquisition-time availability is conservative and cannot establish historical
    availability. Explicit close-plus-delay reconstruction makes an assumption;
    adjusted values can include future actions regardless of that assumption.
    """
    request = acquisition.request
    if not isinstance(request, HistoricalBarsRequest) or missing_policy not in {"error", "exclude"}:
        raise HistoricalAcquisitionError("invalid_normalization_request")
    policy = availability or BarAvailabilityPolicy()
    calendar = {session.date: session for session in sessions}
    if (
        not calendar
        or len(calendar) != len(sessions)
        or any(
            not request.start <= session.date <= request.end
            or session.open_at.astimezone(NEW_YORK).date() != session.date
            or session.close_at.astimezone(NEW_YORK).date() != session.date
            for session in sessions
        )
    ):
        raise HistoricalAcquisitionError("invalid_calendar")
    bars: dict[tuple[str, date], HistoricalBar] = {}
    for page in acquisition.pages:
        payload = decode_historical_page(page.body).get("bars")
        if not isinstance(payload, dict):
            raise HistoricalAcquisitionError("invalid_page")
        for symbol, records in payload.items():
            if symbol not in request.symbols:
                raise HistoricalAcquisitionError("unexpected_symbol")
            if not isinstance(records, list):
                raise HistoricalAcquisitionError("invalid_page")
            for record in records:
                if not isinstance(record, dict):
                    raise HistoricalAcquisitionError("invalid_ohlcv")
                try:
                    timestamp = _utc(datetime.fromisoformat(record["t"]))
                except (KeyError, ValueError, TypeError, HistoricalAcquisitionError):
                    raise HistoricalAcquisitionError("invalid_bar_timestamp") from None
                local = timestamp.astimezone(NEW_YORK)
                if local.timetz().replace(tzinfo=None) != day_time.min:
                    raise HistoricalAcquisitionError("invalid_bar_timestamp")
                session = calendar.get(local.date())
                if session is None:
                    raise HistoricalAcquisitionError("unexpected_session")
                if acquisition.acquired_at < session.close_at:
                    raise HistoricalAcquisitionError("incomplete_session")
                try:
                    values = {
                        name: record[key]
                        for name, key in (
                            ("open", "o"),
                            ("high", "h"),
                            ("low", "l"),
                            ("close", "c"),
                        )
                    }
                    if any(
                        isinstance(v, bool)
                        or not isinstance(v, int | float | Decimal)
                        or not math.isfinite(v)
                        for v in values.values()
                    ):
                        raise ValueError
                    volume = record["v"]
                    if isinstance(volume, bool) or not isinstance(volume, int) or volume < 0:
                        raise ValueError
                    exact = ExactOHLCV(**values, volume=volume)
                    bar = AdjustedDailyBar(
                        symbol=symbol,
                        date=session.date,
                        **values,
                        volume=volume,
                        adjusted=request.adjustment != "raw",
                        provider="alpaca",
                        payload_hash=page.sha256,
                    )
                except (KeyError, ValueError, TypeError, ValidationError):
                    raise HistoricalAcquisitionError("invalid_ohlcv") from None
                key = (symbol, session.date)
                if key in bars:
                    raise HistoricalAcquisitionError("duplicate_session")
                available = acquisition.acquired_at
                basis: Literal["observed", "assumed"] = "observed"
                if policy.mode == "assumed_close_plus_delay":
                    available = session.close_at.astimezone(UTC) + timedelta(
                        seconds=policy.delay_seconds
                    )
                    basis = "assumed"
                    if available > acquisition.acquired_at:
                        raise HistoricalAcquisitionError("availability_after_acquisition")
                bars[key] = HistoricalBar(
                    bar,
                    timestamp,
                    acquisition.acquired_at,
                    available,
                    basis,
                    request.adjustment,
                    request.feed,
                    exact,
                )
    missing = tuple(
        MissingBar(symbol, d)
        for symbol in request.symbols
        for d in sorted(calendar)
        if (symbol, d) not in bars
    )
    if missing and missing_policy == "error":
        raise HistoricalAcquisitionError("missing_sessions")
    warnings = ["historical_first_publication_unverified"]
    if policy.mode == "assumed_close_plus_delay":
        warnings.append("historical_availability_is_assumed")
    if request.adjustment != "raw":
        warnings.append("adjusted_prices_are_not_point_in_time")
    return NormalizedHistoricalBars(
        tuple(bars[key] for key in sorted(bars)), missing, tuple(warnings), policy
    )


def _bounded_action_rate(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise ValueError("invalid rate type")
    encoded = str(value)
    if len(encoded) > 64:
        raise ValueError("rate representation exceeds supported size")
    amount = Decimal(encoded)
    if (
        not amount.is_finite()
        or not Decimal("1e-9") <= amount <= Decimal("1e9")
        or len(amount.as_tuple().digits) > 32
    ):
        raise ValueError("rate exceeds supported magnitude or precision")
    return amount


def normalize_corporate_actions(
    acquisition: HistoricalAcquisition,
    *,
    security_ids: Mapping[str, str],
) -> tuple[CorporateAction, ...]:
    """Bounded split/USD-cash normalization; caller owns point-in-time identities.

    No provider historical first-publication timestamp is fabricated. Special or
    foreign dividends and unsupported action classes require a separate policy.
    Cash rates are accepted only for domestic ordinary USD dividends. A coincident
    split/dividend is rejected because this endpoint supplies no rate share basis.
    Cash/split rates require <=64 encoded characters, <=32 coefficient digits,
    and magnitudes in [1e-9, 1e9]. Reduced split numerator/denominator terms
    cannot exceed one billion. Unsupported rates fail before integer expansion.
    """
    request = acquisition.request
    if not isinstance(request, CorporateActionsRequest):
        raise HistoricalAcquisitionError("invalid_normalization_request")
    actions: list[CorporateAction] = []
    categories = {
        "forward_splits": "forward_split",
        "reverse_splits": "reverse_split",
        "cash_dividends": "cash_dividend",
    }
    for page in acquisition.pages:
        payload = decode_historical_page(page.body).get("corporate_actions")
        if not isinstance(payload, dict):
            raise HistoricalAcquisitionError("invalid_page")
        for category, records in payload.items():
            if category not in categories or (
                request.types != "all" and categories[category] not in request.types
            ):
                raise HistoricalAcquisitionError("unsupported_corporate_action")
            if not isinstance(records, list):
                raise HistoricalAcquisitionError("invalid_page")
            for record in records:
                if not isinstance(record, dict):
                    raise HistoricalAcquisitionError("invalid_corporate_action")
                try:
                    symbol = record["symbol"]
                    if symbol not in request.symbols or not security_ids.get(symbol):
                        raise HistoricalAcquisitionError("unknown_security_identity")
                    process_date = date.fromisoformat(record["process_date"])
                    if not request.start <= process_date <= request.end:
                        raise HistoricalAcquisitionError("action_outside_process_window")
                    shared = {
                        "action_id": record["id"],
                        "security_id": security_ids[symbol],
                        "symbol": symbol,
                        "ex_date": record["ex_date"],
                        "available_at": acquisition.acquired_at,
                        "availability_basis": "observed",
                    }
                    if category == "cash_dividends":
                        if (
                            record["foreign"] is not False
                            or record["special"] is not False
                            or record.get("currency", "USD") != "USD"
                        ):
                            raise HistoricalAcquisitionError("unsupported_corporate_action")
                        actions.append(
                            CashDividendAction(
                                **shared,
                                pay_date=record["payable_date"],
                                cash_per_share=_bounded_action_rate(record["rate"]),
                                currency="USD",
                            )
                        )
                    else:
                        new_rate = _bounded_action_rate(record["new_rate"])
                        old_rate = _bounded_action_rate(record["old_rate"])
                        # Bound terms before materializing integer fractions.
                        ratio = Fraction(new_rate) / Fraction(old_rate)
                        if max(ratio.numerator, ratio.denominator) > 1_000_000_000:
                            raise ValueError
                        if category == "forward_splits" and ratio <= 1:
                            raise ValueError
                        if category == "reverse_splits" and ratio >= 1:
                            raise ValueError
                        actions.append(
                            SplitAction(
                                **shared,
                                numerator=ratio.numerator,
                                denominator=ratio.denominator,
                            )
                        )
                except HistoricalAcquisitionError:
                    raise
                except (KeyError, TypeError, ValueError, ArithmeticError):
                    raise HistoricalAcquisitionError("invalid_corporate_action") from None
    split_keys = {(a.security_id, a.ex_date) for a in actions if isinstance(a, SplitAction)}
    if any(
        isinstance(a, CashDividendAction) and (a.security_id, a.ex_date) in split_keys
        for a in actions
    ):
        raise HistoricalAcquisitionError("ambiguous_dividend_share_basis")
    try:
        return validate_actions(actions)
    except ValueError:
        raise HistoricalAcquisitionError("invalid_corporate_action") from None

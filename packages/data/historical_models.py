"""Explicit v2 provenance contracts; v1 models and meanings remain unchanged."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, time
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from packages.data.corporate_actions import AvailabilityBasis, ExactDecimal
from packages.data.snapshots import MarketSession, SnapshotModel

Permission = Literal["confirmed", "requires_clarification", "prohibited"]
SHA_PATTERN = r"^[0-9a-f]{64}$"
NEW_YORK = ZoneInfo("America/New_York")


class HistoricalModel(SnapshotModel):
    @field_validator("*")
    @classmethod
    def meaningful_text(cls, value: object) -> object:
        if isinstance(value, str) and (not value.strip() or value != value.strip()):
            raise ValueError("blank_or_padded_provenance")
        return value


def utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("timestamp_requires_offset")
    return value.astimezone(UTC)


class HistoricalSession(MarketSession):
    early_close: bool

    @field_validator("open_at", "close_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def regular_session(self) -> Self:
        opening = self.open_at.astimezone(NEW_YORK)
        closing = self.close_at.astimezone(NEW_YORK)
        if (
            self.date.weekday() >= 5
            or opening.date() != self.date
            or closing.date() != self.date
            or opening.time() != time(9, 30)
            or closing.time() != (time(13) if self.early_close else time(16))
        ):
            raise ValueError("invalid_regular_session")
        return self


class HistoricalCalendar(HistoricalModel):
    name: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    version: str = Field(min_length=1)
    timezone: Literal["America/New_York"]
    price_session: Literal["regular"]
    volume_session: Literal["regular", "full_day", "synthetic"]
    coverage_complete: Literal[True]


class SymbolMapping(HistoricalModel):
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]*$")
    start: date
    end: date
    source: str = Field(min_length=1)
    available_at: datetime
    availability_basis: AvailabilityBasis
    point_in_time_status: Literal["confirmed", "uncertain"]

    @field_validator("available_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def valid_interval(self) -> Self:
        if self.end < self.start:
            raise ValueError("invalid_mapping_interval")
        return self


class SecurityIdentity(HistoricalModel):
    security_id: str = Field(min_length=1)
    mappings: tuple[SymbolMapping, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def disjoint_intervals(self) -> Self:
        ordered = sorted(self.mappings, key=lambda m: m.start)
        if any(a.end >= b.start for a, b in zip(ordered, ordered[1:], strict=False)):
            raise ValueError("overlapping_symbol_mapping")
        return self


class HistoricalLicense(HistoricalModel):
    name: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    entitlement: Permission
    storage: Permission
    retention: Permission
    raw_redistribution: Permission
    derived_publication: Permission
    restrictions: tuple[str, ...] = Field(min_length=1)


class SnapshotRevision(HistoricalModel):
    revision_id: str = Field(min_length=1)
    parent_manifest_sha256: str | None = Field(pattern=SHA_PATTERN)
    correction_observed_at: datetime | None
    reason: str = Field(min_length=1)

    @field_validator("correction_observed_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        return None if value is None else utc(value)

    @model_validator(mode="after")
    def correction_has_parent(self) -> Self:
        if (self.parent_manifest_sha256 is None) != (self.correction_observed_at is None):
            raise ValueError("correction_requires_parent_and_observation")
        return self


class AcquisitionProvenance(HistoricalModel):
    acquisition_id: str = Field(min_length=1)
    provider: Literal["synthetic", "alpaca"]
    mocked: bool
    endpoint: Literal["/v2/stocks/bars", "/v1/corporate-actions"]
    symbols: tuple[str, ...] = Field(min_length=1)
    feed: Literal["sip"] | None
    adjustment: Literal["raw"] | None
    timeframe: Literal["1Day"] | None
    start: date
    end: date
    asof: date | Literal["-"] | None
    currency: Literal["USD"] | None
    request_started_at: datetime
    acquired_at: datetime
    page_sha256: tuple[str, ...] = Field(min_length=1)
    query_parameters: tuple[tuple[str, str], ...] = Field(min_length=1)
    page_query_sha256: tuple[str, ...] = Field(min_length=1)
    complete: Literal[True]
    action_scope: Literal["all"] | None = None

    @field_validator("request_started_at", "acquired_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def query_consistency(self) -> Self:
        if self.end < self.start or self.acquired_at < self.request_started_at:
            raise ValueError("invalid_acquisition_interval")
        if tuple(sorted(set(self.symbols))) != self.symbols:
            raise ValueError("query_symbols_not_canonical")
        if any(
            not re.fullmatch(SHA_PATTERN, digest)
            for digest in (*self.page_sha256, *self.page_query_sha256)
        ) or len(self.page_sha256) != len(self.page_query_sha256):
            raise ValueError("invalid_page_hash")
        query = dict(self.query_parameters)
        if len(query) != len(self.query_parameters) or "page_token" in query:
            raise ValueError("invalid_query_parameters")
        if query.get("symbols") != ",".join(self.symbols) or query.get("sort") != "asc":
            raise ValueError("query_parameter_mismatch")
        first_query_hash = hashlib.sha256(
            json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self.page_query_sha256[0] != first_query_hash:
            raise ValueError("query_hash_mismatch")
        if self.endpoint == "/v2/stocks/bars":
            if (
                self.adjustment != "raw"
                or self.timeframe != "1Day"
                or self.action_scope
                or self.feed != "sip"
                or self.currency != "USD"
                or self.asof is None
            ):
                raise ValueError("raw_daily_query_required")
            required = {
                "symbols",
                "sort",
                "start",
                "end",
                "limit",
                "feed",
                "adjustment",
                "timeframe",
                "asof",
                "currency",
            }
            if set(query) != required or any(
                query[name] != str(getattr(self, name))
                for name in ("feed", "adjustment", "timeframe", "asof", "currency")
            ):
                raise ValueError("query_parameter_mismatch")
            if (
                utc(datetime.fromisoformat(query["start"])).astimezone(NEW_YORK).date()
                != self.start
                or utc(datetime.fromisoformat(query["end"])).astimezone(NEW_YORK).date() != self.end
            ):
                raise ValueError("query_date_mismatch")
            max_limit = 10000
        elif (
            self.adjustment is not None
            or self.timeframe is not None
            or self.action_scope != "all"
            or self.feed is not None
            or self.currency is not None
            or self.asof is not None
        ):
            raise ValueError("complete_action_discovery_required")
        else:
            if (
                set(query) != {"symbols", "sort", "start", "end", "limit", "region", "data_quality"}
                or query["start"] != self.start.isoformat()
                or query["end"] != self.end.isoformat()
                or query["region"] != "us"
                or query["data_quality"] not in {"all", "complete"}
            ):
                raise ValueError("query_parameter_mismatch")
            max_limit = 1000
        if not query["limit"].isdigit() or not 1 <= int(query["limit"]) <= max_limit:
            raise ValueError("query_limit_mismatch")
        return self


class HistoricalSnapshotFile(HistoricalModel):
    path: str = Field(min_length=1)
    format: Literal["json"]
    role: Literal["raw_bars", "corporate_actions"]
    acquisition_id: str = Field(min_length=1)
    size_bytes: int = Field(gt=0, strict=True)
    sha256: str = Field(pattern=SHA_PATTERN)


class MissingObservation(HistoricalModel):
    security_id: str = Field(min_length=1)
    date: date
    reason: str = Field(min_length=1)


class HistoricalAvailability(HistoricalModel):
    mode: Literal["observed", "reconstructed", "synthetic"]
    statement: str = Field(min_length=1)
    evidence_reference: str = Field(min_length=1)


class HistoricalSnapshotManifest(HistoricalModel):
    schema_version: Literal["market-snapshot/v2"]
    dataset_id: str = Field(min_length=1)
    kind: Literal["synthetic", "historical"]
    source: str = Field(min_length=1)
    frozen_at: datetime
    coverage_start: date
    coverage_end: date
    currency: Literal["USD"]
    calendar: HistoricalCalendar
    sessions: tuple[HistoricalSession, ...] = Field(min_length=1)
    execution_price_basis: Literal["raw"]
    feature_policy: Literal["raw_or_split_asof"]
    normalization_version: Literal["historical-json/v1"]
    historical_availability: HistoricalAvailability
    action_coverage: Literal["complete"]
    action_inventory_source: str = Field(min_length=1)
    expected_action_ids: tuple[str, ...]
    securities: tuple[SecurityIdentity, ...] = Field(min_length=1)
    identity_policy: Literal["require_confirmed", "allow_uncertain"]
    missing_session_policy: Literal["reject", "exclude"]
    exclusions: tuple[MissingObservation, ...]
    license: HistoricalLicense
    revision: SnapshotRevision
    acquisitions: tuple[AcquisitionProvenance, ...] = Field(min_length=1)
    files: tuple[HistoricalSnapshotFile, ...] = Field(min_length=2, max_length=2)

    @field_validator("frozen_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def complete_contract(self) -> Self:
        dates = tuple(s.date for s in self.sessions)
        if dates != tuple(sorted(set(dates))):
            raise ValueError("calendar_not_sorted_unique")
        if dates[0] != self.coverage_start or dates[-1] != self.coverage_end:
            raise ValueError("calendar_coverage_mismatch")
        if any(s.close_at > self.frozen_at for s in self.sessions):
            raise ValueError("session_after_freeze")
        for name, values in (
            ("security", [s.security_id for s in self.securities]),
            ("file", [f.path for f in self.files]),
            ("file_role", [f.role for f in self.files]),
            ("acquisition", [a.acquisition_id for a in self.acquisitions]),
            ("action", list(self.expected_action_ids)),
            ("exclusion", [(e.security_id, e.date) for e in self.exclusions]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate_{name}")
        if tuple(sorted(self.expected_action_ids)) != self.expected_action_ids:
            raise ValueError("action_inventory_not_canonical")
        if {f.role for f in self.files} != {"raw_bars", "corporate_actions"}:
            raise ValueError("required_file_roles_missing")
        if any(a.acquired_at > self.frozen_at for a in self.acquisitions):
            raise ValueError("acquisition_after_freeze")
        if self.kind == "historical" and self.calendar.volume_session == "synthetic":
            raise ValueError("synthetic_calendar_in_historical_input")
        corrected = self.revision.correction_observed_at
        if corrected is not None and corrected > self.frozen_at:
            raise ValueError("correction_after_freeze")
        return self


class HistoricalBar(HistoricalModel):
    security_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]*$")
    date: date
    open: ExactDecimal = Field(gt=0)
    high: ExactDecimal = Field(gt=0)
    low: ExactDecimal = Field(gt=0)
    close: ExactDecimal = Field(gt=0)
    volume: ExactDecimal = Field(ge=0)
    available_at: datetime
    availability_basis: AvailabilityBasis
    acquisition_id: str = Field(min_length=1)

    @field_validator("available_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def valid_prices(self) -> Self:
        if not self.low <= self.open <= self.high or not self.low <= self.close <= self.high:
            raise ValueError("invalid_ohlcv")
        return self

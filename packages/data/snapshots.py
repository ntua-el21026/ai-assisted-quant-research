"""Integrity-checked local OHLCV snapshots. No provider access or acquisition fallback."""

from __future__ import annotations

import csv
import hashlib
import io
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from packages.data.models import AdjustedDailyBar
from packages.data.quality import SnapshotError, check_missing_sessions


class SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class MarketSession(SnapshotModel):
    date: date
    open_at: datetime
    close_at: datetime

    @model_validator(mode="after")
    def validate_times(self) -> Self:
        if self.open_at.tzinfo is None or self.close_at.tzinfo is None:
            raise ValueError("session timestamps require offsets")
        if self.open_at >= self.close_at:
            raise ValueError("session open must precede close")
        return self

    @property
    def decision_at(self) -> datetime:
        return self.close_at.astimezone(UTC) + timedelta(minutes=1)


class SnapshotFile(SnapshotModel):
    path: str
    format: Literal["csv"]
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SnapshotManifest(SnapshotModel):
    schema_version: Literal["market-snapshot/v1"]
    dataset_id: str = Field(min_length=1)
    kind: Literal["synthetic", "historical"]
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    frozen_at: datetime
    coverage_start: date
    coverage_end: date
    symbols: tuple[str, ...]
    timezone: str
    calendar_name: str = Field(min_length=1)
    sessions: tuple[MarketSession, ...]
    feature_price_basis: str
    execution_price_basis: str
    corporate_action_policy: str
    dividend_policy: str
    missing_session_policy: Literal["warn", "reject"]
    normalization_version: Literal["ohlcv-csv/v1"]
    universe_source: str = Field(min_length=1)
    survivorship_bias: str = Field(min_length=1)
    files: tuple[SnapshotFile, ...] = Field(min_length=1)

    @field_validator("frozen_at")
    @classmethod
    def aware_freeze(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("freeze timestamp requires an offset")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_calendar(self) -> Self:
        if not self.symbols or tuple(sorted(set(self.symbols))) != self.symbols:
            raise ValueError("symbols must be nonempty, sorted and unique")
        if any(not s or s != s.upper() for s in self.symbols):
            raise ValueError("symbols must be uppercase")
        dates = tuple(s.date for s in self.sessions)
        if not dates or dates != tuple(sorted(set(dates))):
            raise ValueError("calendar must be sorted and unique")
        if dates[0] != self.coverage_start or dates[-1] != self.coverage_end:
            raise ValueError("calendar coverage must match declared dates")
        try:
            zone = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("unknown timezone") from exc
        for session in self.sessions:
            if (
                session.open_at.astimezone(zone).date() != session.date
                or session.close_at.astimezone(zone).date() != session.date
                or session.close_at > self.frozen_at
            ):
                raise ValueError("session timestamp outside declared date/freeze")
        if len({f.path for f in self.files}) != len(self.files):
            raise ValueError("duplicate file paths")
        return self


@dataclass(frozen=True)
class DatasetSnapshot:
    dataset_id: str
    manifest_sha256: str
    feature_bars_by_symbol: Mapping[str, tuple[AdjustedDailyBar, ...]]
    execution_bars_by_symbol: Mapping[str, tuple[AdjustedDailyBar, ...]]
    warnings: tuple[str, ...]
    sessions: tuple[MarketSession, ...]
    availability_by_key: Mapping[tuple[str, date], datetime]
    manifest: SnapshotManifest

    @property
    def session_by_date(self) -> Mapping[date, MarketSession]:
        return MappingProxyType({s.date: s for s in self.sessions})


def load_dataset_snapshot(manifest_path: Path) -> DatasetSnapshot:
    try:
        raw_manifest = manifest_path.read_bytes()
    except OSError as exc:
        raise SnapshotError("missing_manifest", manifest_path.name) from exc
    try:
        manifest = SnapshotManifest.model_validate_json(raw_manifest)
    except (ValidationError, ValueError) as exc:
        raise SnapshotError("invalid_manifest", str(exc)) from exc
    if manifest.feature_price_basis != "raw" or manifest.execution_price_basis != "raw":
        raise SnapshotError(
            "unsupported_price_basis", "v1 requires raw feature and execution prices"
        )
    if (
        manifest.corporate_action_policy != "none_in_coverage"
        or manifest.dividend_policy != "none_in_coverage"
    ):
        raise SnapshotError(
            "unsupported_corporate_actions", "v1 requires action/dividend-free coverage"
        )
    root = manifest_path.parent.resolve()
    bars: dict[str, list[AdjustedDailyBar]] = {s: [] for s in manifest.symbols}
    availability: dict[tuple[str, date], datetime] = {}
    calendar = {s.date: s for s in manifest.sessions}
    last_key: tuple[str, date] | None = None
    required = ["symbol", "date", "open", "high", "low", "close", "volume", "available_at"]
    for entry in manifest.files:
        relative = Path(entry.path)
        path = (root / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root):
            raise SnapshotError("unsafe_path", entry.path)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise SnapshotError("missing_file", entry.path) from exc
        if len(data) != entry.size_bytes:
            raise SnapshotError("size_mismatch", entry.path)
        if hashlib.sha256(data).hexdigest() != entry.sha256:
            raise SnapshotError("hash_mismatch", entry.path)
        try:
            reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
            if reader.fieldnames != required:
                raise SnapshotError("invalid_schema", entry.path)
            for row in reader:
                try:
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError("incomplete row")
                    values = {k: row[k] for k in required if k != "available_at"}
                    bar = AdjustedDailyBar.model_validate(
                        {
                            **values,
                            "adjusted": False,
                            "provider": manifest.source,
                            "payload_hash": entry.sha256,
                        }
                    )
                    if not all(
                        math.isfinite(getattr(bar, k)) for k in ("open", "high", "low", "close")
                    ):
                        raise ValueError("nonfinite OHLC")
                except (ValidationError, ValueError, TypeError) as exc:
                    raise SnapshotError("invalid_ohlcv", entry.path) from exc
                key = (bar.symbol, bar.date)
                if key in availability:
                    raise SnapshotError("duplicate_session", f"{bar.symbol}:{bar.date}")
                if last_key is not None and key < last_key:
                    raise SnapshotError("unsorted_rows", entry.path)
                last_key = key
                session = calendar.get(bar.date)
                if session is None:
                    raise SnapshotError("unexpected_session", str(bar.date))
                if bar.symbol not in bars:
                    raise SnapshotError("unexpected_symbol", bar.symbol)
                try:
                    available_at = datetime.fromisoformat(row["available_at"])
                    if (
                        available_at.tzinfo is None
                        or available_at < session.close_at
                        or available_at > manifest.frozen_at
                    ):
                        raise ValueError("availability outside close/freeze")
                except (ValueError, TypeError) as exc:
                    raise SnapshotError("invalid_availability", f"{bar.symbol}:{bar.date}") from exc
                bars[bar.symbol].append(bar)
                availability[key] = available_at.astimezone(UTC)
        except (UnicodeError, csv.Error) as exc:
            raise SnapshotError("invalid_schema", entry.path) from exc
    warnings = list(check_missing_sessions(bars, tuple(calendar), manifest.missing_session_policy))
    warnings.extend(
        (
            f"dataset_kind:{manifest.kind}",
            f"calendar_assumption:{manifest.calendar_name}",
            f"universe_limitation:{manifest.survivorship_bias}",
            "raw_prices_action_and_dividend_free_coverage_required",
        )
    )
    frozen_bars = MappingProxyType({s: tuple(bars[s]) for s in sorted(bars)})
    return DatasetSnapshot(
        manifest.dataset_id,
        hashlib.sha256(raw_manifest).hexdigest(),
        frozen_bars,
        frozen_bars,
        tuple(warnings),
        manifest.sessions,
        MappingProxyType(availability),
        manifest,
    )

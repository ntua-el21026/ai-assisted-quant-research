"""Read-only, source-documented US core sessions for the bounded R4-B window.

The explicit schedule is independent of provider observations. It does not qualify
provider daily aggregation, historical publication latency, or intraday halts.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from packages.data.historical_models import HistoricalSession

_NEW_YORK = ZoneInfo("America/New_York")
_YEAR_COUNTS = {
    2020: (253, 2),
    2021: (252, 1),
    2022: (251, 1),
    2023: (250, 2),
    2024: (252, 3),
    2025: (250, 3),
}


class _CalendarModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Source(_CalendarModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    published_on: date | None
    consulted_on: Literal["2026-11-17"]
    evidence_role: str = Field(min_length=1)


class _SupplementalClosure(_CalendarModel):
    date: date
    reason: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)


class _Year(_CalendarModel):
    year: int = Field(strict=True)
    source_id: str = Field(min_length=1)
    closed_dates: tuple[date, ...]
    early_close_dates: tuple[date, ...]
    supplemental_closures: tuple[_SupplementalClosure, ...]
    expected_sessions: int = Field(strict=True)
    expected_early_closes: int = Field(strict=True)


class _CalendarSpec(_CalendarModel):
    schema_version: Literal["research-calendar/v1"]
    name: Literal["US core prices"]
    timezone: Literal["America/New_York"]
    coverage_start: date
    coverage_end: date
    price_session: Literal["regular"]
    regular_open: Literal["09:30"]
    regular_close: Literal["16:00"]
    early_close: Literal["13:00"]
    status: Literal["official_schedule_qualified"]
    qualification_basis: str = Field(min_length=1)
    sources: tuple[_Source, ...] = Field(min_length=1)
    years: tuple[_Year, ...]


@dataclass(frozen=True)
class ResearchCalendar:
    """Validated sessions and identity of the exact locally read schedule bytes."""

    sessions: tuple[HistoricalSession, ...]
    sha256: str
    source_refs: tuple[str, ...]
    status: Literal["official_schedule_qualified"]
    warnings: tuple[str, ...]


def _unique_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("calendar_duplicate_json_key")
        result[key] = value
    return result


def load_research_calendar(path: Path, *, expected_sha256: str | None = None) -> ResearchCalendar:
    """Read the complete 2020–2025 schedule without network access or writes.

    Pin ``expected_sha256`` when reusing a frozen private candidate. Source URLs
    document the transcribed facts; this input digest is not a document checksum.
    """
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and (
        re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None or digest != expected_sha256
    ):
        raise ValueError("calendar_hash_mismatch")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_json_keys)
        spec = _CalendarSpec.model_validate(value)
    except (ValidationError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("calendar_invalid_schema") from None
    if (
        spec.coverage_start != date(2020, 1, 1)
        or spec.coverage_end != date(2025, 12, 31)
        or tuple(year.year for year in spec.years) != tuple(_YEAR_COUNTS)
    ):
        raise ValueError("calendar_coverage_mismatch")
    source_ids = {source.source_id for source in spec.sources}
    if len(source_ids) != len(spec.sources):
        raise ValueError("calendar_duplicate_source")
    for source in spec.sources:
        url = urlsplit(source.url)
        if (
            url.scheme != "https"
            or url.hostname not in {"www.nyse.com", "ir.theice.com", "www.nasdaqtrader.com"}
            or url.username is not None
            or url.password is not None
            or (source.published_on is not None and source.published_on > date(2026, 11, 17))
        ):
            raise ValueError("calendar_invalid_source")
    sessions: list[HistoricalSession] = []
    for year in spec.years:
        references = (
            year.source_id,
            *(s for c in year.supplemental_closures for s in c.source_ids),
        )
        if not set(references) <= source_ids:
            raise ValueError("calendar_unknown_source")
        expected = _YEAR_COUNTS[year.year]
        if (year.expected_sessions, year.expected_early_closes) != expected:
            raise ValueError("calendar_declared_counts_mismatch")
        closed = (*year.closed_dates, *(c.date for c in year.supplemental_closures))
        early = set(year.early_close_dates)
        if len(set(closed)) != len(closed) or len(early) != len(year.early_close_dates):
            raise ValueError("calendar_duplicate_date")
        if any(d.year != year.year or d.weekday() >= 5 for d in (*closed, *early)):
            raise ValueError("calendar_invalid_date")
        if early & set(closed):
            raise ValueError("calendar_early_close_on_closed_day")
        current = date(year.year, 1, 1)
        stop = date(year.year + 1, 1, 1)
        year_sessions: list[HistoricalSession] = []
        while current < stop:
            if current.weekday() < 5 and current not in closed:
                early_close = current in early
                year_sessions.append(
                    HistoricalSession(
                        date=current,
                        open_at=datetime.combine(current, time(9, 30), _NEW_YORK),
                        close_at=datetime.combine(
                            current, time(13 if early_close else 16), _NEW_YORK
                        ),
                        early_close=early_close,
                    )
                )
            current += timedelta(days=1)
        if (len(year_sessions), len(early)) != expected:
            raise ValueError("calendar_generated_counts_mismatch")
        sessions.extend(year_sessions)
    return ResearchCalendar(
        sessions=tuple(sessions),
        sha256=digest,
        source_refs=tuple(sorted(source.url for source in spec.sources)),
        status=spec.status,
        warnings=(
            "calendar_sources_not_provider_aggregation",
            "calendar_not_independent_runtime_oracle",
        ),
    )

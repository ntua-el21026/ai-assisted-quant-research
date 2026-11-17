"""Official schedule facts, literal date regressions, and immutable input identity."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import pytest

CONFIG = Path("experiments/configs/r4b_calendar_2020_2025.json")


def calendar_module() -> Any:
    try:
        return importlib.import_module("packages.data.research_calendar")
    except ModuleNotFoundError:
        pytest.fail("research calendar loader is not implemented")


def changed_config(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    target = tmp_path / "calendar.json"
    return target, json.loads(CONFIG.read_bytes())


def write_config(path: Path, value: object) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_calendar_has_literal_annual_counts_and_exceptional_closure() -> None:
    calendar = calendar_module().load_research_calendar(CONFIG)
    assert len(calendar.sessions) == 1508
    assert Counter(s.date.year for s in calendar.sessions) == {
        2020: 253,
        2021: 252,
        2022: 251,
        2023: 250,
        2024: 252,
        2025: 250,
    }
    assert sum(s.early_close for s in calendar.sessions) == 12
    dates = tuple(s.date for s in calendar.sessions)
    assert dates == tuple(sorted(set(dates)))
    assert dates[0] == date(2020, 1, 2)
    assert dates[-1] == date(2025, 12, 31)
    assert date(2025, 1, 9) not in dates
    assert date(2021, 12, 31) in dates
    assert date(2021, 6, 18) in dates
    assert date(2022, 6, 20) not in dates


@pytest.mark.parametrize(
    ("day", "opening", "closing", "early"),
    [
        ("2024-03-08", "2024-03-08T14:30:00+00:00", "2024-03-08T21:00:00+00:00", False),
        ("2024-03-11", "2024-03-11T13:30:00+00:00", "2024-03-11T20:00:00+00:00", False),
        ("2024-11-01", "2024-11-01T13:30:00+00:00", "2024-11-01T20:00:00+00:00", False),
        ("2024-11-04", "2024-11-04T14:30:00+00:00", "2024-11-04T21:00:00+00:00", False),
        ("2025-07-03", "2025-07-03T13:30:00+00:00", "2025-07-03T17:00:00+00:00", True),
        ("2025-12-24", "2025-12-24T14:30:00+00:00", "2025-12-24T18:00:00+00:00", True),
    ],
)
def test_core_session_hours_follow_dst_and_declared_early_closes(
    day: str, opening: str, closing: str, early: bool
) -> None:
    sessions = calendar_module().load_research_calendar(CONFIG).sessions
    session = next(s for s in sessions if s.date.isoformat() == day)
    assert session.open_at.isoformat() == opening
    assert session.close_at.isoformat() == closing
    assert session.early_close is early


def test_input_hash_pins_exact_bytes_without_claiming_source_document_hashes(
    tmp_path: Path,
) -> None:
    module = calendar_module()
    raw = CONFIG.read_bytes()
    expected = hashlib.sha256(raw).hexdigest()
    calendar = module.load_research_calendar(CONFIG, expected_sha256=expected)
    assert calendar.sha256 == expected
    assert calendar.status == "official_schedule_qualified"
    assert "calendar_sources_not_provider_aggregation" in calendar.warnings
    assert "calendar_not_independent_runtime_oracle" in calendar.warnings
    assert any("Jimmy-Carter" in url for url in calendar.source_refs)
    assert all(url.startswith("https://") for url in calendar.source_refs)
    changed = tmp_path / "calendar.json"
    changed.write_bytes(raw + b"\n")
    with pytest.raises(ValueError, match="calendar_hash_mismatch"):
        module.load_research_calendar(changed, expected_sha256=expected)
    assert module.load_research_calendar(changed).sha256 != expected


@pytest.mark.parametrize("mutation", ["missing_holiday", "missing_carter", "wrong_year_count"])
def test_omitted_closures_or_changed_acceptance_counts_fail(tmp_path: Path, mutation: str) -> None:
    module = calendar_module()
    target, payload = changed_config(tmp_path)
    if mutation == "missing_holiday":
        payload["years"][4]["closed_dates"].remove("2024-03-29")
    elif mutation == "missing_carter":
        payload["years"][5]["supplemental_closures"] = []
    else:
        payload["years"][4]["expected_sessions"] = 253
    write_config(target, payload)
    with pytest.raises(ValueError, match="calendar_.*count"):
        module.load_research_calendar(target)


@pytest.mark.parametrize(
    "mutation",
    ["duplicate_closure", "early_on_closed_day", "weekend_closure", "wrong_year", "missing_year"],
)
def test_invalid_date_tables_fail(tmp_path: Path, mutation: str) -> None:
    module = calendar_module()
    target, payload = changed_config(tmp_path)
    year = payload["years"][4]
    if mutation == "duplicate_closure":
        year["closed_dates"].append("2024-03-29")
    elif mutation == "early_on_closed_day":
        year["early_close_dates"][0] = "2024-07-04"
    elif mutation == "weekend_closure":
        year["closed_dates"][0] = "2024-01-06"
    elif mutation == "wrong_year":
        year["early_close_dates"][0] = "2025-07-03"
    else:
        payload["years"].pop()
    write_config(target, payload)
    with pytest.raises(ValueError, match="calendar_"):
        module.load_research_calendar(target)


@pytest.mark.parametrize("mutation", ["missing_source", "duplicate_source", "unknown_source"])
def test_source_provenance_is_required(tmp_path: Path, mutation: str) -> None:
    module = calendar_module()
    target, payload = changed_config(tmp_path)
    if mutation == "missing_source":
        payload["sources"][0].pop("published_on")
    elif mutation == "duplicate_source":
        payload["sources"].append(payload["sources"][0])
    else:
        payload["years"][0]["source_id"] = "unregistered"
    write_config(target, payload)
    with pytest.raises(ValueError, match="calendar_"):
        module.load_research_calendar(target)


def test_ambiguous_duplicate_json_keys_fail(tmp_path: Path) -> None:
    module = calendar_module()
    target = tmp_path / "calendar.json"
    target.write_text('{"schema_version":"research-calendar/v1","schema_version":"other"}')
    with pytest.raises(ValueError, match="calendar_duplicate_json_key"):
        module.load_research_calendar(target)

"""Integrity and quality regressions using original synthetic inputs."""

import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest

FIXTURE = Path("tests/fixtures/market_snapshot/manifest.json")


def copy_snapshot(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURE.parent, tmp_path / "snapshot")
    return tmp_path / "snapshot/manifest.json"


def rewrite(path: Path, *, rows: list[dict[str, str]] | None = None, **changes: object) -> None:
    manifest = json.loads(path.read_text())
    if rows is not None:
        data_path = path.parent / "bars.csv"
        with data_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0], lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        data = data_path.read_bytes()
        manifest["files"][0].update(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    manifest.update(changes)
    path.write_text(json.dumps(manifest))


def test_valid_snapshot_is_deterministic_and_raw() -> None:
    from packages.data.snapshots import load_dataset_snapshot

    first = load_dataset_snapshot(FIXTURE)
    second = load_dataset_snapshot(FIXTURE)
    assert first == second
    assert first.dataset_id == "synthetic-reference-v1"
    assert tuple(first.execution_bars_by_symbol) == ("AAPL", "QQQ", "SPY")
    assert len(first.execution_bars_by_symbol["SPY"]) == 210
    assert not first.execution_bars_by_symbol["SPY"][0].adjusted
    assert first.warnings
    with pytest.raises(TypeError):
        first.execution_bars_by_symbol["OTHER"] = ()


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("duplicate", "duplicate_session"),
        ("unsorted", "unsorted_rows"),
        ("ohlc", "invalid_ohlcv"),
        ("nan", "invalid_ohlcv"),
        ("timestamp", "invalid_availability"),
        ("early", "invalid_availability"),
        ("unknown_session", "unexpected_session"),
        ("negative_volume", "invalid_ohlcv"),
    ],
)
def test_bad_rows_are_rejected(tmp_path: Path, mutation: str, code: str) -> None:
    from packages.data.snapshots import load_dataset_snapshot

    path = copy_snapshot(tmp_path)
    rows = list(csv.DictReader((path.parent / "bars.csv").open()))
    if mutation == "duplicate":
        rows.insert(1, rows[0].copy())
    elif mutation == "unsorted":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "ohlc":
        rows[0]["low"] = "999"
    elif mutation == "nan":
        rows[0]["close"] = "nan"
    elif mutation == "timestamp":
        rows[0]["available_at"] = "2025-01-02T21:00:30"
    elif mutation == "early":
        rows[0]["available_at"] = "2025-01-02T10:00:00Z"
    elif mutation == "unknown_session":
        rows[0]["date"] = "2025-01-04"
    else:
        rows[0]["volume"] = "-1"
    rewrite(path, rows=rows)
    with pytest.raises(ValueError, match=code):
        load_dataset_snapshot(path)


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"feature_price_basis": "adjusted"}, "unsupported_price_basis"),
        ({"execution_price_basis": None}, "invalid_manifest"),
        ({"corporate_action_policy": "splits_ignored"}, "unsupported_corporate_actions"),
        ({"frozen_at": "2025-12-01"}, "invalid_manifest"),
    ],
)
def test_unsupported_manifest(tmp_path: Path, change: dict[str, object], code: str) -> None:
    from packages.data.snapshots import load_dataset_snapshot

    path = copy_snapshot(tmp_path)
    rewrite(path, **change)
    with pytest.raises(ValueError, match=code):
        load_dataset_snapshot(path)


def test_integrity_and_missing_file(tmp_path: Path) -> None:
    from packages.data.snapshots import load_dataset_snapshot

    path = copy_snapshot(tmp_path)
    data = path.parent / "bars.csv"
    data.write_bytes(data.read_bytes().replace(b"100.00", b"101.00", 1))
    with pytest.raises(ValueError, match="hash_mismatch"):
        load_dataset_snapshot(path)
    data.unlink()
    with pytest.raises(ValueError, match="missing_file"):
        load_dataset_snapshot(path)


def test_missing_session_warn_or_fail(tmp_path: Path) -> None:
    from packages.data.snapshots import load_dataset_snapshot

    path = copy_snapshot(tmp_path)
    rows = list(csv.DictReader((path.parent / "bars.csv").open()))
    del rows[2]
    rewrite(path, rows=rows)
    assert any("missing_session:AAPL:2025-01-06" in w for w in load_dataset_snapshot(path).warnings)
    rewrite(path, missing_session_policy="reject")
    with pytest.raises(ValueError, match="missing_session"):
        load_dataset_snapshot(path)


def test_paths_cannot_escape_snapshot(tmp_path: Path) -> None:
    from packages.data.snapshots import load_dataset_snapshot

    path = copy_snapshot(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["files"][0]["path"] = "../outside.csv"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsafe_path"):
        load_dataset_snapshot(path)


def test_size_and_schema_are_verified(tmp_path: Path) -> None:
    from packages.data.snapshots import load_dataset_snapshot

    path = copy_snapshot(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["files"][0]["size_bytes"] += 1
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="size_mismatch"):
        load_dataset_snapshot(path)
    manifest["files"][0]["size_bytes"] -= 1
    manifest["schema_version"] = "future/v999"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="invalid_manifest"):
        load_dataset_snapshot(path)


def test_calendar_timestamps_and_duplicate_calendar_rejected(tmp_path: Path) -> None:
    from packages.data.snapshots import load_dataset_snapshot

    path = copy_snapshot(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["sessions"].insert(1, manifest["sessions"][0])
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="invalid_manifest"):
        load_dataset_snapshot(path)

"""Synthetic v2 provenance and causality regressions; expectations are literal."""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from packages.data.quality import SnapshotError
from packages.data.snapshots import load_dataset_snapshot

FIXTURE = Path("tests/fixtures/historical_snapshot")


def _module():
    try:
        return importlib.import_module("packages.data.historical_snapshots")
    except ModuleNotFoundError:
        pytest.fail("v2 historical snapshot implementation missing")


def _copy(tmp_path: Path) -> Path:
    root = tmp_path / "snapshot"
    shutil.copytree(FIXTURE, root)
    return root / "manifest.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def _replace_file(manifest_path: Path, role: str, rows: list) -> None:
    manifest = _json(manifest_path)
    descriptor = next(f for f in manifest["files"] if f["role"] == role)
    path = manifest_path.parent / descriptor["path"]
    _write(path, rows)
    descriptor["size_bytes"] = path.stat().st_size
    descriptor["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write(manifest_path, manifest)


def _query_symbols(receipt: dict, symbols: list[str]) -> None:
    receipt["symbols"] = symbols
    query = dict(receipt["query_parameters"])
    query["symbols"] = ",".join(symbols)
    receipt["query_parameters"] = sorted(query.items())
    receipt["page_query_sha256"][0] = hashlib.sha256(
        json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_v2_loads_exact_raw_prices_actions_and_provenance() -> None:
    snapshot = _module().load_historical_snapshot(FIXTURE / "manifest.json")
    assert snapshot.manifest.schema_version == "market-snapshot/v2"
    assert snapshot.manifest.kind == "synthetic"
    assert [b.close for b in snapshot.raw_bars] == [
        Decimal("400"),
        Decimal("100"),
        Decimal("99"),
        Decimal("9.9"),
        Decimal("10"),
        Decimal("11"),
    ]
    assert [a.action_id for a in snapshot.actions] == ["split-4", "cash-1", "split-10"]
    assert (
        snapshot.manifest_sha256
        == hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
    )


def test_future_splits_cannot_restate_an_earlier_feature_view() -> None:
    snapshot = _module().load_historical_snapshot(FIXTURE / "manifest.json")
    before = snapshot.feature_view(datetime(2024, 3, 8, 21, 1, tzinfo=UTC), basis="split_asof")
    assert [b.close for b in before.bars] == [Decimal("400")]
    assert before.action_ids == ()
    after = snapshot.feature_view(datetime(2024, 3, 11, 20, 1, tzinfo=UTC), basis="split_asof")
    assert [b.close for b in after.bars] == [Decimal("100"), Decimal("100")]
    assert after.bars[0].volume == Decimal("4000")
    assert after.action_ids == ("split-4",)
    later = snapshot.feature_view(datetime(2024, 3, 13, 20, 1, tzinfo=UTC), basis="split_asof")
    assert [b.close for b in later.bars] == [
        Decimal("10"),
        Decimal("10"),
        Decimal("9.9"),
        Decimal("9.9"),
    ]
    assert later.bars[0].volume == Decimal("40000")
    assert later.action_ids == ("split-4", "split-10")


def test_raw_feature_view_does_not_apply_dividend_or_split_prices() -> None:
    snapshot = _module().load_historical_snapshot(FIXTURE / "manifest.json")
    view = snapshot.feature_view(datetime(2024, 3, 15, 20, 1, tzinfo=UTC), basis="raw")
    assert view.bars == snapshot.raw_bars
    assert view.action_ids == ()


@pytest.mark.parametrize("basis", ["all", "dividend", "split", "fully_adjusted"])
def test_unsupported_feature_adjustment_is_explicit(basis: str) -> None:
    snapshot = _module().load_historical_snapshot(FIXTURE / "manifest.json")
    with pytest.raises(ValueError, match="unsupported_feature_basis"):
        snapshot.feature_view(datetime(2024, 3, 15, 20, 1, tzinfo=UTC), basis=basis)


def test_unavailable_close_is_not_exposed_to_features(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    rows = json.loads((manifest.parent / "bars.json").read_bytes())
    rows[0]["available_at"] = "2024-03-11T21:00:00Z"
    _replace_file(manifest, "raw_bars", rows)
    snapshot = _module().load_historical_snapshot(manifest)
    view = snapshot.feature_view(datetime(2024, 3, 8, 21, 1, tzinfo=UTC), basis="raw")
    assert view.bars == ()


def test_effective_but_unavailable_split_fails_closed(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    actions = json.loads((manifest.parent / "actions.json").read_bytes())
    actions[0]["available_at"] = "2024-03-12T13:30:00Z"
    _replace_file(manifest, "corporate_actions", actions)
    snapshot = _module().load_historical_snapshot(manifest)
    with pytest.raises(ValueError, match="action_unavailable"):
        snapshot.feature_view(datetime(2024, 3, 11, 20, 1, tzinfo=UTC), basis="split_asof")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "market-snapshot/v3"),
        ("execution_price_basis", "all"),
        ("feature_policy", "provider_all"),
        ("action_coverage", "unknown"),
        ("expected_action_ids", ["split-4", "cash-1"]),
        ("acquisitions", []),
        ("action_inventory_source", ""),
        ("frozen_at", "2024-03-15T00:00:00Z"),
    ],
)
def test_incomplete_or_inconsistent_manifest_fails(
    tmp_path: Path, field: str, value: object
) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    payload[field] = value
    _write(manifest, payload)
    with pytest.raises(SnapshotError):
        _module().load_historical_snapshot(manifest)


@pytest.mark.parametrize("mode", ["hash", "size", "missing", "unsafe", "symlink"])
def test_frozen_file_integrity_fails_closed(tmp_path: Path, mode: str) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    if mode == "hash":
        payload["files"][0]["sha256"] = "0" * 64
    elif mode == "size":
        payload["files"][0]["size_bytes"] += 1
    elif mode == "missing":
        (manifest.parent / "bars.json").unlink()
    elif mode == "unsafe":
        payload["files"][0]["path"] = "../bars.json"
    else:
        (manifest.parent / "bars.json").rename(manifest.parent / "original.json")
        (manifest.parent / "bars.json").symlink_to("original.json")
    _write(manifest, payload)
    with pytest.raises(SnapshotError):
        _module().load_historical_snapshot(manifest)


@pytest.mark.parametrize(
    "mode",
    ["duplicate", "missing", "bad_ohlc", "unknown_id", "early_availability", "after_acquisition"],
)
def test_invalid_observations_are_rejected(tmp_path: Path, mode: str) -> None:
    manifest = _copy(tmp_path)
    rows = json.loads((manifest.parent / "bars.json").read_bytes())
    if mode == "duplicate":
        rows.append(rows[0])
    elif mode == "missing":
        rows.pop()
    elif mode == "bad_ohlc":
        rows[0]["low"] = "500"
    elif mode == "unknown_id":
        rows[0]["security_id"] = "unknown"
    elif mode == "early_availability":
        rows[0]["available_at"] = "2024-03-08T20:59:00Z"
    else:
        rows[0]["available_at"] = "2024-03-17T21:00:00Z"
    _replace_file(manifest, "raw_bars", rows)
    with pytest.raises(SnapshotError):
        _module().load_historical_snapshot(manifest)


def test_row_order_is_normalized_without_changing_identity(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    original = _module().load_historical_snapshot(manifest)
    rows = json.loads((manifest.parent / "bars.json").read_bytes())
    _replace_file(manifest, "raw_bars", list(reversed(rows)))
    reordered = _module().load_historical_snapshot(manifest)
    assert reordered.raw_bars == original.raw_bars
    assert reordered.manifest_sha256 != original.manifest_sha256


def test_declared_missing_observation_has_an_explicit_exclusion(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    payload["missing_session_policy"] = "exclude"
    payload["exclusions"] = [
        {"security_id": "synthetic:001", "date": "2024-03-15", "reason": "synthetic_missing"}
    ]
    _write(manifest, payload)
    rows = json.loads((manifest.parent / "bars.json").read_bytes())[:-1]
    _replace_file(manifest, "raw_bars", rows)
    snapshot = _module().load_historical_snapshot(manifest)
    assert len(snapshot.raw_bars) == 5
    assert any("missing_session:synthetic:001:2024-03-15" in w for w in snapshot.warnings)


def test_dst_and_early_close_calendar_metadata_are_preserved(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    payload["sessions"][-1]["close_at"] = "2024-03-15T17:00:00Z"
    payload["sessions"][-1]["early_close"] = True
    _write(manifest, payload)
    snapshot = _module().load_historical_snapshot(manifest)
    assert snapshot.manifest.sessions[0].open_at.hour == 14
    assert snapshot.manifest.sessions[1].open_at.hour == 13
    assert snapshot.manifest.sessions[-1].early_close


def test_uncertain_point_in_time_identity_requires_explicit_restricted_mode(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    payload["securities"][0]["mappings"][0]["point_in_time_status"] = "uncertain"
    _write(manifest, payload)
    with pytest.raises(SnapshotError, match="uncertain_identity"):
        _module().load_historical_snapshot(manifest)
    payload["identity_policy"] = "allow_uncertain"
    _write(manifest, payload)
    snapshot = _module().load_historical_snapshot(manifest)
    assert any("uncertain_identity" in w for w in snapshot.warnings)


def test_symbol_rename_retains_security_identity_and_cutoff_availability(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    first = payload["securities"][0]["mappings"][0]
    first["end"] = "2024-03-12"
    second = {
        **first,
        "symbol": "NEW",
        "start": "2024-03-13",
        "end": "2024-03-15",
        "available_at": "2024-03-13T12:00:00Z",
    }
    payload["securities"][0]["mappings"].append(second)
    for receipt in payload["acquisitions"]:
        _query_symbols(receipt, ["NEW", "SYN"])
    _write(manifest, payload)
    rows = json.loads((manifest.parent / "bars.json").read_bytes())
    for row in rows[3:]:
        row["symbol"] = "NEW"
    _replace_file(manifest, "raw_bars", rows)
    actions = json.loads((manifest.parent / "actions.json").read_bytes())
    actions[-1]["symbol"] = "NEW"
    _replace_file(manifest, "corporate_actions", actions)
    snapshot = _module().load_historical_snapshot(manifest)
    assert {b.security_id for b in snapshot.raw_bars} == {"synthetic:001"}
    before = snapshot.feature_view(datetime(2024, 3, 12, 20, 1, tzinfo=UTC), basis="raw")
    assert all(b.symbol == "SYN" for b in before.bars)


def test_revision_records_new_identity_and_preserves_original_bytes(tmp_path: Path) -> None:
    original_path = _copy(tmp_path)
    original_bytes = original_path.read_bytes()
    original = _module().load_historical_snapshot(original_path)
    revised_root = tmp_path / "revision"
    shutil.copytree(original_path.parent, revised_root)
    revised_path = revised_root / "manifest.json"
    payload = _json(revised_path)
    payload["revision"] = {
        "revision_id": "synthetic-r2",
        "parent_manifest_sha256": original.manifest_sha256,
        "correction_observed_at": "2024-03-16T12:00:00Z",
        "reason": "synthetic correction",
    }
    _write(revised_path, payload)
    revised = _module().load_historical_snapshot(revised_path)
    assert revised.manifest_sha256 != original.manifest_sha256
    assert original_path.read_bytes() == original_bytes


@pytest.mark.parametrize("permission", ["entitlement", "storage", "retention"])
def test_historical_snapshot_requires_confirmed_rights(tmp_path: Path, permission: str) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    payload["kind"] = "historical"
    payload["calendar"]["volume_session"] = "full_day"
    for receipt in payload["acquisitions"]:
        receipt["mocked"] = False
        receipt["provider"] = "alpaca"
    payload["license"][permission] = "requires_clarification"
    _write(manifest, payload)
    with pytest.raises(SnapshotError, match="unconfirmed_data_rights"):
        _module().load_historical_snapshot(manifest)


def test_v1_contract_is_unchanged_and_does_not_silently_load_v2() -> None:
    assert (
        load_dataset_snapshot(
            Path("tests/fixtures/market_snapshot/manifest.json")
        ).manifest.schema_version
        == "market-snapshot/v1"
    )
    with pytest.raises(SnapshotError, match="invalid_manifest"):
        load_dataset_snapshot(FIXTURE / "manifest.json")
    _module()


def test_manifest_pin_detects_a_new_revision_before_reading_files(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    pinned = hashlib.sha256(manifest.read_bytes()).hexdigest()
    payload = _json(manifest)
    payload["dataset_id"] = "changed"
    _write(manifest, payload)
    with pytest.raises(SnapshotError, match="manifest_hash_mismatch"):
        _module().load_historical_snapshot(manifest, expected_sha256=pinned)


def test_future_correction_cannot_restate_past_feature_inputs(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    payload["revision"] = {
        "revision_id": "corrected",
        "parent_manifest_sha256": "a" * 64,
        "correction_observed_at": "2024-03-16T12:00:00Z",
        "reason": "synthetic correction",
    }
    _write(manifest, payload)
    snapshot = _module().load_historical_snapshot(manifest)
    with pytest.raises(ValueError, match="revision_not_available_at_cutoff"):
        snapshot.feature_view(datetime(2024, 3, 15, 20, 1, tzinfo=UTC), basis="raw")


@pytest.mark.parametrize("section", ["source", "action_inventory_source", "license"])
def test_blank_essential_provenance_is_rejected(tmp_path: Path, section: str) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    if section == "license":
        payload["license"]["reference"] = "   "
    else:
        payload[section] = "   "
    _write(manifest, payload)
    with pytest.raises(SnapshotError):
        _module().load_historical_snapshot(manifest)


def test_availability_policy_must_bind_record_evidence_basis(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    payload["historical_availability"] = {
        "mode": "observed",
        "statement": "synthetic observations do not prove this",
        "evidence_reference": "synthetic unsupported claim",
    }
    _write(manifest, payload)
    with pytest.raises(SnapshotError, match="availability_basis_mismatch"):
        _module().load_historical_snapshot(manifest)


def test_feature_arithmetic_is_independent_of_ambient_decimal_context() -> None:
    from decimal import Inexact, localcontext

    snapshot = _module().load_historical_snapshot(FIXTURE / "manifest.json")
    with localcontext() as context:
        context.prec = 2
        context.Emax = 1
        context.Emin = -1
        context.traps[Inexact] = True
        view = snapshot.feature_view(datetime(2024, 3, 13, 20, 1, tzinfo=UTC), basis="split_asof")
    assert view.bars[0].close == Decimal("10")
    assert view.bars[0].volume == Decimal("40000")


def test_action_identity_must_be_available_before_feature_adjustment(tmp_path: Path) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    old = payload["securities"][0]["mappings"][0]
    old["end"] = "2024-03-08"
    payload["securities"][0]["mappings"].append(
        {
            **old,
            "symbol": "NEW",
            "start": "2024-03-11",
            "end": "2024-03-15",
            "available_at": "2024-03-14T12:00:00Z",
        }
    )
    for receipt in payload["acquisitions"]:
        _query_symbols(receipt, ["NEW", "SYN"])
    _write(manifest, payload)
    rows = json.loads((manifest.parent / "bars.json").read_bytes())
    for row in rows[1:]:
        row["symbol"] = "NEW"
    _replace_file(manifest, "raw_bars", rows)
    actions = json.loads((manifest.parent / "actions.json").read_bytes())
    for action in actions:
        action["symbol"] = "NEW"
    _replace_file(manifest, "corporate_actions", actions)
    snapshot = _module().load_historical_snapshot(manifest)
    with pytest.raises(SnapshotError, match="action_identity_unavailable"):
        snapshot.feature_view(datetime(2024, 3, 11, 20, 1, tzinfo=UTC), basis="split_asof")


@pytest.mark.parametrize("mode", ["synthetic_mapping", "premature_bar", "premature_action"])
def test_historical_observation_evidence_cannot_be_backdated(tmp_path: Path, mode: str) -> None:
    manifest = _copy(tmp_path)
    payload = _json(manifest)
    payload["kind"] = "historical"
    payload["calendar"]["volume_session"] = "full_day"
    payload["historical_availability"]["mode"] = "observed"
    for receipt in payload["acquisitions"]:
        receipt.update(mocked=False, provider="alpaca")
    if mode != "synthetic_mapping":
        payload["securities"][0]["mappings"][0]["availability_basis"] = "observed"
    _write(manifest, payload)
    rows = json.loads((manifest.parent / "bars.json").read_bytes())
    for row in rows:
        row["availability_basis"] = "observed"
        if mode != "premature_bar":
            row["available_at"] = "2024-03-16T10:01:00Z"
    _replace_file(manifest, "raw_bars", rows)
    actions = json.loads((manifest.parent / "actions.json").read_bytes())
    for action in actions:
        action["availability_basis"] = "observed"
        if mode != "premature_action":
            action["available_at"] = "2024-03-16T10:01:00Z"
    _replace_file(manifest, "corporate_actions", actions)
    expected = {
        "synthetic_mapping": "synthetic_identity_in_historical_input",
        "premature_bar": "observed_availability_precedes_acquisition",
        "premature_action": "observed_action_precedes_acquisition",
    }[mode]
    with pytest.raises(SnapshotError, match=expected):
        _module().load_historical_snapshot(manifest)

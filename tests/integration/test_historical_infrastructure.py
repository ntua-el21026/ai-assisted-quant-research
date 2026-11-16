"""Actual synthetic v2 qualification; no historical study or network access."""

from __future__ import annotations

import builtins
import hashlib
import importlib
import json
import shutil
import socket
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

FIXTURE = Path("tests/fixtures/historical_snapshot/manifest.json")


def _runner():
    try:
        return importlib.import_module("packages.research.historical_demo").run_historical_synthetic
    except ModuleNotFoundError:
        pytest.fail("synthetic historical infrastructure runner missing")


def _run(output: Path):
    return _runner()(FIXTURE, output, security_id="synthetic:001", initial_cash=Decimal("1000"))


def test_synthetic_artifacts_contain_independent_literal_accounting(tmp_path: Path) -> None:
    output = tmp_path / "run"
    summary = _run(output)
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert manifest["run_id"] == summary.run_id
    assert manifest["kind"] == "synthetic"
    assert manifest["schema_version"] == "historical-infrastructure-artifacts/v1"
    accounting = json.loads((output / "accounting.json").read_bytes())
    points = accounting["points"]
    assert [Decimal(p["equity"]) for p in points] == [
        Decimal("1000"),
        Decimal("1000"),
        Decimal("1000"),
        Decimal("1000"),
        Decimal("1010"),
        Decimal("1110"),
    ]
    assert Decimal(points[2]["dividend_receivable"]) == 10
    final = points[-1]["state"]
    assert Decimal(final["cash"]) == 10
    assert Decimal(final["positions"][0]["quantity"]) == 100
    assert Decimal(final["positions"][0]["cost_basis"]) == 1000
    assert Decimal(final["positions"][0]["stop_price"]) == 9
    assert Decimal(final["pending_orders"][0]["quantity"]) == 40
    assert Decimal(final["pending_orders"][0]["limit_price"]) == 10
    assert len(final["entitlements"]) == 1
    assert Decimal(final["entitlements"][0]["cash_amount"]) == 10
    assert final["entitlements"][0]["paid"]
    benchmarks = json.loads((output / "benchmarks.json").read_bytes())["results"]
    assert {name: Decimal(value["points"][-1]["equity"]) for name, value in benchmarks.items()} == {
        "price_return": Decimal("1100"),
        "total_return_cash": Decimal("1110"),
        "total_return_reinvest": Decimal("1111"),
    }
    assert "Synthetic" in (output / "report.md").read_text()
    assert manifest["dataset"]["provenance"]["historical_availability"]["mode"] == "synthetic"


def test_two_independent_runs_match_all_indexed_bytes(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    a, b = _run(first), _run(second)
    assert a.run_id == b.run_id
    assert a.deterministic_sha256 == b.deterministic_sha256
    index = json.loads((first / "hashes.json").read_bytes())["sha256"]
    for root in (first, second):
        assert {p.name for p in root.iterdir()} == set(index) | {"hashes.json", "runtime.json"}
        for name, digest in index.items():
            assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    for name in (*index, "hashes.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_ordinary_offline_execution_never_imports_provider_or_uses_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _runner()
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(("packages.data.alpaca", "packages.broker", "urllib.request")):
            pytest.fail(f"provider import forbidden:{name}")
        return original_import(name, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("network forbidden")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    result = runner(
        FIXTURE, tmp_path / "run", security_id="synthetic:001", initial_cash=Decimal(1000)
    )
    assert result.output_dir.exists()


def test_existing_output_is_immutable(tmp_path: Path) -> None:
    output = tmp_path / "run"
    _run(output)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(FileExistsError):
        _run(output)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


def test_corrupt_input_has_no_published_result(tmp_path: Path) -> None:
    root = tmp_path / "input"
    shutil.copytree(FIXTURE.parent, root)
    (root / "bars.json").write_bytes(b"[]")
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="size_mismatch"):
        _runner()(
            root / "manifest.json", output, security_id="synthetic:001", initial_cash=Decimal(1000)
        )
    assert not output.exists()


def test_historical_kind_is_refused_before_observation_files_are_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "input"
    shutil.copytree(FIXTURE.parent, root)
    manifest = root / "manifest.json"
    payload = json.loads(manifest.read_bytes())
    payload["kind"] = "historical"
    manifest.write_text(json.dumps(payload))
    original_read = Path.read_bytes

    def guarded_read(path):
        if path.name in {"bars.json", "actions.json"}:
            pytest.fail("historical observation file must not be read")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(ValueError, match="synthetic_inputs_only"):
        _runner()(
            manifest, tmp_path / "run", security_id="synthetic:001", initial_cash=Decimal(1000)
        )


def test_synthetic_command_runs_in_a_separate_process(tmp_path: Path) -> None:
    _runner()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "packages.research.historical_demo",
            "--dataset",
            str(FIXTURE),
            "--security-id",
            "synthetic:001",
            "--initial-cash",
            "1000",
            "--output",
            str(tmp_path / "cli"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["output_dir"] == str(tmp_path / "cli")


@pytest.mark.parametrize("initial", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
def test_invalid_capital_cannot_publish(tmp_path: Path, initial: Decimal) -> None:
    with pytest.raises(ValueError, match="invalid_initial_cash"):
        _runner()(FIXTURE, tmp_path / "run", security_id="synthetic:001", initial_cash=initial)
    assert not (tmp_path / "run").exists()

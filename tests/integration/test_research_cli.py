"""Offline end-to-end artifact, causality, provenance and publication checks."""

import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CONFIG = Path("experiments/configs/baseline.yaml")
DATASET = Path("tests/fixtures/market_snapshot/manifest.json")
REQUIRED = {
    "manifest.json",
    "config.snapshot.json",
    "trades.csv",
    "equity.csv",
    "metrics.json",
    "comparisons.json",
    "report.md",
    "hashes.json",
    "runtime.json",
}


def invoke(output: Path, *, config: Path = CONFIG, dataset: Path = DATASET):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "packages.research.cli",
            "run",
            "--config",
            str(config),
            "--dataset",
            str(dataset),
            "--output",
            str(output),
        ],
        env={"PATH": os.defpath, "PYTHONHASHSEED": "317"},
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_produces_identical_hashed_complete_results_twice(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    a, b = invoke(first), invoke(second)
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    assert set(p.name for p in first.iterdir()) == REQUIRED
    hashes = json.loads((first / "hashes.json").read_text())["sha256"]
    for name, digest in hashes.items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == digest
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert (first / "hashes.json").read_bytes() == (second / "hashes.json").read_bytes()
    assert "runtime.json" not in hashes
    manifest = json.loads((first / "manifest.json").read_text())
    assert manifest["schema_version"] == "research-artifacts/v1"
    assert manifest["dataset"]["kind"] == "synthetic"
    assert (
        manifest["dataset"]["manifest_sha256"] == hashlib.sha256(DATASET.read_bytes()).hexdigest()
    )
    assert len(manifest["source"]["sha256"]) == 64
    assert manifest["execution_model"] == "research-execution/v1"
    metrics = json.loads((first / "metrics.json").read_text())
    # Independently checked: one share at 174*1.001 plus 1 bp fee,
    # sold after gap at 155*.998 minus 1 bp fee. No other fills.
    assert metrics["values"]["trade_count"] == 1
    assert metrics["accounting"]["final_equity"] == pytest.approx(9980.4831136, abs=1e-8)
    assert metrics["accounting"]["realized_pnl"] == pytest.approx(-19.5168864, abs=1e-8)
    assert metrics["accounting"]["total_fees"] == pytest.approx(0.0328864, abs=1e-8)
    assert metrics["accounting"]["open_positions"] == []
    assert "Synthetic demonstration" in (first / "report.md").read_text()
    assert json.loads((first / "comparisons.json").read_text())["status"] == "deferred_to_R2"


@pytest.mark.parametrize("bad_input", ["config", "dataset", "network_field", "manifest_hash"])
def test_cli_fails_closed_without_publishing(tmp_path: Path, bad_input: str) -> None:
    config, dataset = CONFIG, DATASET
    if bad_input == "config":
        config = tmp_path / "bad.yaml"
        config.write_text("schema_version: invalid\n")
    elif bad_input == "dataset":
        dataset = tmp_path / "absent.json"
    else:
        values = yaml.safe_load(CONFIG.read_text())
        if bad_input == "network_field":
            values["provider_url"] = "https://invalid.example/data"
        else:
            values["dataset_manifest_sha256"] = "0" * 64
        config = tmp_path / "bad.yaml"
        config.write_text(yaml.safe_dump(values))
    output = tmp_path / "result"
    result = invoke(output, config=config, dataset=dataset)
    assert result.returncode != 0
    assert not output.exists()


def test_runner_cannot_use_network_or_broker_modules(tmp_path: Path, monkeypatch) -> None:
    from packages.research.runner import run_research

    def forbidden(*args, **kwargs):
        raise AssertionError("offline runner attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    run_research(CONFIG, DATASET, tmp_path / "offline")
    # A separate process proves the import boundary even when legacy test collection
    # has already imported broker modules in the parent pytest process.
    code = """
import socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError('network forbidden')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from pathlib import Path
from packages.research.runner import run_research
blocked = ('packages.broker', 'packages.paper', 'temporalio')
assert not any(n.startswith(blocked) for n in sys.modules)
run_research(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
"""
    isolated = subprocess.run(
        [sys.executable, "-c", code, str(CONFIG), str(DATASET), str(tmp_path / "isolated")],
        capture_output=True,
        text=True,
        env={"PATH": os.defpath},
        check=False,
    )
    assert isolated.returncode == 0, isolated.stderr


def test_partial_artifact_write_rolls_back_and_allows_retry(tmp_path: Path, monkeypatch) -> None:
    from packages.research.runner import run_research

    original = Path.write_bytes

    def interrupt(path: Path, data: bytes) -> int:
        if path.name == "metrics.json":
            raise OSError("injected disk write failure")
        return original(path, data)

    output = tmp_path / "atomic"
    monkeypatch.setattr(Path, "write_bytes", interrupt)
    with pytest.raises(OSError, match="injected"):
        run_research(CONFIG, DATASET, output)
    assert not output.exists()
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(Path, "write_bytes", original)
    run_research(CONFIG, DATASET, output)
    assert set(p.name for p in output.iterdir()) == REQUIRED


def test_existing_output_is_immutable(tmp_path: Path) -> None:
    from packages.research.runner import run_research

    output = tmp_path / "exists"
    output.mkdir()
    (output / "user.txt").write_text("preserve")
    with pytest.raises(FileExistsError):
        run_research(CONFIG, DATASET, output)
    assert (output / "user.txt").read_text() == "preserve"
    assert set(p.name for p in output.iterdir()) == {"user.txt"}


def test_artifacts_preserve_signal_rationale_and_closed_trade_pnl(tmp_path: Path) -> None:
    import csv

    from packages.research.runner import run_research

    output = tmp_path / "audit"
    run_research(CONFIG, DATASET, output)
    events = list(csv.DictReader((output / "trades.csv").open()))
    entry = next(e for e in events if e["status"] == "filled" and e["action"] == "buy")
    assert entry["decision_accepted"] == "True"
    assert "breakout_20_passed" in json.loads(entry["decision_reason_codes"])
    assert float(entry["reference_price"]) == 170
    assert float(entry["stop_price"]) == pytest.approx(164.62857142857143)
    metrics = json.loads((output / "metrics.json").read_text())
    assert metrics["accounting"]["closed_trades"][0]["pnl"] == pytest.approx(-19.5168864)

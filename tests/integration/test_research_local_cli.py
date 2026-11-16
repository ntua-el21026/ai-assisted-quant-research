"""The optional local Temporal command completes, replays and reuses results."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import temporalio


def binary_path() -> Path:
    default = Path(tempfile.gettempdir()) / (
        f"temporal-test-server-sdk-python-{temporalio.service.__version__}"
    )
    binary = Path(os.environ.get("TEMPORAL_TEST_SERVER_PATH", str(default)))
    assert binary.is_file() and os.access(binary, os.X_OK), (
        "R3 qualification requires an existing local Temporal SDK test binary; no download"
    )
    return binary


def command(state: Path, binary: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "apps.workers.app.research_local",
        "--experiment-id",
        "local-cli-reference",
        "--config",
        "experiments/configs/baseline.yaml",
        "--dataset",
        "tests/fixtures/market_snapshot/manifest.json",
        "--state",
        str(state),
        "--test-server-binary",
        str(binary),
        "--mode",
        "run",
    ]


def test_local_cli_runs_real_workflow_replays_and_retains_repeated_histories(
    tmp_path: Path,
) -> None:
    from packages.research.research_ledger import SQLiteResearchLedger

    state = tmp_path / "state"
    first_process = subprocess.run(
        command(state, binary_path()), capture_output=True, text=True, check=True, timeout=45
    )
    first = json.loads(first_process.stdout)
    assert first["replay_verified"] is True
    assert first["local_test_server_only"] is True
    result = first["result"]
    assert result["state"] == "COMMITTED"
    root = Path(result["artifact_dir"])
    assert root.is_dir()
    index = json.loads((root / "hashes.json").read_bytes())["sha256"]
    for name, digest in index.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    ledger = SQLiteResearchLedger(state / "experiments.sqlite3")
    events = ledger.events(result["experiment_id"])
    counts = ledger.counts(result["experiment_id"])
    assert counts["committed_results"] == counts["completion_events"] == 1
    second_process = subprocess.run(
        command(state, binary_path()), capture_output=True, text=True, check=True, timeout=45
    )
    second = json.loads(second_process.stdout)
    assert second["result"] == result
    assert second["replay_verified"] is True
    assert second["history_path"] != first["history_path"]
    for history in (first["history_path"], second["history_path"]):
        payload = json.loads(Path(history).read_bytes())
        assert any(
            "workflowExecutionCompletedEventAttributes" in event for event in payload["events"]
        )
    assert len(list((state / "histories").glob("*.json"))) == 2
    assert ledger.events(result["experiment_id"]) == events
    assert ledger.counts(result["experiment_id"]) == counts


def test_local_cli_missing_binary_fails_before_inputs_or_state_and_never_downloads(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    process = subprocess.run(
        command(state, tmp_path / "absent-test-server"),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert process.returncode == 2
    assert "existing executable Temporal test-server binary required" in process.stderr
    assert "No download was attempted" in process.stderr
    assert not state.exists()


def test_local_cli_requires_explicit_test_binary(tmp_path: Path) -> None:
    args = command(tmp_path / "state", tmp_path / "unused")
    index = args.index("--test-server-binary")
    del args[index : index + 2]
    process = subprocess.run(args, capture_output=True, text=True, check=False, timeout=10)
    assert process.returncode == 2
    assert "--test-server-binary" in process.stderr
    assert not (tmp_path / "state").exists()

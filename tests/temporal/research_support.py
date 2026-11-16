"""Local-only Temporal qualification and independent artifact observations."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import temporalio
from temporalio.client import WorkflowHistory
from temporalio.testing import WorkflowEnvironment


async def start_research_environment() -> WorkflowEnvironment:
    default = Path(tempfile.gettempdir()) / (
        f"temporal-test-server-sdk-python-{temporalio.service.__version__}"
    )
    binary = Path(os.environ.get("TEMPORAL_TEST_SERVER_PATH", str(default)))
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(
            "R3 local qualification requires an existing executable Temporal test server; "
            "set TEMPORAL_TEST_SERVER_PATH. No download was attempted."
        )
    return await WorkflowEnvironment.start_time_skipping(test_server_existing_path=str(binary))


def artifact_index(root: Path) -> dict[str, str]:
    index: dict[str, str] = json.loads((root / "hashes.json").read_bytes())["sha256"]
    expected = set(index) | {"hashes.json", "runtime.json"}
    assert {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == expected
    for name, digest in index.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    return index


def persisted_files(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def activity_names(history: WorkflowHistory) -> tuple[str, ...]:
    return tuple(
        event.activity_task_scheduled_event_attributes.activity_type.name
        for event in history.events
        if event.HasField("activity_task_scheduled_event_attributes")
    )


def ledger_snapshot(state_dir: Path, experiment_id: str) -> tuple[object, ...]:
    from packages.research.research_ledger import SQLiteResearchLedger

    ledger = SQLiteResearchLedger(state_dir / "experiments.sqlite3")
    return ledger.get(experiment_id), ledger.events(experiment_id), ledger.counts(experiment_id)

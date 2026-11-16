"""SQLite research checkpoints retain one immutable result through retry boundaries."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import FrozenInstanceError

import pytest

from packages.research.artifacts import canonical_json


def api():
    from packages.research import research_ledger

    return research_ledger


def register(ledger, experiment_id="experiment", **extra):
    raw = canonical_json({"mode": "evaluate", "seed": 0, **extra}).decode()
    return ledger.register(experiment_id, hashlib.sha256(raw.encode()).hexdigest(), raw)


def prepared(**updates):
    hashes = {"manifest.json": "a" * 64, "cases/example/metrics.json": "b" * 64}
    values = {
        "run_id": "c" * 64,
        "deterministic_sha256": hashlib.sha256(canonical_json(hashes)).hexdigest(),
        "artifact_hashes": hashes,
        "stage_relpath": "attempts/experiment/00000001/artifacts",
        "output_relpath": "runs/" + "c" * 64,
        "runtime_sha256": "e" * 64,
    }
    values.update(updates)
    return api().PreparedResult(**values)


def test_registration_is_immutable_and_idempotent_across_reopened_connections(tmp_path):
    module = api()
    path = tmp_path / "state.sqlite"
    ledger = module.SQLiteResearchLedger(path)
    first = register(ledger)
    assert first.state == "REGISTERED"
    assert first.attempt_count == 0 and first.prepared is None and first.failure_reason is None
    assert module.SQLiteResearchLedger(path).get("experiment") == first
    assert register(ledger) == first
    assert ledger.events("experiment") == module.SQLiteResearchLedger(path).events("experiment")
    assert len(ledger.events("experiment")) == 1
    with pytest.raises(FrozenInstanceError):
        first.state = "COMMITTED"
    with pytest.raises(module.ResearchConflict):
        register(ledger, seed=1)
    with pytest.raises(module.ResearchConflict):
        register(ledger, experiment_id="alias")
    assert ledger.get("missing") is None and ledger.find_run("d" * 64) is None
    assert len(ledger.events("experiment")) == 1


def test_complete_checkpoints_are_single_effects_under_repeated_calls(tmp_path):
    ledger = api().SQLiteResearchLedger(tmp_path / "state.sqlite")
    register(ledger)
    assert ledger.start_attempt("experiment").attempt_count == 1
    assert ledger.start_attempt("experiment").attempt_count == 2
    result = prepared()
    first = ledger.prepare("experiment", result)
    assert first.state == "PREPARED"
    assert ledger.prepare("experiment", result) == first
    published = ledger.mark_published("experiment")
    assert published.state == "PUBLISHED" and ledger.mark_published("experiment") == published
    committed = ledger.commit("experiment")
    assert committed.state == "COMMITTED" and committed.prepared == result
    assert ledger.commit("experiment") == committed
    assert ledger.prepare("experiment", result) == committed
    assert ledger.mark_published("experiment") == committed
    assert ledger.find_run(result.run_id) == committed
    assert ledger.counts("experiment") == {
        "experiments": 1,
        "committed_results": 1,
        "completion_events": 1,
        "prepared_events": 1,
        "published_events": 1,
        "attempts": 2,
    }
    assert len(ledger.events("experiment")) == 6


@pytest.mark.parametrize(
    "operation", ["start_attempt", "prepare", "mark_published", "commit", "fail"]
)
def test_unknown_experiment_cannot_create_progress(operation, tmp_path):
    ledger = api().SQLiteResearchLedger(tmp_path / "state.sqlite")
    args = (
        ("missing", prepared())
        if operation == "prepare"
        else (("missing", "invalid") if operation == "fail" else ("missing",))
    )
    with pytest.raises(api().ResearchConflict):
        getattr(ledger, operation)(*args)
    assert ledger.get("missing") is None and ledger.events("missing") == ()
    assert ledger.counts("missing") == {
        "experiments": 0,
        "committed_results": 0,
        "completion_events": 0,
        "prepared_events": 0,
        "published_events": 0,
        "attempts": 0,
    }


def test_invalid_order_and_conflicting_preparation_preserve_original_state(tmp_path):
    module = api()
    ledger = module.SQLiteResearchLedger(tmp_path / "state.sqlite")
    initial = register(ledger)
    for operation in (
        lambda: ledger.prepare("experiment", prepared()),
        lambda: ledger.mark_published("experiment"),
        lambda: ledger.commit("experiment"),
    ):
        with pytest.raises(module.ResearchConflict):
            operation()
        assert ledger.get("experiment") == initial
    ledger.start_attempt("experiment")
    first = ledger.prepare("experiment", prepared())
    with pytest.raises(module.ResearchConflict):
        ledger.prepare("experiment", prepared(stage_relpath="attempts/different/artifacts"))
    with pytest.raises(module.ResearchConflict):
        ledger.start_attempt("experiment")
    with pytest.raises(module.ResearchConflict):
        ledger.commit("experiment")
    assert ledger.get("experiment") == first


def test_unique_run_and_destination_conflicts_rollback_without_progress(tmp_path):
    module = api()
    ledger = module.SQLiteResearchLedger(tmp_path / "state.sqlite")
    register(ledger)
    register(ledger, experiment_id="other", seed=1)
    ledger.start_attempt("experiment")
    ledger.start_attempt("other")
    ledger.prepare("experiment", prepared())
    before = ledger.get("other")
    events = ledger.events("other")
    with pytest.raises(module.ResearchConflict):
        ledger.prepare("other", prepared())
    with pytest.raises(module.ResearchConflict):
        ledger.prepare("other", prepared(run_id="d" * 64))
    assert ledger.get("other") == before and ledger.events("other") == events


@pytest.mark.parametrize("state", ["REGISTERED", "RUNNING", "PREPARED", "PUBLISHED"])
def test_failure_is_terminal_and_retains_preparation_evidence(state, tmp_path):
    module = api()
    ledger = module.SQLiteResearchLedger(tmp_path / "state.sqlite")
    register(ledger)
    if state != "REGISTERED":
        ledger.start_attempt("experiment")
    if state in {"PREPARED", "PUBLISHED"}:
        ledger.prepare("experiment", prepared())
    if state == "PUBLISHED":
        ledger.mark_published("experiment")
    prior = ledger.get("experiment")
    failed = ledger.fail("experiment", "artifact_integrity_mismatch")
    assert failed.state == "FAILED" and failed.failure_reason == "artifact_integrity_mismatch"
    assert failed.prepared == prior.prepared
    assert ledger.fail("experiment", "artifact_integrity_mismatch") == failed
    with pytest.raises(module.ResearchConflict):
        ledger.start_attempt("experiment")
    with pytest.raises(module.ResearchConflict):
        ledger.commit("experiment")
    assert ledger.counts("experiment")["committed_results"] == 0


def test_committed_result_cannot_be_reclassified_as_failed(tmp_path):
    ledger = api().SQLiteResearchLedger(tmp_path / "state.sqlite")
    register(ledger)
    ledger.start_attempt("experiment")
    ledger.prepare("experiment", prepared())
    ledger.mark_published("experiment")
    committed = ledger.commit("experiment")
    with pytest.raises(api().ResearchConflict):
        ledger.fail("experiment", "later_error")
    assert ledger.get("experiment") == committed


@pytest.mark.parametrize("kind", ["wrong_hash", "noncanonical", "invalid_json"])
def test_invalid_request_never_creates_a_record(kind, tmp_path):
    ledger = api().SQLiteResearchLedger(tmp_path / "state.sqlite")
    raw = canonical_json({"seed": 0}).decode()
    if kind == "noncanonical":
        raw = json.dumps({"seed": 0})
    if kind == "invalid_json":
        raw = "invalid"
    sha = "a" * 64 if kind == "wrong_hash" else hashlib.sha256(raw.encode()).hexdigest()
    with pytest.raises(ValueError):
        ledger.register("experiment", sha, raw)
    assert ledger.get("experiment") is None


@pytest.mark.parametrize(
    "updates",
    [
        {"stage_relpath": "../escape"},
        {"output_relpath": "/absolute"},
        {"artifact_hashes": {"../escape": "a" * 64}},
        {"run_id": "invalid"},
        {"runtime_sha256": "invalid"},
        {"deterministic_sha256": "d" * 64},
    ],
)
def test_invalid_prepared_payload_is_rejected_without_a_checkpoint(updates, tmp_path):
    ledger = api().SQLiteResearchLedger(tmp_path / "state.sqlite")
    register(ledger)
    before = ledger.start_attempt("experiment")
    with pytest.raises(ValueError):
        ledger.prepare("experiment", prepared(**updates))
    assert ledger.get("experiment") == before


@pytest.mark.parametrize(
    "change",
    ["state", "attempt_count", "request_json", "event_payload", "event_deleted", "result_deleted"],
)
def test_persisted_record_event_and_result_corruption_fails_closed(change, tmp_path):
    module = api()
    path = tmp_path / "state.sqlite"
    ledger = module.SQLiteResearchLedger(path)
    register(ledger)
    ledger.start_attempt("experiment")
    ledger.prepare("experiment", prepared())
    ledger.mark_published("experiment")
    ledger.commit("experiment")
    with sqlite3.connect(path) as connection:
        if change == "state":
            connection.execute("UPDATE research_experiments SET state='RUNNING'")
        elif change == "attempt_count":
            connection.execute("UPDATE research_experiments SET attempt_count=42")
        elif change == "request_json":
            connection.execute("UPDATE research_experiments SET request_json='{}'")
        elif change == "event_payload":
            connection.execute("UPDATE research_events SET details_json='{}' WHERE sequence=2")
        elif change == "event_deleted":
            connection.execute("DELETE FROM research_events WHERE sequence=2")
        else:
            connection.execute("DELETE FROM research_results")
    before = path.read_bytes()
    with pytest.raises(module.ResearchStateCorruption):
        ledger.get("experiment")
    with pytest.raises(module.ResearchStateCorruption):
        ledger.commit("experiment")
    assert path.read_bytes() == before


def test_unknown_schema_and_corrupt_sqlite_are_not_initialized_over_evidence(tmp_path):
    module = api()
    for name, raw in (("foreign.sqlite", None), ("broken.sqlite", b"broken sqlite bytes")):
        path = tmp_path / name
        if raw is None:
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE foreign_data (value TEXT)")
        else:
            path.write_bytes(raw)
        before = path.read_bytes()
        with pytest.raises(module.ResearchStateCorruption):
            module.SQLiteResearchLedger(path)
        assert path.read_bytes() == before


@pytest.mark.parametrize("change", ["missing", "symlink"])
def test_reopened_operation_does_not_recreate_or_follow_replaced_database(change, tmp_path):
    module = api()
    path = tmp_path / "state.sqlite"
    ledger = module.SQLiteResearchLedger(path)
    register(ledger)
    evidence = tmp_path / "retained.sqlite"
    path.rename(evidence)
    retained = evidence.read_bytes()
    if change == "symlink":
        path.symlink_to(evidence)
    with pytest.raises(module.ResearchStateCorruption):
        ledger.get("experiment")
    assert evidence.read_bytes() == retained
    assert path.is_symlink() if change == "symlink" else not path.exists()


def test_commit_transaction_rolls_back_all_effects_if_completion_event_write_fails(
    tmp_path, monkeypatch
):
    module = api()
    path = tmp_path / "state.sqlite"
    ledger = module.SQLiteResearchLedger(path)
    register(ledger)
    ledger.start_attempt("experiment")
    ledger.prepare("experiment", prepared())
    published = ledger.mark_published("experiment")
    before = ledger.events("experiment")
    original = module.SQLiteResearchLedger._append

    def fail_completion(connection, experiment_id, kind, details):
        if kind == "committed":
            raise OSError("injected completion-event persistence failure")
        return original(connection, experiment_id, kind, details)

    monkeypatch.setattr(module.SQLiteResearchLedger, "_append", staticmethod(fail_completion))
    with pytest.raises(OSError, match="injected"):
        ledger.commit("experiment")
    reopened = module.SQLiteResearchLedger(path)
    assert reopened.get("experiment") == published
    assert reopened.events("experiment") == before
    assert reopened.counts("experiment")["committed_results"] == 0
    monkeypatch.setattr(module.SQLiteResearchLedger, "_append", staticmethod(original))
    reopened.commit("experiment")
    assert reopened.counts("experiment")["committed_results"] == 1

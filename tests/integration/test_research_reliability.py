"""Actual offline runner recovery across the SQLite/filesystem commit boundary."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from packages.research.runner import run_research


def request_for(tmp_path, *, mode="run", name="reference-experiment"):
    from packages.research.reliability import prepare_workflow_request

    return prepare_workflow_request(
        name,
        Path(
            "experiments/configs/baseline.yaml"
            if mode == "run"
            else "experiments/configs/ablations.yaml"
        ),
        Path("tests/fixtures/market_snapshot/manifest.json"),
        tmp_path / "state",
        mode=mode,
    )


def inventory(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize(
    "phase",
    [
        "before_register",
        "after_register",
        "before_execution",
        "after_execution",
        "before_prepare",
        "after_prepare",
        "before_publish",
        "after_publish_rename",
        "before_published",
        "after_published",
        "before_commit",
        "after_commit",
    ],
)
def test_interrupted_transitions_reconcile_to_independent_uninterrupted_reference(tmp_path, phase):
    from packages.research.reliability import execute_research_experiment, verify_research_run_state
    from packages.research.research_ledger import SQLiteResearchLedger

    reference = run_research(
        Path("experiments/configs/baseline.yaml"),
        Path("tests/fixtures/market_snapshot/manifest.json"),
        tmp_path / "reference",
    )
    request = request_for(tmp_path)

    def interrupt(current):
        if current == phase:
            raise RuntimeError("injected_transient_failure")

    with pytest.raises(RuntimeError, match="injected_transient_failure"):
        execute_research_experiment(request, fault=interrupt)
    result = execute_research_experiment(request)
    assert result.run_id == reference.run_id
    assert result.deterministic_sha256 == reference.deterministic_sha256
    final = Path(result.artifact_dir)
    assert json.loads((final / "hashes.json").read_bytes()) == json.loads(
        (reference.output_dir / "hashes.json").read_bytes()
    )
    ledger = SQLiteResearchLedger(Path(request.state_dir) / "experiments.sqlite3")
    assert ledger.get(request.experiment_id).state == "COMMITTED"
    counts = ledger.counts(request.experiment_id)
    assert {
        k: counts[k]
        for k in (
            "experiments",
            "committed_results",
            "completion_events",
            "prepared_events",
            "published_events",
        )
    } == dict.fromkeys(
        (
            "experiments",
            "committed_results",
            "completion_events",
            "prepared_events",
            "published_events",
        ),
        1,
    )
    assert len(list((Path(request.state_dir) / "runs").iterdir())) == 1
    check = verify_research_run_state(result.run_id, final, ledger)
    assert check.state == "COMMITTED" and check.deterministic_sha256 == result.deterministic_sha256
    before, events = inventory(final), ledger.events(request.experiment_id)
    assert execute_research_experiment(request) == result
    assert inventory(final) == before
    assert ledger.events(request.experiment_id) == events


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra", "symlink", "bad_index"])
def test_committed_corruption_fails_closed_and_retains_evidence(tmp_path, mutation):
    from packages.research.reliability import execute_research_experiment
    from packages.research.research_ledger import ResearchStateCorruption

    request = request_for(tmp_path)
    result = execute_research_experiment(request)
    root = Path(result.artifact_dir)
    target = root / "equity.csv"
    if mutation == "changed":
        target.write_bytes(target.read_bytes() + b"changed")
    elif mutation == "missing":
        target.unlink()
    elif mutation == "extra":
        (root / "unindexed.txt").write_text("unexpected evidence")
    elif mutation == "symlink":
        target.rename(root.parent / "outside.csv")
        target.symlink_to(root.parent / "outside.csv")
    else:
        (root / "hashes.json").write_text('{"sha256":{"../escape":"' + "0" * 64 + '"}}')
    before = inventory(root)
    with pytest.raises(ResearchStateCorruption):
        execute_research_experiment(request)
    assert inventory(root) == before
    with pytest.raises(ResearchStateCorruption):
        execute_research_experiment(request)


def test_same_identity_conflicts_and_source_input_contract_is_pinned(tmp_path):
    from packages.research.reliability import execute_research_experiment
    from packages.research.research_ledger import ResearchConflict

    original = request_for(tmp_path)
    completed = execute_research_experiment(original)
    conflicting = request_for(tmp_path, mode="evaluate")
    with pytest.raises(ResearchConflict):
        execute_research_experiment(conflicting)
    with pytest.raises(ResearchConflict):
        execute_research_experiment(replace(original, input_fingerprint="0" * 64))
    assert execute_research_experiment(original) == completed


def test_process_death_after_rename_releases_ownership_and_recovers(tmp_path):
    from dataclasses import asdict

    from packages.research.reliability import execute_research_experiment

    request = request_for(tmp_path)
    payload = tmp_path / "request.json"
    payload.write_text(json.dumps(asdict(request)))
    script = """
import json,os,sys
from pathlib import Path
from packages.research.reliability import execute_research_experiment
from packages.research.reliability_models import ResearchWorkflowRequest
request=ResearchWorkflowRequest(**json.loads(Path(sys.argv[1]).read_bytes()))
def kill(phase):
    if phase=='after_publish_rename':
        os._exit(73)
execute_research_experiment(request,fault=kill)
"""
    child = subprocess.run([sys.executable, "-c", script, str(payload)], timeout=30, check=False)
    assert child.returncode == 73
    first = execute_research_experiment(request)
    assert execute_research_experiment(request) == first


def test_importing_research_activity_never_loads_legacy_provider_or_broker_registries():
    script = """
import importlib.abc,sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname in {'apps.workers.app.activities.ai','apps.workers.app.activities.broker',
                         'apps.workers.app.activities.ledger','apps.workers.app.activities.reporting'}:
            raise AssertionError('forbidden legacy activity import: '+fullname)
sys.meta_path.insert(0,Guard())
from apps.workers.app.activities.research import ResearchActivities
assert ResearchActivities
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)


def test_deleted_ledger_is_never_silently_reinitialized(tmp_path):
    from packages.research.reliability import execute_research_experiment
    from packages.research.research_ledger import ResearchStateCorruption

    request = request_for(tmp_path)
    result = execute_research_experiment(request)
    database = Path(request.state_dir) / "experiments.sqlite3"
    database.rename(database.with_suffix(".retained"))
    before = inventory(Path(request.state_dir))
    with pytest.raises(ResearchStateCorruption, match="missing"):
        execute_research_experiment(request)
    assert inventory(Path(request.state_dir)) == before
    assert Path(result.artifact_dir).exists()


def test_valid_empty_replacement_ledger_cannot_erase_owned_attempt_history(tmp_path):
    from packages.research.reliability import execute_research_experiment
    from packages.research.research_ledger import ResearchStateCorruption, SQLiteResearchLedger

    request = request_for(tmp_path)
    result = execute_research_experiment(request)
    database = Path(request.state_dir) / "experiments.sqlite3"
    database.rename(database.with_suffix(".retained"))
    SQLiteResearchLedger(database)
    before = inventory(Path(request.state_dir))
    with pytest.raises(ResearchStateCorruption):
        execute_research_experiment(request)
    assert inventory(Path(request.state_dir)) == before
    assert Path(result.artifact_dir).exists()


@pytest.mark.parametrize("mutation", ["changed_stage", "missing_stage", "contradictory_final"])
def test_prepared_inconsistency_preserves_evidence_without_recomputation(tmp_path, mutation):
    import shutil

    from packages.research.reliability import execute_research_experiment
    from packages.research.research_ledger import ResearchStateCorruption, SQLiteResearchLedger

    request = request_for(tmp_path)

    def stop(phase):
        if phase == "after_prepare":
            raise RuntimeError("prepared_interruption")

    with pytest.raises(RuntimeError, match="prepared_interruption"):
        execute_research_experiment(request, fault=stop)
    root = Path(request.state_dir)
    ledger = SQLiteResearchLedger(root / "experiments.sqlite3")
    prepared = ledger.get(request.experiment_id).prepared
    stage = root / prepared.stage_relpath
    if mutation == "changed_stage":
        (stage / "equity.csv").write_bytes(b"corrupt")
    elif mutation == "missing_stage":
        stage.rename(stage.with_name("retained-evidence"))
    else:
        final = root / prepared.output_relpath
        final.parent.mkdir()
        shutil.copytree(stage, final)
    before = inventory(root / "attempts")
    with pytest.raises(ResearchStateCorruption):
        execute_research_experiment(request)
    assert inventory(root / "attempts") == before
    assert ledger.get(request.experiment_id).state == "FAILED"
    assert ledger.counts(request.experiment_id)["attempts"] == 1
    assert ledger.counts(request.experiment_id)["committed_results"] == 0


def test_transient_failure_inside_actual_artifact_writer_retries_privately(tmp_path, monkeypatch):
    from packages.research.reliability import execute_research_experiment
    from packages.research.research_ledger import SQLiteResearchLedger

    request = request_for(tmp_path)
    write = Path.write_bytes

    def fail_equity(path, data):
        if path.name == "equity.csv":
            raise OSError("injected_partial_write")
        return write(path, data)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_bytes", fail_equity)
        with pytest.raises(OSError, match="injected_partial_write"):
            execute_research_experiment(request)
    result = execute_research_experiment(request)
    ledger = SQLiteResearchLedger(Path(request.state_dir) / "experiments.sqlite3")
    assert ledger.counts(request.experiment_id)["attempts"] == 2
    assert ledger.counts(request.experiment_id)["committed_results"] == 1
    assert Path(result.artifact_dir).exists()


def test_overlapping_same_experiment_attempt_cannot_duplicate_effects(tmp_path):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from packages.research.reliability import execute_research_experiment
    from packages.research.research_ledger import SQLiteResearchLedger

    request = request_for(tmp_path)
    entered, release = threading.Event(), threading.Event()

    def pause(phase):
        if phase == "before_execution":
            entered.set()
            assert release.wait(10)

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(execute_research_experiment, request, fault=pause)
        try:
            assert entered.wait(10)
            with pytest.raises(RuntimeError, match="experiment_execution_busy"):
                execute_research_experiment(request)
        finally:
            release.set()
        result = first.result(timeout=15)
    assert execute_research_experiment(request) == result
    counts = SQLiteResearchLedger(Path(request.state_dir) / "experiments.sqlite3").counts(
        request.experiment_id
    )
    assert counts["attempts"] == counts["committed_results"] == counts["completion_events"] == 1

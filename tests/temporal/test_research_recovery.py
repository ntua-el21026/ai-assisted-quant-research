"""Retries and an actual worker replacement while a durable activity retry is pending."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from research_support import (
    activity_names,
    artifact_index,
    ledger_snapshot,
    persisted_files,
    start_research_environment,
)
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.worker import Replayer, Worker


def test_activity_transient_failure_before_execution_retries_actual_pipeline(
    tmp_path: Path,
) -> None:
    asyncio.run(_retry_before_execution(tmp_path))


async def _retry_before_execution(tmp_path: Path) -> None:
    from apps.workers.app.activities.research import ResearchActivities
    from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
    from packages.research.reliability import prepare_workflow_request
    from packages.research.runner import run_research

    config = Path("experiments/configs/baseline.yaml")
    dataset = Path("tests/fixtures/market_snapshot/manifest.json")
    reference = run_research(config, dataset, tmp_path / "reference")
    request = prepare_workflow_request("retry", config, dataset, tmp_path / "state", mode="run")
    attempts = 0

    def transient(phase: str) -> None:
        nonlocal attempts
        if phase == "before_execution":
            attempts += 1
            if attempts == 1:
                raise RuntimeError("controlled_transient_before_execution")

    activities = ResearchActivities(fault=transient)
    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await start_research_environment() as env:
            async with Worker(
                env.client,
                task_queue="local-research-retry",
                workflows=[ResearchExperimentWorkflow],
                activities=[activities.run],
                activity_executor=executor,
            ):
                result = await asyncio.wait_for(
                    env.client.execute_workflow(
                        ResearchExperimentWorkflow.run,
                        request,
                        id="retry-before-execution",
                        task_queue="local-research-retry",
                    ),
                    timeout=30,
                )
                assert attempts == 2
                assert result.run_id == reference.run_id
                assert result.deterministic_sha256 == reference.deterministic_sha256
                assert artifact_index(Path(result.artifact_dir)) == artifact_index(
                    reference.output_dir
                )


def test_worker_replacement_resumes_pending_retry_and_replays_without_effects(
    tmp_path: Path,
) -> None:
    asyncio.run(_worker_replacement(tmp_path))


async def _worker_replacement(tmp_path: Path) -> None:
    from apps.workers.app.activities.research import ResearchActivities
    from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
    from packages.research.reliability import prepare_workflow_request
    from packages.research.runner import run_research

    config = Path("experiments/configs/baseline.yaml")
    dataset = Path("tests/fixtures/market_snapshot/manifest.json")
    reference = run_research(config, dataset, tmp_path / "reference")
    request = prepare_workflow_request("restart", config, dataset, tmp_path / "state", mode="run")
    phase_ready = threading.Event()
    shutdown_observed = threading.Event()
    attempts_a = 0
    attempts_b = 0

    def worker_a_failure(phase: str) -> None:
        nonlocal attempts_a
        if phase == "before_execution":
            attempts_a += 1
            phase_ready.set()
            # Shutdown must stop A's polling before its transient failure is
            # reported, so A cannot reserve the retry during context teardown.
            activity.wait_for_worker_shutdown_sync(timeout=10)
            assert activity.is_worker_shutdown()
            shutdown_observed.set()
            raise RuntimeError("controlled_worker_a_transient")

    def worker_b_observation(phase: str) -> None:
        nonlocal attempts_b
        if phase == "before_execution":
            attempts_b += 1

    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await start_research_environment() as env:
            worker_a = Worker(
                env.client,
                task_queue="local-research-restart",
                identity="research-worker-a",
                max_cached_workflows=0,
                workflows=[ResearchExperimentWorkflow],
                activities=[ResearchActivities(fault=worker_a_failure).run],
                activity_executor=executor,
            )
            async with worker_a:
                handle = await env.client.start_workflow(
                    ResearchExperimentWorkflow.run,
                    request,
                    id="worker-restart-experiment",
                    task_queue="local-research-restart",
                )
                assert await asyncio.to_thread(phase_ready.wait, 10)
            # This verifies SDK worker replacement with an outstanding retry, not
            # a process kill, server restart, power loss or in-flight hard crash.
            assert not worker_a.is_running
            assert shutdown_observed.is_set()
            async with Worker(
                env.client,
                task_queue="local-research-restart",
                identity="research-worker-b",
                max_cached_workflows=0,
                workflows=[ResearchExperimentWorkflow],
                activities=[ResearchActivities(fault=worker_b_observation).run],
                activity_executor=executor,
            ):
                result = await asyncio.wait_for(handle.result(), timeout=30)
                assert result.run_id == reference.run_id
                assert result.deterministic_sha256 == reference.deterministic_sha256
                assert artifact_index(Path(result.artifact_dir)) == artifact_index(
                    reference.output_dir
                )
                history = await handle.fetch_history()
                assert activity_names(history) == ("run_research_experiment",)
                starts = [
                    e.activity_task_started_event_attributes
                    for e in history.events
                    if e.HasField("activity_task_started_event_attributes")
                ]
                assert any(s.identity == "research-worker-b" and s.attempt >= 2 for s in starts)
                assert attempts_a == attempts_b == 1
                before_replay = persisted_files(tmp_path / "state")
            replay = await Replayer(workflows=[ResearchExperimentWorkflow]).replay_workflow(history)
            assert replay.replay_failure is None
            assert persisted_files(tmp_path / "state") == before_replay


def test_retry_after_commit_does_not_repeat_publication_or_ledger_completion(
    tmp_path: Path,
) -> None:
    asyncio.run(_retry_after_commit(tmp_path))


async def _retry_after_commit(tmp_path: Path) -> None:
    from apps.workers.app.activities.research import ResearchActivities
    from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
    from packages.research.reliability import prepare_workflow_request
    from packages.research.research_ledger import SQLiteResearchLedger

    state = tmp_path / "state"
    request = prepare_workflow_request(
        "lost-completion",
        Path("experiments/configs/baseline.yaml"),
        Path("tests/fixtures/market_snapshot/manifest.json"),
        state,
        mode="run",
    )
    after_commit_calls = 0
    committed_snapshot: tuple[object, ...] | None = None
    committed_artifacts: dict[str, str] | None = None

    def lost_completion(phase: str) -> None:
        nonlocal after_commit_calls, committed_snapshot, committed_artifacts
        if phase == "after_commit":
            after_commit_calls += 1
            ledger = SQLiteResearchLedger(state / "experiments.sqlite3")
            record = ledger.get(request.experiment_id)
            assert record is not None and record.prepared is not None
            committed_snapshot = ledger_snapshot(state, request.experiment_id)
            committed_artifacts = persisted_files(state / record.prepared.output_relpath)
            raise RuntimeError("controlled_lost_completion_after_commit")

    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await start_research_environment() as env:
            async with Worker(
                env.client,
                task_queue="local-research-lost-completion",
                workflows=[ResearchExperimentWorkflow],
                activities=[ResearchActivities(fault=lost_completion).run],
                activity_executor=executor,
            ):
                result = await asyncio.wait_for(
                    env.client.execute_workflow(
                        ResearchExperimentWorkflow.run,
                        request,
                        id="lost-completion-workflow",
                        task_queue="local-research-lost-completion",
                    ),
                    timeout=30,
                )
                assert after_commit_calls == 1
                assert committed_snapshot is not None
                assert ledger_snapshot(state, request.experiment_id) == committed_snapshot
                assert persisted_files(Path(result.artifact_dir)) == committed_artifacts
                counts = SQLiteResearchLedger(state / "experiments.sqlite3").counts(
                    request.experiment_id
                )
                assert counts["completion_events"] == counts["committed_results"] == 1
                assert counts["attempts"] == 1


def test_exhausted_transient_retries_do_not_fabricate_success(tmp_path: Path) -> None:
    asyncio.run(_exhausted_retry(tmp_path))


async def _exhausted_retry(tmp_path: Path) -> None:
    from apps.workers.app.activities.research import ResearchActivities
    from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
    from packages.research.reliability import prepare_workflow_request
    from packages.research.research_ledger import SQLiteResearchLedger

    state = tmp_path / "state"
    request = prepare_workflow_request(
        "exhausted",
        Path("experiments/configs/baseline.yaml"),
        Path("tests/fixtures/market_snapshot/manifest.json"),
        state,
        mode="run",
    )
    attempts = 0

    def always_unavailable(phase: str) -> None:
        nonlocal attempts
        if phase == "before_execution":
            attempts += 1
            raise RuntimeError("controlled_persistent_transient_error")

    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await start_research_environment() as env:
            async with Worker(
                env.client,
                task_queue="local-research-exhausted",
                workflows=[ResearchExperimentWorkflow],
                activities=[ResearchActivities(fault=always_unavailable).run],
                activity_executor=executor,
            ):
                with pytest.raises(WorkflowFailureError):
                    await asyncio.wait_for(
                        env.client.execute_workflow(
                            ResearchExperimentWorkflow.run,
                            request,
                            id="exhausted-workflow",
                            task_queue="local-research-exhausted",
                        ),
                        timeout=30,
                    )
                assert attempts == 3
                counts = SQLiteResearchLedger(state / "experiments.sqlite3").counts(
                    request.experiment_id
                )
                assert counts["committed_results"] == counts["completion_events"] == 0
                assert not (state / "runs").exists() or not list((state / "runs").iterdir())

"""Actual local SDK execution and replay of the deterministic offline pipeline."""

from __future__ import annotations

import asyncio
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
from temporalio.client import WorkflowFailureError
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError
from temporalio.worker import Replayer, Worker


@pytest.mark.parametrize("mode", ["run", "evaluate"])
def test_research_workflow_executes_actual_pipeline_and_replays_without_effects(
    tmp_path: Path, mode: str
) -> None:
    # Removing the workflow/real activity or returning fabricated hashes breaks
    # independent reference parity; replay must not perform another side effect.
    asyncio.run(_execute_and_replay(tmp_path, mode))


async def _execute_and_replay(tmp_path: Path, mode: str) -> None:
    from apps.workers.app.activities.research import ResearchActivities
    from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
    from packages.research.reliability import prepare_workflow_request
    from packages.research.reliability_models import ResearchWorkflowResult
    from packages.research.runner import evaluate_research, run_research

    config = Path(f"experiments/configs/{'baseline' if mode == 'run' else 'ablations'}.yaml")
    dataset = Path("tests/fixtures/market_snapshot/manifest.json")
    reference = (run_research if mode == "run" else evaluate_research)(
        config, dataset, tmp_path / "reference"
    )
    request = prepare_workflow_request(
        f"reference-{mode}", config, dataset, tmp_path / "state", mode=mode
    )
    activities = ResearchActivities()
    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await start_research_environment() as env:
            async with Worker(
                env.client,
                task_queue="local-research-reference",
                workflows=[ResearchExperimentWorkflow],
                activities=[activities.run],
                activity_executor=executor,
            ):
                handle = await env.client.start_workflow(
                    ResearchExperimentWorkflow.run,
                    request,
                    id=f"local-reference-{mode}",
                    task_queue="local-research-reference",
                )
                result = await asyncio.wait_for(handle.result(), timeout=30)
                assert isinstance(result, ResearchWorkflowResult)
                assert result.state == "COMMITTED"
                assert result.experiment_id == request.experiment_id
                assert result.run_id == reference.run_id
                assert result.deterministic_sha256 == reference.deterministic_sha256
                assert artifact_index(Path(result.artifact_dir)) == artifact_index(
                    reference.output_dir
                )
                history = await handle.fetch_history()
                assert activity_names(history) == ("run_research_experiment",)
                before_replay = persisted_files(tmp_path / "state")
            replay = await Replayer(workflows=[ResearchExperimentWorkflow]).replay_workflow(history)
            assert replay.replay_failure is None
            assert persisted_files(tmp_path / "state") == before_replay


def test_duplicate_workflow_and_distinct_workflow_ids_do_not_repeat_committed_effects(
    tmp_path: Path,
) -> None:
    asyncio.run(_duplicate_workflow(tmp_path))


async def _duplicate_workflow(tmp_path: Path) -> None:
    from apps.workers.app.activities.research import ResearchActivities
    from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
    from packages.research.reliability import prepare_workflow_request

    request = prepare_workflow_request(
        "duplicate-experiment",
        Path("experiments/configs/baseline.yaml"),
        Path("tests/fixtures/market_snapshot/manifest.json"),
        tmp_path / "state",
        mode="run",
    )
    activities = ResearchActivities()
    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await start_research_environment() as env:
            async with Worker(
                env.client,
                task_queue="local-research-duplicate",
                workflows=[ResearchExperimentWorkflow],
                activities=[activities.run],
                activity_executor=executor,
            ):
                first = await env.client.execute_workflow(
                    ResearchExperimentWorkflow.run,
                    request,
                    id="duplicate-workflow",
                    task_queue="local-research-duplicate",
                )
                baseline = ledger_snapshot(tmp_path / "state", request.experiment_id)
                artifact_bytes = persisted_files(Path(first.artifact_dir))
                with pytest.raises(WorkflowAlreadyStartedError):
                    await env.client.start_workflow(
                        ResearchExperimentWorkflow.run,
                        request,
                        id="duplicate-workflow",
                        task_queue="local-research-duplicate",
                        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                    )
                assert ledger_snapshot(tmp_path / "state", request.experiment_id) == baseline
                assert persisted_files(Path(first.artifact_dir)) == artifact_bytes
                second = await env.client.execute_workflow(
                    ResearchExperimentWorkflow.run,
                    request,
                    id="second-workflow-same-experiment",
                    task_queue="local-research-duplicate",
                )
                assert second == first
                assert ledger_snapshot(tmp_path / "state", request.experiment_id) == baseline
                assert persisted_files(Path(first.artifact_dir)) == artifact_bytes


def test_conflicting_experiment_identity_is_nonretryable_and_preserves_evidence(
    tmp_path: Path,
) -> None:
    asyncio.run(_conflicting_workflow(tmp_path))


async def _conflicting_workflow(tmp_path: Path) -> None:
    from apps.workers.app.activities.research import ResearchActivities
    from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
    from packages.research.reliability import prepare_workflow_request

    state = tmp_path / "state"
    dataset = Path("tests/fixtures/market_snapshot/manifest.json")
    first_request = prepare_workflow_request(
        "conflict", Path("experiments/configs/baseline.yaml"), dataset, state, mode="run"
    )
    conflicting = prepare_workflow_request(
        "conflict", Path("experiments/configs/ablations.yaml"), dataset, state
    )
    activities = ResearchActivities()
    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await start_research_environment() as env:
            async with Worker(
                env.client,
                task_queue="local-research-conflict",
                workflows=[ResearchExperimentWorkflow],
                activities=[activities.run],
                activity_executor=executor,
            ):
                first = await env.client.execute_workflow(
                    ResearchExperimentWorkflow.run,
                    first_request,
                    id="conflict-original",
                    task_queue="local-research-conflict",
                )
                before = ledger_snapshot(state, first_request.experiment_id)
                artifact_bytes = persisted_files(Path(first.artifact_dir))
                with pytest.raises(WorkflowFailureError) as failed:
                    await env.client.execute_workflow(
                        ResearchExperimentWorkflow.run,
                        conflicting,
                        id="conflict-request",
                        task_queue="local-research-conflict",
                    )
                cause = failed.value.cause.cause
                assert isinstance(cause, ApplicationError)
                assert cause.non_retryable and cause.type == "ResearchConflict"
                assert ledger_snapshot(state, first_request.experiment_id) == before
                assert persisted_files(Path(first.artifact_dir)) == artifact_bytes
                assert artifact_index(Path(first.artifact_dir))


def test_corrupt_committed_result_fails_workflow_without_repair_or_duplicate_effects(
    tmp_path: Path,
) -> None:
    asyncio.run(_corrupt_committed_result(tmp_path))


async def _corrupt_committed_result(tmp_path: Path) -> None:
    from apps.workers.app.activities.research import ResearchActivities
    from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
    from packages.research.reliability import prepare_workflow_request

    state = tmp_path / "state"
    request = prepare_workflow_request(
        "corruption",
        Path("experiments/configs/baseline.yaml"),
        Path("tests/fixtures/market_snapshot/manifest.json"),
        state,
        mode="run",
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await start_research_environment() as env:
            async with Worker(
                env.client,
                task_queue="local-research-corruption",
                workflows=[ResearchExperimentWorkflow],
                activities=[ResearchActivities().run],
                activity_executor=executor,
            ):
                first = await env.client.execute_workflow(
                    ResearchExperimentWorkflow.run,
                    request,
                    id="before-corruption",
                    task_queue="local-research-corruption",
                )
                target = Path(first.artifact_dir) / "equity.csv"
                target.write_bytes(target.read_bytes() + b"controlled corruption\n")
                corrupted = persisted_files(Path(first.artifact_dir))
                before = ledger_snapshot(state, request.experiment_id)
                with pytest.raises(WorkflowFailureError) as failed:
                    await env.client.execute_workflow(
                        ResearchExperimentWorkflow.run,
                        request,
                        id="after-corruption",
                        task_queue="local-research-corruption",
                    )
                cause = failed.value.cause.cause
                assert isinstance(cause, ApplicationError)
                assert cause.non_retryable and cause.type == "ResearchStateCorruption"
                assert ledger_snapshot(state, request.experiment_id) == before
                assert persisted_files(Path(first.artifact_dir)) == corrupted

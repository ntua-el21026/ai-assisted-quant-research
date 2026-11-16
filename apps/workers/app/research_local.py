"""One finite local SDK workflow and replay; no server download or cloud connection."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, cast

from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from apps.workers.app.activities.research import ResearchActivities
from apps.workers.app.workflows.research_experiment import ResearchExperimentWorkflow
from packages.research.artifacts import _sync_directory
from packages.research.reliability import prepare_workflow_request


async def _run(args: argparse.Namespace, binary: Path) -> dict[str, Any]:
    request = prepare_workflow_request(
        args.experiment_id,
        args.config,
        args.dataset,
        args.state,
        mode=cast(Literal["run", "evaluate"], args.mode),
        include_final=args.include_final,
    )
    invocation = uuid.uuid4().hex
    task_queue = f"local-research-{invocation}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        async with await WorkflowEnvironment.start_time_skipping(
            test_server_existing_path=str(binary)
        ) as env:
            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[ResearchExperimentWorkflow],
                activities=[ResearchActivities().run],
                activity_executor=executor,
                max_cached_workflows=0,
            ):
                handle = await env.client.start_workflow(
                    ResearchExperimentWorkflow.run,
                    request,
                    id=f"research-{invocation}",
                    task_queue=task_queue,
                )
                result = await asyncio.wait_for(handle.result(), timeout=17 * 60)
                history = await handle.fetch_history()
    histories = Path(request.state_dir) / "histories"
    if histories.is_symlink():
        raise ValueError("history_directory_must_not_be_a_symlink")
    histories.mkdir(exist_ok=True)
    history_path = histories / f"{invocation}.json"
    # Retain actual history even if subsequent replay fails; never overwrite an attempt.
    with history_path.open("x", encoding="utf-8") as stream:
        stream.write(history.to_json())
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(histories)
    replay = await Replayer(workflows=[ResearchExperimentWorkflow]).replay_workflow(history)
    if replay.replay_failure is not None:
        raise RuntimeError("local_research_history_replay_failed")
    return {
        "result": asdict(result),
        "history_path": str(history_path),
        "replay_verified": True,
        "local_test_server_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--test-server-binary", required=True, type=Path)
    parser.add_argument("--mode", choices=("run", "evaluate"), default="evaluate")
    parser.add_argument("--include-final", action="store_true")
    args = parser.parse_args(argv)
    binary = args.test_server_binary.absolute()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(
            "existing executable Temporal test-server binary required. No download was attempted."
        )
    try:
        result = asyncio.run(_run(args, binary))
    except (OSError, ValueError, RuntimeError, WorkflowFailureError) as exc:
        print(f"research-local: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Optional deterministic orchestration for one local offline research experiment."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from packages.research.reliability_models import ResearchWorkflowRequest, ResearchWorkflowResult


@workflow.defn
class ResearchExperimentWorkflow:
    """Delegate I/O and recovery to one idempotent, typed local activity."""

    @workflow.run
    async def run(self, request: ResearchWorkflowRequest) -> ResearchWorkflowResult:
        result: ResearchWorkflowResult = await workflow.execute_activity(
            "run_research_experiment",
            request,
            result_type=ResearchWorkflowResult,
            start_to_close_timeout=timedelta(minutes=5),
            schedule_to_close_timeout=timedelta(minutes=16),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=2),
                maximum_attempts=3,
            ),
        )
        return result

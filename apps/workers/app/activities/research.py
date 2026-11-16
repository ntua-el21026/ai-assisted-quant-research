"""Real offline research activity, deliberately outside the legacy activity registry."""

from __future__ import annotations

from collections.abc import Callable

from temporalio import activity
from temporalio.exceptions import ApplicationError

from packages.research.reliability_models import ResearchWorkflowRequest, ResearchWorkflowResult


class ResearchActivities:
    """Run the actual pipeline with local durable reconciliation and bounded fault hooks.

    Synchronous execution belongs in a worker's dedicated thread executor. SDK
    shutdown drains the activity instead of injecting cancellation into SQLite or
    filesystem critical sections. A lost process is recovered by the durable core.
    """

    def __init__(self, *, fault: Callable[[str], None] | None = None) -> None:
        self._fault = fault

    @activity.defn(name="run_research_experiment", no_thread_cancel_exception=True)
    def run(self, request: ResearchWorkflowRequest) -> ResearchWorkflowResult:
        # Import the I/O core only in the activity; workflow sandbox/replay never
        # imports the runner, SQLite, providers or filesystem reconciliation.
        from packages.research.reliability import execute_research_experiment
        from packages.research.research_ledger import ResearchConflict, ResearchStateCorruption

        try:
            return execute_research_experiment(request, fault=self._fault)
        except (ResearchConflict, ResearchStateCorruption) as exc:
            raise ApplicationError(str(exc), type=type(exc).__name__, non_retryable=True) from exc
        except ValueError as exc:
            raise ApplicationError(
                str(exc), type="ResearchValidationError", non_retryable=True
            ) from exc

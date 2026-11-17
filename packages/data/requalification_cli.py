"""Finite R4-B.1 acquisition and offline qualification; no strategy execution."""

from __future__ import annotations

import argparse
import hashlib
import signal
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from packages.data.acquisition_cli import _Deadline, _deadline
from packages.data.acquisition_plan import load_alpaca_credentials
from packages.data.acquisition_session import acquire_registered_candidate
from packages.data.alpaca_historical import UrllibHistoricalTransport
from packages.data.checkpoint_budget import BudgetReceiptReference, CheckpointBudgetAuthority
from packages.data.historical_candidates import load_historical_candidate
from packages.data.private_storage import PrivateStorage
from packages.data.requalification import (
    RequalificationInputs,
    build_requalification_report,
    load_requalification_inputs,
    make_action_evaluator,
    make_pilot_gate,
)
from packages.research.artifacts import canonical_json, content_hashes


def qualify_requalified(
    manifest: Path,
    inputs: RequalificationInputs,
    *,
    repository: Path,
    output: Path,
    storage_guard: Callable[[int], None] | None = None,
) -> dict[str, object]:
    """Publish a new private report; never change or promote a frozen candidate."""
    storage = PrivateStorage(output, repository, storage_guard=storage_guard)
    candidate = load_historical_candidate(manifest)
    if candidate.manifest.kind == "historical" and storage_guard is None:
        raise ValueError("checkpoint_authority_required")
    report = build_requalification_report(candidate, inputs)
    sources = {
        str(p.relative_to(repository)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((repository / "packages/data").glob("*.py"))
    }
    files = {
        "requalification.json": canonical_json(report),
        "qualifier-source.json": canonical_json(sources),
        "input-binding.json": canonical_json(
            {
                "candidate_manifest_sha256": candidate.manifest_sha256,
                "policy_sha256": inputs.sha256,
            }
        ),
    }
    storage.publish(
        "report", files, canonical_json({"qualified_at": datetime.now(UTC).isoformat()})
    )
    return {
        "hashes": content_hashes(files),
        "candidate_manifest_sha256": candidate.manifest_sha256,
        "dataset_to_r4c": report["dataset_to_r4c"],
        "technical_pilot": report["technical_pilot"],
    }


def _authority(inputs: RequalificationInputs, repository: Path) -> CheckpointBudgetAuthority:
    policy = inputs.policy
    manifest = repository / policy.original_manifest_path
    quality = repository / policy.original_qualification_path
    return CheckpointBudgetAuthority(
        repository / "datasets/private/r4b/aggregate-budget-r4b1-v1",
        repository,
        repository / policy.seed_events_path,
        policy.seed_events_sha256,
        prior_receipts=(
            BudgetReceiptReference(
                manifest, policy.original_manifest_sha256, manifest.stat().st_size
            ),
            BudgetReceiptReference(
                quality, policy.original_qualification_sha256, quality.stat().st_size
            ),
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "acquire", "qualify"):
        command = commands.add_parser(name)
        command.add_argument("--policy", type=Path, required=True)
        if name == "acquire":
            command.add_argument("--allow-network", action="store_true")
            command.add_argument("--credentials-file", type=Path, required=True)
            command.add_argument("--workspace", type=Path, required=True)
        elif name == "qualify":
            command.add_argument("--candidate", type=Path, required=True)
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "acquire" and not args.allow_network:
        print('{"error":"explicit_network_authorization_required"}')
        return 2
    try:
        repository = Path(__file__).resolve().parents[2]
        inputs = load_requalification_inputs(args.policy, repository)
        if args.command == "plan":
            print(
                canonical_json(
                    {
                        "policy_sha256": inputs.sha256,
                        "plan_sha256": inputs.registered.sha256,
                        "feed": "iex",
                        "reused_preflight_requests": 2,
                        "network": False,
                    }
                ).decode(),
                end="",
            )
            return 0
        with _authority(inputs, repository) as authority:
            if args.command == "qualify":
                result = qualify_requalified(
                    args.candidate,
                    inputs,
                    repository=repository,
                    output=args.output,
                    storage_guard=authority.check_storage,
                )
            else:
                before = authority.snapshot()
                credentials = load_alpaca_credentials(args.credentials_file)
                print('{"credentials_available":true}', flush=True)
                transport = UrllibHistoricalTransport(credentials.api_key, credentials.secret_key)
                cached = {
                    record.acquisition_id: acquisition
                    for record, acquisition in zip(
                        inputs.original.manifest.acquisitions,
                        inputs.original.acquisitions,
                        strict=True,
                    )
                }
                previous = signal.signal(signal.SIGALRM, _deadline)
                signal.setitimer(
                    signal.ITIMER_REAL, inputs.registered.plan.budget.max_elapsed_seconds
                )
                try:
                    # Conservative initial pacing also separates successive process invocations.
                    time.sleep(inputs.registered.plan.budget.min_interval_seconds)
                    acquired = acquire_registered_candidate(
                        inputs.registered,
                        repository=repository,
                        workspace=args.workspace,
                        transport=transport,
                        kind="historical",
                        reused_acquisitions=cached,
                        supplemental_evidence={
                            "policy.json": inputs.raw_bytes,
                            "lineage.json": canonical_json(
                                {
                                    "parent_candidate_sha256": inputs.original.manifest_sha256,
                                    "provider_correction_claimed": False,
                                }
                            ),
                        },
                        storage_guard=authority.check_storage,
                        budget_factory=lambda storage: authority.session_budget(
                            max_attempts=inputs.registered.plan.budget.max_attempts,
                            max_received_body_bytes=inputs.registered.plan.budget.max_received_body_bytes,
                            max_elapsed_seconds=inputs.registered.plan.budget.max_elapsed_seconds,
                            min_interval_seconds=inputs.registered.plan.budget.min_interval_seconds,
                            event_callback=storage.append_event,
                        ),
                        action_evaluator=make_action_evaluator(inputs),
                        pilot_gate=make_pilot_gate(inputs),
                        stop_on_pilot_failure=True,
                    )
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, previous)
                after = authority.snapshot()
                result = {
                    "manifest_path": str(acquired.manifest_path),
                    "budget_before": before,
                    "budget_after": after,
                    "terminal_error": acquired.stopped_code,
                    "larger_acquisition_permitted": acquired.pilot_passed,
                }
            print(canonical_json(result).decode(), end="")
            return (
                1
                if args.command == "acquire"
                and (acquired.stopped_code or not acquired.pilot_passed)
                else 0
            )
    except _Deadline:
        print('{"error":"session_deadline_exceeded","manual_budget_review_required":true}')
        return 1
    except Exception as exc:
        code = getattr(exc, "code", None)
        safe = (
            code
            if isinstance(code, str) and code.replace("_", "").isalnum()
            else "requalification_failed"
        )
        if isinstance(exc, ValueError) and str(exc) == "credentials_unavailable":
            print('{"credentials_available":false}')
            safe = "credentials_unavailable"
        print(canonical_json({"error": safe}).decode(), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

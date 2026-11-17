"""Finite opt-in acquisition; immutable candidates remain distinct from admitted v2 data.

No strategy, broker, automatic resume, credential discovery, or public data export.
An unsuccessful query is retained as evidence, never promoted into a complete receipt.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from packages.data.acquisition_budget import (
    BoundedHistoricalTransport,
    BudgetedHistoricalTransport,
    HistoricalSessionBudget,
)
from packages.data.acquisition_plan import RegisteredAcquisitionPlan
from packages.data.alpaca_historical import (
    AlpacaHistoricalAcquirer,
    HistoricalAcquisition,
    HistoricalAcquisitionError,
    HistoricalBarsRequest,
    HttpResponse,
    normalize_corporate_actions,
    normalize_historical_bars,
)
from packages.data.candidate_publication import publish_candidate
from packages.data.historical_candidates import (
    CandidateAcquisition,
    CandidateFile,
    CandidateManifest,
    CandidatePage,
    EvidenceDecision,
    FailureCode,
    load_historical_candidate,
)
from packages.data.historical_models import (
    HistoricalAvailability,
    HistoricalLicense,
    SecurityIdentity,
    SnapshotRevision,
    SymbolMapping,
)
from packages.data.historical_normalization import (
    HistoricalNormalizationError,
    to_acquisition_provenance,
    to_snapshot_bar,
)
from packages.data.historical_qualification import (
    qualification_report_bytes,
    qualify_historical_candidate,
)
from packages.data.private_storage import PrivateStorage, PrivateStorageError
from packages.research.artifacts import canonical_json, content_hashes, publish_artifacts


@dataclass(frozen=True)
class AcquisitionResult:
    manifest_path: Path
    attempts: int
    received_body_bytes: int
    successful_body_bytes: int
    pilot_passed: bool
    stopped_code: str | None


class _Capture:
    def __init__(
        self,
        transport: BudgetedHistoricalTransport,
        storage: PrivateStorage,
        clock: Callable[[], datetime],
    ) -> None:
        self.transport, self.storage, self.clock = transport, storage, clock
        self.acquisition_id = ""
        self.pages: list[CandidatePage] = []
        self.files: dict[str, bytes] = {}

    def get(self, endpoint: str, params: Mapping[str, str], timeout_seconds: float) -> HttpResponse:
        response = self.transport.get(endpoint, params, timeout_seconds)
        relative = f"pages/{self.acquisition_id}/{len(self.pages):04d}.json"
        try:
            self.storage.write_bytes("captures/" + relative, response.body)
        except PrivateStorageError:
            # A persistence failure must never be mistaken for a retryable HTTP error.
            raise HistoricalAcquisitionError("session_journal_failed") from None
        self.files[relative] = response.body
        self.pages.append(
            CandidatePage(
                file_path=relative,
                query=tuple(sorted(params.items())),
                received_at=self.clock(),
                http_status=response.status_code,
            )
        )
        return response


def _unverified(statement: str, *references: str) -> EvidenceDecision:
    return EvidenceDecision(status="unverified", statement=statement, source_refs=references)


def acquire_registered_candidate(
    registered: RegisteredAcquisitionPlan,
    *,
    repository: Path,
    workspace: Path,
    transport: BoundedHistoricalTransport,
    kind: Literal["historical", "synthetic"],
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> AcquisitionResult:
    """Execute one fresh sequential session under one shared durable budget.

    Library injection supports credential-free synthetic HTTP tests. The CLI alone
    supplies authenticated transport after explicit opt-in. No retry/resume of a
    previously created workspace is supported: an interrupted reservation remains
    evidence and requires manual review within the checkpoint's remaining budget.
    """
    plan = registered.plan
    storage = PrivateStorage(workspace, repository, plan.budget.max_local_bytes)
    storage.write_bytes("registered-plan.json", registered.raw_bytes)
    storage.write_bytes(
        "calendar.json",
        canonical_json(
            {
                "source_sha256": registered.calendar.sha256,
                "source_refs": registered.calendar.source_refs,
                "sessions": [s.model_dump(mode="json") for s in registered.calendar.sessions],
            }
        ),
    )
    source_files = {
        str(p.relative_to(repository)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((repository / "packages/data").glob("*.py"))
    }
    for relative in ("uv.lock", "pyproject.toml", "packages/research/artifacts.py"):
        path = repository / relative
        if path.is_file():
            source_files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    storage.write_bytes("source-fingerprints.json", canonical_json(source_files))
    revision = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    import pydantic

    storage.write_bytes(
        "runtime/environment.json",
        canonical_json(
            {
                "python": platform.python_version(),
                "pydantic": pydantic.__version__,
                "head": revision.stdout.strip() if revision.returncode == 0 else None,
                "source_note": (
                    "Exact file hashes describe acquisition code including any uncommitted edits."
                ),
            }
        ),
    )
    budget = HistoricalSessionBudget(
        max_attempts=plan.budget.max_attempts,
        max_received_body_bytes=plan.budget.max_received_body_bytes,
        max_elapsed_seconds=plan.budget.max_elapsed_seconds,
        min_interval_seconds=plan.budget.min_interval_seconds,
        monotonic=monotonic,
        sleep=sleep,
        event_callback=storage.append_event,
    )
    capture = _Capture(
        BudgetedHistoricalTransport(transport=transport, budget=budget), storage, clock
    )
    acquirer = AlpacaHistoricalAcquirer(
        transport=capture,
        clock=clock,
        sleep=sleep,
        timeout_seconds=plan.budget.timeout_seconds,
        max_total_body_bytes=plan.budget.max_received_body_bytes,
    )
    records: list[CandidateAcquisition] = []
    files: dict[str, bytes] = {}
    roles: dict[str, tuple[str, str | None]] = {}
    skipped: list[dict[str, str]] = []
    pilot_passed = False
    pilot_completed: set[str] = set()
    stopped: str | None = None
    for stage in plan.stages:
        if stopped is not None or (stage.role == "candidate" and not pilot_passed):
            skipped.append(
                {"acquisition_id": stage.acquisition_id, "reason": stopped or "pilot_not_qualified"}
            )
            continue
        capture.acquisition_id, capture.pages = stage.acquisition_id, []
        started = clock()
        acquired: HistoricalAcquisition | None = None
        error: str | None = None
        normalization_error: str | None = None
        try:
            request = stage.request
            acquired = (
                acquirer.fetch_bars(request)
                if isinstance(request, HistoricalBarsRequest)
                else acquirer.fetch_actions(request)
            )
        except HistoricalAcquisitionError as exc:
            error = exc.code
        finished = acquired.acquired_at if acquired is not None else clock()
        pages = capture.pages
        if acquired is not None:
            # Bind page timestamps to the exact acquirer receipt used by normalization.
            successful = iter(acquired.pages)
            pages = [
                p.model_copy(update={"received_at": next(successful).received_at})
                if p.http_status == 200
                else p
                for p in pages
            ]
            try:
                if isinstance(stage.request, HistoricalBarsRequest):
                    sessions = [
                        s
                        for s in registered.calendar.sessions
                        if stage.request.start <= s.date <= stage.request.end
                    ]
                    if sessions:
                        normalized = normalize_historical_bars(
                            acquired,
                            sessions=sessions,
                            missing_policy="error",
                        )
                        if stage.request.adjustment == "raw":
                            bars = [
                                to_snapshot_bar(
                                    bar,
                                    security_id="research:" + bar.bar.symbol,
                                    acquisition_id=stage.acquisition_id,
                                    mocked=kind == "synthetic",
                                ).model_dump(mode="json")
                                for bar in normalized.bars
                            ]
                            name = f"normalized/{stage.acquisition_id}-bars.json"
                            files[name] = canonical_json(bars)
                            roles[name] = ("normalized_bars", stage.acquisition_id)
                    # Early-year probes lack a qualified calendar, intentionally remain raw.
                else:
                    actions = normalize_corporate_actions(
                        acquired,
                        security_ids={s: "research:" + s for s in stage.request.symbols},
                    )
                    name = f"normalized/{stage.acquisition_id}-actions.json"
                    files[name] = canonical_json([a.model_dump(mode="json") for a in actions])
                    roles[name] = ("normalized_actions", stage.acquisition_id)
                if not (
                    isinstance(stage.request, HistoricalBarsRequest)
                    and stage.request.adjustment != "raw"
                ):
                    receipt = to_acquisition_provenance(
                        acquired,
                        acquisition_id=stage.acquisition_id,
                        mocked=kind == "synthetic",
                    )
                    name = f"receipts/{stage.acquisition_id}.json"
                    files[name] = canonical_json(receipt.model_dump(mode="json"))
                    roles[name] = ("evidence", stage.acquisition_id)
            except (HistoricalAcquisitionError, HistoricalNormalizationError) as exc:
                normalization_error = exc.code
        if stage.role == "pilot" and error is None and normalization_error is None:
            pilot_completed.add(stage.request_kind)
            pilot_passed = pilot_completed == {"bars", "actions"}
        records.append(
            CandidateAcquisition(
                acquisition_id=stage.acquisition_id,
                role=stage.role,
                request_kind=stage.request_kind,
                request=stage.request,
                request_started_at=started,
                acquired_at=finished,
                pages=tuple(pages),
                complete=acquired is not None,
                error_code=cast(FailureCode | None, error),
                normalization_error_code=cast(FailureCode | None, normalization_error),
            )
        )
        for page in pages:
            files[page.file_path] = capture.files[page.file_path]
            roles[page.file_path] = ("raw_page", stage.acquisition_id)
        if error is not None:
            # Entitlement/authentication, resource, transport and provider errors close this
            # bounded session. A caller must not silently restart its request allowance.
            stopped = error
        elif stage.role == "preflight" and normalization_error is not None:
            stopped = normalization_error
    frozen = clock()
    identities = tuple(
        SecurityIdentity(
            security_id="research:" + symbol,
            mappings=(
                SymbolMapping(
                    symbol=symbol,
                    start=min(s.request.start for s in plan.stages),
                    end=plan.candidate_end,
                    source=(
                        "query ticker only; no verified permanent identity or historical membership"
                    ),
                    available_at=frozen,
                    availability_basis="synthetic" if kind == "synthetic" else "observed",
                    point_in_time_status="uncertain",
                ),
            ),
        )
        for symbol in sorted({s for stage in plan.stages for s in stage.request.symbols})
    )
    evidence = {
        "registered-plan.json": registered.raw_bytes,
        "calendar.json": (storage.root / "calendar.json").read_bytes(),
        "source-fingerprints.json": canonical_json(source_files),
        "execution-summary.json": canonical_json(
            {
                "budget": budget.snapshot(),
                "pilot_passed": pilot_passed,
                "stopped_code": stopped,
                "skipped": skipped,
            }
        ),
    }
    for name, body in evidence.items():
        files["evidence/" + name] = body
        roles["evidence/" + name] = ("evidence", None)
    manifest = CandidateManifest(
        schema_version="historical-candidate/v1",
        kind=kind,
        candidate_id=plan.plan_id
        + "-"
        + hashlib.sha256(
            canonical_json(
                {
                    "files": content_hashes(files),
                    "frozen_at": frozen.isoformat(),
                }
            )
        ).hexdigest(),
        frozen_at=frozen,
        feed=plan.feed,
        symbols=plan.symbols,
        start=plan.candidate_start,
        end=plan.candidate_end,
        sessions=registered.calendar.sessions,
        calendar_evidence=EvidenceDecision(
            status="confirmed",
            source_refs=registered.calendar.source_refs,
            statement=(
                "Versioned official US regular-session schedule; "
                "not provider daily-bar aggregation proof."
            ),
        ),
        license=HistoricalLicense(
            name="Alpaca Basic personal noncommercial IEX candidate",
            reference="; ".join(plan.entitlement_sources),
            entitlement="confirmed",
            storage="confirmed",
            retention="requires_clarification",
            raw_redistribution="prohibited",
            derived_publication="requires_clarification",
            restrictions=(
                plan.rights_statement,
                "IEX venue-only; no SIP or public empirical data grant.",
            ),
        ),
        availability=HistoricalAvailability(
            mode="synthetic" if kind == "synthetic" else "observed",
            statement=(
                "Acquisition-observed availability only; "
                "historical first publication/revisions unverified."
            ),
            evidence_reference="Per-page UTC receive timestamps and immutable source hashes.",
        ),
        identities=identities,
        action_inventory=_unverified(
            "Exhausted process-date queries do not establish complete historical ex-date coverage.",
            "https://docs.alpaca.markets/us/reference/corporateactions-1",
        ),
        reconciliation=_unverified(
            "Issuer reconciliation and permanent historical identities require separate evidence."
        ),
        revision=SnapshotRevision(
            revision_id="initial-observed-candidate",
            parent_manifest_sha256=None,
            correction_observed_at=None,
            reason="First immutable acquisition; no revision history inferred.",
        ),
        files=tuple(
            CandidateFile(
                path=name,
                role=cast(
                    Literal["raw_page", "normalized_bars", "normalized_actions", "evidence"],
                    roles[name][0],
                ),
                acquisition_id=roles[name][1],
                size_bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
            )
            for name, body in sorted(files.items())
        ),
        acquisitions=tuple(records),
    )
    path = publish_candidate(
        storage,
        "frozen",
        manifest,
        files,
        canonical_json(
            {
                "schema_version": "historical-acquisition-runtime/v1",
                "completed_at": clock().isoformat(),
            }
        ),
    )
    load_historical_candidate(path)
    return AcquisitionResult(
        path,
        budget.attempts,
        budget.received_body_bytes,
        budget.successful_body_bytes,
        pilot_passed,
        stopped,
    )


def qualify_candidate(manifest: Path, output: Path) -> dict[str, object]:
    """Offline deterministic diagnostics; historical outputs stay in ignored private storage."""
    candidate = load_historical_candidate(manifest)
    if candidate.manifest.kind == "historical":
        if ".." in output.parts or ".." in manifest.parts:
            raise ValueError("private_qualification_output_required")
        # Require both paths in the same existing private checkpoint workspace.
        private = next(
            (
                p
                for p in manifest.absolute().parents
                if p.parent.name == "r4b" and p.parent.parent.name == "private"
            ),
            None,
        )
        if private is None or not output.absolute().is_relative_to(private):
            raise ValueError("private_qualification_output_required")
        repository = private.parent.parent.parent.parent
        ignored = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "check-ignore",
                "--quiet",
                "--no-index",
                "--",
                str(output.absolute().relative_to(repository)),
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if ignored.returncode:
            raise ValueError("private_qualification_output_required")
        if any(p.is_symlink() for p in (output, *output.parents)):
            raise ValueError("private_qualification_output_required")
    report = qualify_historical_candidate(candidate)
    files = {
        "qualification.json": qualification_report_bytes(report),
        "input-inventory.json": canonical_json(
            {
                "candidate_manifest_sha256": candidate.manifest_sha256,
                "files": {
                    f.path: {"sha256": f.sha256, "size_bytes": f.size_bytes}
                    for f in candidate.manifest.files
                },
            }
        ),
    }
    if candidate.manifest.kind == "historical":
        assert private is not None
        retained = sum(p.stat().st_size for p in private.rglob("*") if p.is_file())
        if retained + sum(map(len, files.values())) + 16384 > 1024**3:
            raise ValueError("private_storage_limit")
    import os

    previous = os.umask(0o077)
    try:
        publish_artifacts(
            output, files, canonical_json({"qualified_at": datetime.now(UTC).isoformat()})
        )
    finally:
        os.umask(previous)
    return {
        "status": report.status,
        "technical_status": report.technical_status,
        "next_phase": report.next_phase,
        "hashes": content_hashes(files),
        "candidate_manifest_sha256": candidate.manifest_sha256,
    }

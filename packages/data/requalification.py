"""Pinned offline R4-B.1 evidence, action scope, and conservative acquisition gates.

Full-query diagnostics remain unchanged. Scoped normalization is derived evidence,
and a technically usable pilot does not admit v2 inputs or authorize R4-C.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import Field, ValidationError, field_validator

from packages.data.acquisition_plan import (
    AcquisitionStage,
    RegisteredAcquisitionPlan,
    load_acquisition_plan,
)
from packages.data.acquisition_session import ActionEvaluation
from packages.data.action_reconciliation import IndependentActionRecord, reconcile_actions
from packages.data.action_scope import (
    ActionScopeContext,
    ActionScopeReport,
    classify_action_scope,
    normalize_applicable_actions,
    private_report_bytes,
    public_scope_report_bytes,
)
from packages.data.alpaca_historical import (
    AcquiredPage,
    CorporateActionsRequest,
    HistoricalAcquisition,
    HistoricalAcquisitionError,
    HistoricalBarsRequest,
    decode_historical_page,
    historical_query,
    normalize_historical_bars,
)
from packages.data.corporate_actions import CorporateAction
from packages.data.historical_candidates import (
    CandidateAcquisition,
    CandidateManifest,
    HistoricalCandidate,
    load_historical_candidate,
)
from packages.data.historical_models import SHA_PATTERN, HistoricalModel
from packages.data.historical_normalization import (
    HistoricalNormalizationError,
    to_acquisition_provenance,
)
from packages.data.historical_qualification import (
    HistoricalQualificationReport,
    qualify_historical_candidate,
)

_MAX_FILE_BYTES = 16 * 1024**2
_MAX_TOTAL_BYTES = 64 * 1024**2


class RequalificationError(ValueError):
    """Closed errors contain no private source values or filesystem details."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _relative(value: str) -> str:
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("requalification_path")
    return value


class IssuerIndexReference(HistoricalModel):
    path: str
    sha256: str = Field(pattern=SHA_PATTERN)

    _path = field_validator("path")(_relative)


class RequalificationPolicy(HistoricalModel):
    schema_version: Literal["historical-requalification-policy/v1"]
    checkpoint: Literal["R4-B.1"]
    plan_path: str
    plan_sha256: str = Field(pattern=SHA_PATTERN)
    original_manifest_path: str
    original_manifest_sha256: str = Field(pattern=SHA_PATTERN)
    original_qualification_path: str
    original_qualification_sha256: str = Field(pattern=SHA_PATTERN)
    seed_events_path: str
    seed_events_sha256: str = Field(pattern=SHA_PATTERN)
    issuer_indexes: tuple[IssuerIndexReference, ...] = Field(min_length=1)
    independent_actions_path: str
    independent_actions_sha256: str = Field(pattern=SHA_PATTERN)
    flagged_event_evidence_path: str
    flagged_event_evidence_sha256: str = Field(pattern=SHA_PATTERN)
    pilot_scope: ActionScopeContext
    candidate_scope: ActionScopeContext

    _paths = field_validator(
        "plan_path",
        "original_manifest_path",
        "original_qualification_path",
        "seed_events_path",
        "independent_actions_path",
        "flagged_event_evidence_path",
    )(_relative)


@dataclass(frozen=True)
class RequalificationInputs:
    policy: RequalificationPolicy
    registered: RegisteredAcquisitionPlan
    original: HistoricalCandidate
    independent_actions: tuple[IndependentActionRecord, ...]
    evidence_hashes: Mapping[str, str]
    sha256: str
    raw_bytes: bytes
    original_qualification: Mapping[str, object]
    flagged_event_evidence: Mapping[str, object]


def _decode(raw: bytes) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def reject(value: str) -> None:
        raise ValueError

    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject)


def _object(raw: bytes) -> dict[str, object]:
    result = _decode(raw)
    if not isinstance(result, dict):
        raise RequalificationError("requalification_schema")
    return result


class _Reader:
    def __init__(self, repository: Path) -> None:
        self.repository = repository.absolute()
        self.hashes: dict[str, str] = {}
        self.bodies: dict[str, bytes] = {}
        self.total = 0

    def read(
        self,
        logical: str,
        expected: str | None = None,
        *,
        private: bool = True,
        maximum: int = _MAX_FILE_BYTES,
    ) -> bytes:
        _relative(logical)
        path = self.repository / logical
        if private and Path(logical).parts[:3] != ("datasets", "private", "r4b"):
            raise RequalificationError("requalification_path")
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise RequalificationError("requalification_path")
        if logical not in self.bodies:
            with os.fdopen(
                os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb"
            ) as stream:
                details = os.fstat(stream.fileno())
                if not stat.S_ISREG(details.st_mode) or details.st_size > maximum:
                    raise RequalificationError("requalification_size")
                raw = stream.read(maximum + 1)
            self.total += len(raw)
            if len(raw) > maximum or self.total > _MAX_TOTAL_BYTES:
                raise RequalificationError("requalification_size")
            self.bodies[logical] = raw
            self.hashes[logical] = hashlib.sha256(raw).hexdigest()
        raw = self.bodies[logical]
        if len(raw) > maximum:
            raise RequalificationError("requalification_size")
        if expected is not None and self.hashes[logical] != expected:
            raise RequalificationError("requalification_hash")
        return raw


def load_requalification_inputs(policy_path: Path, repository: Path) -> RequalificationInputs:
    """Verify all local bindings before any callback may use the independent evidence."""
    try:
        reader = _Reader(repository)
        logical_policy = policy_path.absolute().relative_to(reader.repository).as_posix()
        raw = reader.read(logical_policy, private=False, maximum=1024**2)
        policy = RequalificationPolicy.model_validate(_object(raw))
        reader.read(policy.plan_path, policy.plan_sha256, private=False, maximum=1024**2)
        registered = load_acquisition_plan(reader.repository / policy.plan_path)
        if registered.sha256 != policy.plan_sha256:
            raise RequalificationError("requalification_binding")
        calendar = (Path(policy.plan_path).parent / registered.plan.calendar_path).as_posix()
        reader.read(calendar, registered.plan.calendar_sha256, private=False)
        pilot = next(
            s for s in registered.plan.stages if s.role == "pilot" and s.request_kind == "bars"
        )
        if (
            len(registered.plan.stages) != 6
            or policy.pilot_scope.start != pilot.request.start
            or policy.pilot_scope.end != pilot.request.end
            or policy.candidate_scope.start != registered.plan.candidate_start
            or policy.candidate_scope.end != registered.plan.candidate_end
        ):
            raise RequalificationError("requalification_scope")
        original_raw = reader.read(
            policy.original_manifest_path, policy.original_manifest_sha256, maximum=1024**2
        )
        manifest = CandidateManifest.model_validate(_object(original_raw))
        for entry in manifest.files:
            logical = (Path(policy.original_manifest_path).parent / entry.path).as_posix()
            body = reader.read(logical, entry.sha256)
            if len(body) != entry.size_bytes:
                raise RequalificationError("requalification_size")
        original = load_historical_candidate(
            reader.repository / policy.original_manifest_path,
            expected_sha256=policy.original_manifest_sha256,
        )
        if (
            original.manifest.feed != registered.plan.feed
            or original.manifest.symbols != registered.plan.symbols
        ):
            raise RequalificationError("requalification_binding")
        old_preflight = {
            r.request_kind: r for r in original.manifest.acquisitions if r.role == "preflight"
        }
        for stage in registered.plan.stages:
            if stage.role == "preflight" and (
                stage.request_kind not in old_preflight
                or stage.request != old_preflight[stage.request_kind].request
            ):
                raise RequalificationError("requalification_binding")
        old_quality_raw = reader.read(
            policy.original_qualification_path,
            policy.original_qualification_sha256,
            maximum=1024**2,
        )
        original_quality = _object(old_quality_raw)
        quality = HistoricalQualificationReport.model_validate(original_quality)
        if quality.candidate_manifest_sha256 != original.manifest_sha256:
            raise RequalificationError("requalification_binding")
        reader.read(policy.seed_events_path, policy.seed_events_sha256)
        indexed: set[str] = set()
        for reference in policy.issuer_indexes:
            index = _object(reader.read(reference.path, reference.sha256, maximum=2 * 1024**2))
            inventory = index.get("files")
            if not isinstance(inventory, dict) or not inventory:
                raise RequalificationError("requalification_index")
            for name, descriptor in inventory.items():
                _relative(name)
                if not isinstance(descriptor, dict):
                    raise RequalificationError("requalification_index")
                size, sha = descriptor.get("size_bytes"), descriptor.get("sha256")
                if (
                    isinstance(size, bool)
                    or not isinstance(size, int)
                    or size < 0
                    or not isinstance(sha, str)
                    or re.fullmatch(SHA_PATTERN, sha) is None
                ):
                    raise RequalificationError("requalification_index")
                logical = (Path(reference.path).parent / name).as_posix()
                if len(reader.read(logical, sha)) != size:
                    raise RequalificationError("requalification_size")
                indexed.add(logical)
        if not {policy.independent_actions_path, policy.flagged_event_evidence_path} <= indexed:
            raise RequalificationError("requalification_binding")
        independent_raw = reader.read(
            policy.independent_actions_path, policy.independent_actions_sha256
        )
        independent_value = _decode(independent_raw)
        if not isinstance(independent_value, list):
            raise RequalificationError("requalification_schema")
        independent = tuple(
            IndependentActionRecord.model_validate(row) for row in independent_value
        )
        if any(
            record.source_sha256 not in {reader.hashes[name] for name in indexed}
            for record in independent
        ):
            raise RequalificationError("requalification_binding")
        flagged = _object(
            reader.read(policy.flagged_event_evidence_path, policy.flagged_event_evidence_sha256)
        )
        return RequalificationInputs(
            policy,
            registered,
            original,
            independent,
            MappingProxyType(reader.hashes),
            hashlib.sha256(raw).hexdigest(),
            raw,
            MappingProxyType(original_quality),
            MappingProxyType(flagged),
        )
    except RequalificationError:
        raise
    except (
        OSError,
        ValueError,
        ValidationError,
        KeyError,
        TypeError,
        StopIteration,
        RecursionError,
    ):
        raise RequalificationError("requalification_schema") from None


def make_action_evaluator(
    inputs: RequalificationInputs,
) -> Callable[[AcquisitionStage, HistoricalAcquisition, Mapping[str, str]], ActionEvaluation]:
    def evaluate(
        stage: AcquisitionStage, acquisition: HistoricalAcquisition, security_ids: Mapping[str, str]
    ) -> ActionEvaluation:
        context = (
            inputs.policy.candidate_scope
            if stage.role == "candidate"
            else inputs.policy.pilot_scope
        )
        report = classify_action_scope(acquisition, context)
        evidence = {
            "scope-private.json": private_report_bytes(report),
            "scope-summary.json": public_scope_report_bytes(report),
        }
        if report.blocked:
            unsupported = any(
                row.scope == "applicable" and row.support == "unsupported" for row in report.records
            )
            return ActionEvaluation(
                (),
                evidence,
                "unsupported_corporate_action" if unsupported else "invalid_corporate_action",
            )
        try:
            actions = normalize_applicable_actions(acquisition, report, security_ids=security_ids)
            return ActionEvaluation(actions, evidence)
        except (HistoricalAcquisitionError, ValueError):
            return ActionEvaluation((), evidence, "invalid_corporate_action")

    return evaluate


def _projection(record: CandidateAcquisition, files: Mapping[str, bytes]) -> HistoricalAcquisition:
    endpoint, base_query = historical_query(record.request)
    token: str | None = None
    seen: set[str] = set()
    previous = record.request_started_at
    terminal = False
    successful = 0
    if (
        previous.utcoffset() is None
        or record.acquired_at.utcoffset() is None
        or record.acquired_at < previous
    ):
        raise ValueError("requalification_source_pages")
    for page in record.pages:
        expected = dict(base_query)
        if token is not None:
            expected["page_token"] = token
        body = files[page.file_path]
        if (
            terminal
            or not isinstance(body, bytes)
            or len(dict(page.query)) != len(page.query)
            or dict(page.query) != expected
            or page.received_at.utcoffset() is None
            or not previous <= page.received_at <= record.acquired_at
        ):
            raise ValueError("requalification_source_pages")
        previous = page.received_at
        if page.http_status != 200:
            if page.http_status not in {429, 500, 502, 503, 504}:
                raise ValueError("requalification_source_pages")
            continue
        successful += 1
        payload = decode_historical_page(body)
        next_token = payload["next_page_token"]
        if next_token is not None and (
            not isinstance(next_token, str)
            or not next_token
            or len(next_token) > 4096
            or next_token in seen
        ):
            raise ValueError("requalification_source_pages")
        token = next_token
        if token is not None:
            seen.add(token)
        terminal = token is None
    if (
        not terminal
        or not 1 <= successful <= record.request.max_pages
        or previous != record.acquired_at
    ):
        raise ValueError("requalification_source_pages")
    result = HistoricalAcquisition(
        record.request,
        record.request_started_at,
        record.acquired_at,
        tuple(
            AcquiredPage(endpoint, page.query, files[page.file_path], page.received_at)
            for page in record.pages
            if page.http_status == 200
        ),
    )
    to_acquisition_provenance(result, acquisition_id=record.acquisition_id, mocked=True)
    return result


def _pilot_check(
    inputs: RequalificationInputs,
    records: Sequence[CandidateAcquisition],
    files: Mapping[str, bytes],
) -> tuple[dict[str, object], tuple[CorporateAction, ...] | None]:
    pilot = [record for record in records if record.role == "pilot"]
    findings: list[str] = []
    actions: tuple[CorporateAction, ...] | None = None
    if len(pilot) != 2 or {record.request_kind for record in pilot} != {"bars", "actions"}:
        findings.append("pilot_primary_queries_unavailable")
    expected = {
        stage.request_kind: stage.request
        for stage in inputs.registered.plan.stages
        if stage.role == "pilot"
    }
    for record in pilot:
        if (
            not record.complete
            or record.error_code is not None
            or record.normalization_error_code is not None
            or record.request != expected.get(record.request_kind)
        ):
            findings.append("pilot_acquisition_or_normalization_failed")
            continue
        try:
            acquisition = _projection(record, files)
            if isinstance(record.request, HistoricalBarsRequest):
                sessions = tuple(
                    s
                    for s in inputs.registered.calendar.sessions
                    if record.request.start <= s.date <= record.request.end
                )
                normalize_historical_bars(acquisition, sessions=sessions, missing_policy="error")
            else:
                report = classify_action_scope(acquisition, inputs.policy.pilot_scope)
                if report.blocked:
                    findings.append("pilot_action_scope_blocked")
                else:
                    actions = normalize_applicable_actions(
                        acquisition,
                        report,
                        security_ids={s: "research:" + s for s in record.request.symbols},
                    )
        except (
            HistoricalAcquisitionError,
            HistoricalNormalizationError,
            ValueError,
            KeyError,
            TypeError,
        ):
            findings.append("pilot_source_evidence_invalid")
    if findings:
        actions = None
    return {"status": "FAIL" if findings else "PASS", "findings": sorted(set(findings))}, actions


def _reconciliation(
    inputs: RequalificationInputs, actions: tuple[CorporateAction, ...] | None
) -> dict[str, object]:
    if actions is None:
        return {
            "available": False,
            "status": "RESTRICTED",
            "reason": "pilot_scope_or_normalization_blocks_reconciliation",
            "independent_count": len(inputs.independent_actions),
            "complete_independent_inventory": False,
        }
    report = reconcile_actions(
        actions,
        inputs.independent_actions,
        start=inputs.policy.pilot_scope.start,
        end=inputs.policy.pilot_scope.end,
        complete_independent_inventory=False,
    )
    return {"available": True, **report.model_dump(mode="json")}


def _original_scopes(inputs: RequalificationInputs) -> tuple[ActionScopeReport, ...]:
    return tuple(
        classify_action_scope(acquisition, inputs.policy.candidate_scope)
        for acquisition in inputs.original.acquisitions
        if isinstance(acquisition.request, CorporateActionsRequest)
    )


def make_pilot_gate(
    inputs: RequalificationInputs,
) -> Callable[[tuple[CandidateAcquisition, ...], Mapping[str, bytes]], bool]:
    def gate(records: tuple[CandidateAcquisition, ...], files: Mapping[str, bytes]) -> bool:
        try:
            technical, actions = _pilot_check(inputs, records, files)
            if technical["status"] != "PASS" or any(
                report.blocked for report in _original_scopes(inputs)
            ):
                return False
            reconciliation = _reconciliation(inputs, actions)
            return (
                bool(reconciliation["available"])
                and reconciliation["status"] == "PASS"
                and all(
                    reconciliation[name] == 0
                    for name in (
                        "missing_provider_count",
                        "missing_independent_count",
                        "mismatched_count",
                        "ambiguous_count",
                        "unsupported_count",
                    )
                )
            )
        except (HistoricalAcquisitionError, ValueError, KeyError, TypeError):
            return False

    return gate


def build_requalification_report(
    candidate: HistoricalCandidate, inputs: RequalificationInputs
) -> dict[str, object]:
    """Produce deterministic aggregates; retain every full-query failure separately."""
    base = qualify_historical_candidate(candidate).model_dump(mode="json")
    technical, actions = _pilot_check(inputs, candidate.manifest.acquisitions, candidate.files)
    scopes = []
    for record, acquisition in zip(
        candidate.manifest.acquisitions, candidate.acquisitions, strict=True
    ):
        if isinstance(acquisition.request, CorporateActionsRequest):
            context = (
                inputs.policy.candidate_scope
                if record.role == "candidate"
                else inputs.policy.pilot_scope
            )
            report = classify_action_scope(acquisition, context)
            scopes.append({"role": record.role, **_object(public_scope_report_bytes(report))})
    original_scopes = _original_scopes(inputs)
    known_blocked = any(report.blocked for report in original_scopes)
    reasons = {
        "historical_availability_unverified",
        "permanent_identity_unverified",
        "retention_unverified",
        "action_inventory_completeness_unverified",
        "no_v2_admission_in_requalification",
    }
    if known_blocked:
        reasons.add("known_original_candidate_period_action_blocked")
    if technical["status"] != "PASS":
        reasons.add("technical_pilot_failed")
    reconciliation = _reconciliation(inputs, actions)
    if reconciliation["status"] != "PASS":
        reasons.add("independent_reconciliation_restricted")
    evidence = inputs.flagged_event_evidence
    equalities = evidence.get("economic_equalities")
    if isinstance(equalities, Mapping) and equalities.get("pay_date_equal") is False:
        reasons.add("issuer_provider_payable_date_conflict")
    if evidence.get("currency_independently_established") is not True:
        reasons.add("independent_currency_unverified")
    return {
        "schema_version": "historical-requalification-report/v1",
        "checkpoint": "R4-B.1",
        "policy_sha256": inputs.sha256,
        "candidate_manifest_sha256": candidate.manifest_sha256,
        "original_manifest_sha256": inputs.original.manifest_sha256,
        "evidence_hashes": dict(sorted(inputs.evidence_hashes.items())),
        "original_qualification": deepcopy(dict(inputs.original_qualification)),
        "base_qualification": base,
        "scoped_actions": scopes,
        "known_original_candidate_scopes": [
            _object(public_scope_report_bytes(report)) for report in original_scopes
        ],
        "ordinary_action_reconciliation": reconciliation,
        "technical_pilot": technical,
        "larger_acquisition_gate_passed": make_pilot_gate(inputs)(
            candidate.manifest.acquisitions, candidate.files
        ),
        "scientific_readiness": {"decision": "BLOCKED", "reasons": sorted(reasons)},
        "dataset_to_r4c": "BLOCKED",
        "admitted_v2": False,
        "provider_flags_preserved": True,
        "historical_strategy_executed": False,
        "rights_expanded": False,
    }

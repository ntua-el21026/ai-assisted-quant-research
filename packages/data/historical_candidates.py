"""Private immutable evidence envelopes, separate from strict market-snapshot/v2.

Incomplete queries, unsupported source records and unresolved rights belong here.
Loading verifies bytes and provenance structure; qualification diagnoses their content.
No network request, credential discovery or input modification occurs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, ValidationError, field_validator, model_validator

from packages.data.alpaca_historical import (
    ACTIONS_ENDPOINT,
    BARS_ENDPOINT,
    AcquiredPage,
    CorporateActionsRequest,
    HistoricalAcquisition,
    HistoricalBarsRequest,
)
from packages.data.historical_models import (
    SHA_PATTERN,
    HistoricalAvailability,
    HistoricalLicense,
    HistoricalModel,
    HistoricalSession,
    SecurityIdentity,
    SnapshotRevision,
    utc,
)
from packages.data.quality import SnapshotError

FailureCode = Literal[
    "action_policy_failed",
    "pilot_gate_failed",
    "missing_credentials",
    "invalid_body_limit",
    "invalid_total_body_limit",
    "invalid_timeout",
    "endpoint_rejected",
    "redirect_rejected",
    "transport_failed",
    "body_limit_exceeded",
    "total_body_limit_exceeded",
    "authentication_failed",
    "forbidden",
    "invalid_request",
    "rate_limited",
    "provider_failed",
    "invalid_json",
    "invalid_page",
    "pagination_cycle",
    "page_limit_exceeded",
    "invalid_retry_header",
    "retry_budget_exceeded",
    "naive_clock",
    "clock_regressed",
    "invalid_normalization_request",
    "invalid_calendar",
    "invalid_bar_timestamp",
    "unexpected_session",
    "unexpected_symbol",
    "incomplete_session",
    "invalid_ohlcv",
    "duplicate_session",
    "missing_sessions",
    "availability_after_acquisition",
    "unknown_security_identity",
    "action_outside_process_window",
    "unsupported_corporate_action",
    "invalid_corporate_action",
    "ambiguous_dividend_share_basis",
    "raw_execution_required",
    "filtered_action_inventory",
    "invalid_acquisition_query",
    "invalid_pagination_chain",
    "invalid_acquisition_times",
    "request_budget_exceeded",
    "request_limit_exceeded",
    "acquisition_budget_exceeded",
    "invalid_request_budget",
    "invalid_session_budget",
    "session_clock_invalid",
    "session_deadline_exceeded",
    "session_journal_failed",
    "session_request_inflight",
    "session_attempt_limit",
    "session_byte_limit",
    "session_rate_wait_incomplete",
    "invalid_session_accounting",
    "bounded_transport_required",
    "invalid_body_length",
    "incomplete_body",
]


class EvidenceDecision(HistoricalModel):
    status: Literal["confirmed", "unverified", "contradictory"]
    source_refs: tuple[str, ...]
    statement: str = Field(min_length=1)

    @model_validator(mode="after")
    def confirmed_has_reference(self) -> Self:
        if self.status == "confirmed" and not self.source_refs:
            raise ValueError("confirmed_evidence_requires_reference")
        if any(not ref.strip() or ref != ref.strip() for ref in self.source_refs):
            raise ValueError("invalid_evidence_reference")
        return self


def _relative_path(value: str) -> str:
    path = Path(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in value
        or value != path.as_posix()
        or value in {"", "."}
    ):
        raise ValueError("unsafe_candidate_path")
    return value


class CandidateFile(HistoricalModel):
    path: str = Field(min_length=1)
    role: Literal["raw_page", "normalized_bars", "normalized_actions", "evidence"]
    size_bytes: int = Field(ge=0, strict=True)
    sha256: str = Field(pattern=SHA_PATTERN)
    acquisition_id: str | None = None

    _path = field_validator("path")(_relative_path)


class CandidatePage(HistoricalModel):
    file_path: str = Field(min_length=1)
    query: tuple[tuple[str, str], ...]
    received_at: datetime
    http_status: int = Field(default=200, ge=100, le=599, strict=True)

    _path = field_validator("file_path")(_relative_path)
    _time = field_validator("received_at")(utc)

    @model_validator(mode="after")
    def unique_query(self) -> Self:
        if len(dict(self.query)) != len(self.query):
            raise ValueError("duplicate_candidate_query_parameter")
        return self


class CandidateAcquisition(HistoricalModel):
    acquisition_id: str = Field(min_length=1)
    role: Literal["preflight", "pilot", "candidate", "diagnostic"]
    request_kind: Literal["bars", "actions"]
    request: HistoricalBarsRequest | CorporateActionsRequest
    request_started_at: datetime
    acquired_at: datetime
    pages: tuple[CandidatePage, ...]
    complete: bool
    error_code: FailureCode | None = None
    normalization_error_code: FailureCode | None = None

    _times = field_validator("request_started_at", "acquired_at")(utc)

    @model_validator(mode="after")
    def consistent_record(self) -> Self:
        if self.request_kind != (
            "bars" if isinstance(self.request, HistoricalBarsRequest) else "actions"
        ):
            raise ValueError("candidate_request_kind_mismatch")
        if self.acquired_at < self.request_started_at:
            raise ValueError("invalid_candidate_acquisition_interval")
        previous = self.request_started_at
        for page in self.pages:
            if not previous <= page.received_at <= self.acquired_at:
                raise ValueError("invalid_candidate_page_time")
            previous = page.received_at
        if self.complete:
            if self.error_code is not None or not any(p.http_status == 200 for p in self.pages):
                raise ValueError("candidate_completion_requires_success")
        elif self.error_code is None:
            raise ValueError("candidate_partial_requires_failure_code")
        return self


class CandidateManifest(HistoricalModel):
    schema_version: Literal["historical-candidate/v1"]
    kind: Literal["historical", "synthetic"]
    candidate_id: str = Field(min_length=1)
    frozen_at: datetime
    feed: Literal["iex", "sip"]
    symbols: tuple[str, ...] = Field(min_length=1)
    start: date
    end: date
    sessions: tuple[HistoricalSession, ...] = Field(min_length=1)
    calendar_evidence: EvidenceDecision
    license: HistoricalLicense
    availability: HistoricalAvailability
    identities: tuple[SecurityIdentity, ...]
    action_inventory: EvidenceDecision
    reconciliation: EvidenceDecision
    revision: SnapshotRevision
    files: tuple[CandidateFile, ...]
    acquisitions: tuple[CandidateAcquisition, ...]

    _freeze = field_validator("frozen_at")(utc)

    @model_validator(mode="after")
    def consistent_inventory(self) -> Self:
        if self.start > self.end:
            raise ValueError("invalid_candidate_date_interval")
        if self.symbols != tuple(sorted(set(self.symbols))):
            raise ValueError("candidate_symbols_not_canonical")
        if any(re.fullmatch(r"[A-Z][A-Z0-9.-]{0,19}", symbol) is None for symbol in self.symbols):
            raise ValueError("invalid_candidate_symbols")
        days = tuple(s.date for s in self.sessions)
        if days != tuple(sorted(set(days))) or any(
            not self.start <= day <= self.end for day in days
        ):
            raise ValueError("invalid_candidate_sessions")
        if any(s.close_at > self.frozen_at for s in self.sessions):
            raise ValueError("candidate_session_after_freeze")
        paths = {entry.path: entry for entry in self.files}
        acquisitions = {a.acquisition_id: a for a in self.acquisitions}
        if len(paths) != len(self.files) or len(acquisitions) != len(self.acquisitions):
            raise ValueError("duplicate_candidate_inventory")
        if len({s.security_id for s in self.identities}) != len(self.identities):
            raise ValueError("duplicate_candidate_identity")
        if any(a.acquired_at > self.frozen_at for a in self.acquisitions):
            raise ValueError("candidate_acquisition_after_freeze")
        corrected = self.revision.correction_observed_at
        if corrected is not None and corrected > self.frozen_at:
            raise ValueError("candidate_correction_after_freeze")
        referenced: list[str] = []
        for acquisition in self.acquisitions:
            for page in acquisition.pages:
                entry = paths.get(page.file_path)
                if (
                    entry is None
                    or entry.role != "raw_page"
                    or entry.acquisition_id != acquisition.acquisition_id
                ):
                    raise ValueError("candidate_page_file_mismatch")
                referenced.append(page.file_path)
        if len(referenced) != len(set(referenced)):
            raise ValueError("candidate_page_reused")
        if set(referenced) != {f.path for f in self.files if f.role == "raw_page"}:
            raise ValueError("candidate_raw_page_inventory_mismatch")
        if any(
            f.acquisition_id is not None and f.acquisition_id not in acquisitions
            for f in self.files
        ):
            raise ValueError("unknown_candidate_file_acquisition")
        return self


@dataclass(frozen=True)
class HistoricalCandidate:
    manifest: CandidateManifest
    manifest_sha256: str
    files: Mapping[str, bytes]
    acquisitions: tuple[HistoricalAcquisition, ...]


def decode_candidate_json(raw: bytes) -> object:
    """Reject duplicate keys and nonfinite JSON without including source text in errors."""

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for name, value in items:
            if name in result:
                raise ValueError("duplicate_json_key")
            result[name] = value
        return result

    def constant(value: str) -> None:
        raise ValueError("nonfinite_json_number")

    return json.loads(raw, parse_float=Decimal, parse_constant=constant, object_pairs_hook=pairs)


def load_historical_candidate(
    manifest_path: Path,
    *,
    expected_sha256: str | None = None,
) -> HistoricalCandidate:
    """Verify exact private evidence inventory, then project successful retained pages.

    A projection of a partial acquisition is still partial: completion/error truth
    remains in the associated CandidateAcquisition. It must not be certified as v2.
    """
    if any(p.is_symlink() for p in (manifest_path, *manifest_path.parents)):
        raise SnapshotError("candidate_unsafe_path")
    try:
        raw = manifest_path.read_bytes()
    except OSError:
        raise SnapshotError("candidate_missing_manifest") from None
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise SnapshotError("candidate_manifest_hash_mismatch")
    try:
        manifest = CandidateManifest.model_validate(decode_candidate_json(raw))
    except (ValidationError, ValueError, UnicodeError, RecursionError):
        raise SnapshotError("invalid_candidate_manifest") from None
    files: dict[str, bytes] = {}
    for entry in manifest.files:
        path = manifest_path.parent / entry.path
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise SnapshotError("candidate_unsafe_path")
        if not path.is_file():
            raise SnapshotError("candidate_missing_file")
        try:
            data = path.read_bytes()
        except OSError:
            raise SnapshotError("candidate_missing_file") from None
        if len(data) != entry.size_bytes:
            raise SnapshotError("candidate_size_mismatch")
        if hashlib.sha256(data).hexdigest() != entry.sha256:
            raise SnapshotError("candidate_hash_mismatch")
        files[entry.path] = data
    inventory: set[str] = set()
    for path in manifest_path.parent.rglob("*"):
        if path.is_symlink():
            raise SnapshotError("candidate_unsafe_path")
        if path.is_file():
            inventory.add(path.relative_to(manifest_path.parent).as_posix())
    if inventory != set(files) | {manifest_path.name}:
        raise SnapshotError("candidate_inventory_mismatch")
    acquisitions = tuple(
        HistoricalAcquisition(
            record.request,
            record.request_started_at,
            record.acquired_at,
            tuple(
                AcquiredPage(
                    BARS_ENDPOINT if record.request_kind == "bars" else ACTIONS_ENDPOINT,
                    page.query,
                    files[page.file_path],
                    page.received_at,
                )
                for page in record.pages
                if page.http_status == 200
            ),
        )
        for record in manifest.acquisitions
    )
    return HistoricalCandidate(manifest, digest, MappingProxyType(files), acquisitions)

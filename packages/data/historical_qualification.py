"""Deterministic, price-free quality reports for private historical candidates.

These decisions describe frozen data evidence. They do not run strategy execution,
measure returns, grant rights or establish historical first-publication timestamps.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field

from packages.data.alpaca_historical import (
    CorporateActionsRequest,
    HistoricalAcquisition,
    HistoricalAcquisitionError,
    HistoricalBarsRequest,
    historical_query,
    normalize_corporate_actions,
)
from packages.data.historical_candidates import (
    CandidateAcquisition,
    EvidenceDecision,
    HistoricalCandidate,
    decode_candidate_json,
)
from packages.data.historical_models import SHA_PATTERN, HistoricalModel
from packages.research.artifacts import canonical_json

Status = Literal["PASS", "RESTRICTED", "FAIL"]
NEW_YORK = ZoneInfo("America/New_York")


class ObservationKey(HistoricalModel):
    symbol: str
    date: date


class QualificationFinding(HistoricalModel):
    category: str = Field(pattern=r"^[a-z_]+$")
    code: str = Field(pattern=r"^[a-z0-9_]+$")
    status: Status
    role: Literal["preflight", "pilot", "candidate", "diagnostic"] | None = None
    feed: Literal["iex", "sip"] | None = None
    count: int = Field(default=1, ge=1)


class FeedCoverage(HistoricalModel):
    role: Literal["preflight", "pilot", "candidate", "diagnostic"]
    feed: Literal["iex", "sip"]
    adjustment: Literal["raw", "split", "dividend", "all"]
    start: date
    end: date
    symbols: tuple[str, ...]
    expected_pairs: int | None = Field(ge=0)
    calendar_qualified: bool
    observed_session_dates: tuple[date, ...]
    observed_rows: int = Field(ge=0)
    observed_pairs: int = Field(ge=0)
    missing_pairs: tuple[ObservationKey, ...]
    duplicate_pairs: tuple[ObservationKey, ...]
    unexpected_pairs: tuple[ObservationKey, ...]
    invalid_rows: int = Field(ge=0)
    zero_volume_rows: int = Field(ge=0)
    status: Status


class ActionInventorySummary(HistoricalModel):
    observed_records: int = Field(ge=0)
    category_counts: tuple[tuple[str, int], ...]
    unsupported_records: int = Field(ge=0)
    outside_candidate_ex_dates: int = Field(ge=0)
    malformed_records: int = Field(ge=0)
    duplicate_records: int = Field(ge=0)
    status: Status


class HistoricalQualificationReport(HistoricalModel):
    schema_version: Literal["historical-candidate-quality/v1"] = "historical-candidate-quality/v1"
    kind: Literal["historical", "synthetic"]
    candidate_manifest_sha256: str = Field(pattern=SHA_PATTERN)
    source_file_sha256: tuple[str, ...]
    feed: Literal["iex", "sip"]
    start: date
    end: date
    symbols: tuple[str, ...]
    feed_coverage: tuple[FeedCoverage, ...]
    action_inventory: ActionInventorySummary
    findings: tuple[QualificationFinding, ...]
    status: Status
    technical_status: Status
    next_phase: Literal["READY", "RESTRICTED", "BLOCKED"]


def _worst(statuses: list[Status]) -> Status:
    return max(statuses or ["PASS"], key={"PASS": 0, "RESTRICTED": 1, "FAIL": 2}.__getitem__)


def _add(
    findings: list[QualificationFinding],
    category: str,
    code: str,
    status: Status,
    record: CandidateAcquisition | None = None,
    *,
    count: int = 1,
) -> None:
    findings.append(
        QualificationFinding(
            category=category,
            code=code,
            status=status,
            count=count,
            role=None if record is None else record.role,
            feed=record.request.feed
            if record and isinstance(record.request, HistoricalBarsRequest)
            else None,
        )
    )


def _source_pages(
    candidate: HistoricalCandidate,
    record: CandidateAcquisition,
    findings: list[QualificationFinding],
) -> tuple[list[dict[str, object]], Status]:
    _, base_query = historical_query(record.request)
    token: str | None = None
    tokens: set[str] = set()
    payloads: list[dict[str, object]] = []
    statuses: list[Status] = []
    success_pages = [page for page in record.pages if page.http_status == 200]
    if len(success_pages) > record.request.max_pages:
        _add(findings, "acquisition", "acquisition_page_limit_exceeded", "FAIL", record)
        statuses.append("FAIL")
    if record.complete and (
        not success_pages or success_pages[-1].received_at != record.acquired_at
    ):
        _add(findings, "acquisition", "acquisition_completion_time_mismatch", "FAIL", record)
        statuses.append("FAIL")
    terminal_seen = False
    for page in record.pages:
        expected = dict(base_query)
        if token is not None:
            expected["page_token"] = token
        if dict(page.query) != expected:
            _add(findings, "acquisition", "acquisition_query_mismatch", "FAIL", record)
            statuses.append("FAIL")
        if terminal_seen:
            _add(findings, "acquisition", "acquisition_pagination_incomplete", "FAIL", record)
            statuses.append("FAIL")
        if page.http_status != 200:
            continue
        try:
            payload = decode_candidate_json(candidate.files[page.file_path])
            if not isinstance(payload, dict):
                raise ValueError
            if "next_page_token" not in payload:
                raise ValueError
            next_token = payload["next_page_token"]
            if next_token is not None and (
                not isinstance(next_token, str) or not next_token or len(next_token) > 4096
            ):
                raise ValueError
        except (ValueError, UnicodeError, RecursionError):
            _add(findings, "acquisition", "invalid_source_page", "FAIL", record)
            statuses.append("FAIL")
            continue
        if next_token is not None and next_token in tokens:
            _add(findings, "acquisition", "acquisition_pagination_cycle", "FAIL", record)
            statuses.append("FAIL")
        if next_token is not None:
            tokens.add(next_token)
        token = next_token
        terminal_seen = next_token is None
        payloads.append(payload)
    if record.complete and token is not None:
        _add(findings, "acquisition", "acquisition_pagination_incomplete", "FAIL", record)
        statuses.append("FAIL")
    if not record.complete:
        status: Status = "FAIL" if record.role in {"pilot", "candidate"} else "RESTRICTED"
        _add(findings, "acquisition", "acquisition_" + str(record.error_code), status, record)
        statuses.append(status)
    return payloads, _worst(statuses)


def _number(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise ValueError
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError
    return result


def _bar_coverage(
    candidate: HistoricalCandidate,
    record: CandidateAcquisition,
    payloads: list[dict[str, object]],
    initial_status: Status,
    findings: list[QualificationFinding],
) -> FeedCoverage:
    request = record.request
    assert isinstance(request, HistoricalBarsRequest)
    calendar_qualified = not (
        record.role == "diagnostic"
        and (request.start < candidate.manifest.start or request.end > candidate.manifest.end)
    )
    if not calendar_qualified:
        _add(findings, "calendar", "diagnostic_calendar_unqualified", "RESTRICTED", record)
        initial_status = _worst([initial_status, "RESTRICTED"])
    days = {
        session.date
        for session in candidate.manifest.sessions
        if request.start <= session.date <= request.end
    }
    expected = (
        {(symbol, day) for symbol in request.symbols for day in days}
        if calendar_qualified
        else set()
    )
    observed: Counter[tuple[str, date]] = Counter()
    unexpected: set[tuple[str, date]] = set()
    counts: Counter[str] = Counter()
    observed_rows = 0
    invalid_rows = 0
    zero_volume = 0
    for payload in payloads:
        bars = payload.get("bars")
        if not isinstance(bars, dict):
            counts["invalid_source_page"] += 1
            continue
        for symbol, rows in bars.items():
            if not isinstance(rows, list):
                counts["invalid_source_page"] += 1
                continue
            if symbol not in request.symbols:
                counts["unexpected_symbol"] += len(rows) or 1
            for row in rows:
                observed_rows += 1
                row_invalid = False
                if not isinstance(row, dict):
                    counts["invalid_ohlcv"] += 1
                    invalid_rows += 1
                    continue
                try:
                    stamp = datetime.fromisoformat(row["t"])
                    if stamp.utcoffset() is None:
                        raise ValueError
                    local = stamp.astimezone(NEW_YORK)
                    if local.time() != time.min:
                        raise ValueError
                    day = local.date()
                    if symbol in request.symbols:
                        if (symbol, day) in expected or (
                            not calendar_qualified and request.start <= day <= request.end
                        ):
                            observed[(symbol, day)] += 1
                        else:
                            unexpected.add((symbol, day))
                            counts["unexpected_session"] += 1
                            row_invalid = True
                except (KeyError, TypeError, ValueError):
                    counts["invalid_bar_timestamp"] += 1
                    row_invalid = True
                try:
                    opening, high, low, close, volume = (
                        _number(row[name]) for name in ("o", "h", "l", "c", "v")
                    )
                    if (
                        min(opening, high, low, close) <= 0
                        or volume < 0
                        or not low <= opening <= high
                        or not low <= close <= high
                    ):
                        raise ValueError
                    if volume != volume.to_integral_value():
                        counts["fractional_volume"] += 1
                        row_invalid = True
                    if volume == 0:
                        zero_volume += 1
                except (KeyError, TypeError, ValueError, ArithmeticError):
                    counts["invalid_ohlcv"] += 1
                    row_invalid = True
                invalid_rows += int(row_invalid)
    missing = expected - observed.keys()
    duplicates = {key for key, count in observed.items() if count > 1}
    if missing:
        counts["missing_sessions"] = len(missing)
    if duplicates:
        counts["duplicate_sessions"] = sum(observed[key] - 1 for key in duplicates)
    for code, count in sorted(counts.items()):
        failure_status: Status = (
            "RESTRICTED"
            if code == "missing_sessions" and record.role == "preflight" and not record.complete
            else "FAIL"
        )
        _add(
            findings,
            "coverage" if code.endswith("sessions") else "ohlcv",
            code,
            failure_status,
            record,
            count=count,
        )
    if zero_volume:
        _add(findings, "ohlcv", "zero_volume", "RESTRICTED", record, count=zero_volume)
    count_status: Status = "FAIL" if counts else "RESTRICTED" if zero_volume else "PASS"
    if set(counts) <= {"missing_sessions"} and record.role == "preflight" and not record.complete:
        count_status = "RESTRICTED"
    status = _worst([initial_status, count_status])
    return FeedCoverage(
        role=record.role,
        feed=request.feed,
        adjustment=request.adjustment,
        start=request.start,
        end=request.end,
        symbols=request.symbols,
        expected_pairs=len(expected) if calendar_qualified else None,
        calendar_qualified=calendar_qualified,
        observed_session_dates=tuple(sorted({day for symbol, day in observed})),
        observed_rows=observed_rows,
        observed_pairs=len(observed),
        missing_pairs=tuple(
            ObservationKey(symbol=symbol, date=day) for symbol, day in sorted(missing)
        ),
        duplicate_pairs=tuple(
            ObservationKey(symbol=symbol, date=day) for symbol, day in sorted(duplicates)
        ),
        unexpected_pairs=tuple(
            ObservationKey(symbol=symbol, date=day) for symbol, day in sorted(unexpected)
        ),
        invalid_rows=invalid_rows,
        zero_volume_rows=zero_volume,
        status=status,
    )


def _decision(
    decision: EvidenceDecision,
    category: str,
    findings: list[QualificationFinding],
) -> bool:
    if decision.status == "confirmed":
        return False
    _add(
        findings,
        category,
        category + "_" + decision.status,
        "FAIL" if decision.status == "contradictory" else "RESTRICTED",
    )
    return True


def _identity_findings(
    candidate: HistoricalCandidate,
    findings: list[QualificationFinding],
) -> bool:
    manifest = candidate.manifest
    counts: Counter[str] = Counter()
    for symbol in manifest.symbols:
        for session in manifest.sessions:
            matches = [
                mapping
                for identity in manifest.identities
                for mapping in identity.mappings
                if mapping.symbol == symbol and mapping.start <= session.date <= mapping.end
            ]
            if len(matches) != 1:
                counts["identity_missing_or_ambiguous"] += 1
                continue
            mapping = matches[0]
            if mapping.point_in_time_status == "uncertain":
                counts["identity_uncertain"] += 1
            if mapping.available_at > session.open_at:
                counts["identity_unavailable_at_historical_open"] += 1
            if manifest.kind == "historical" and mapping.availability_basis == "synthetic":
                counts["synthetic_identity_in_historical_candidate"] += 1
    for code, count in sorted(counts.items()):
        status: Status = (
            "FAIL"
            if code
            in {"identity_missing_or_ambiguous", "synthetic_identity_in_historical_candidate"}
            else "RESTRICTED"
        )
        _add(findings, "identity", code, status, count=count)
    return bool(counts)


def _actions(
    candidate: HistoricalCandidate,
    sources: list[
        tuple[CandidateAcquisition, HistoricalAcquisition, list[dict[str, object]], Status]
    ],
    findings: list[QualificationFinding],
) -> ActionInventorySummary:
    categories: Counter[str] = Counter()
    observed = unsupported = outside = malformed = duplicate = 0
    statuses: list[Status] = []
    known = {"forward_splits", "reverse_splits", "cash_dividends"}
    recognized = known | {
        "stock_dividends",
        "spin_offs",
        "mergers",
        "name_changes",
        "symbol_changes",
        "rights",
        "worthless_removals",
        "redemptions",
    }
    action_sources = 0
    identity_sets: dict[str, set[str]] = {}
    for identity in candidate.manifest.identities:
        for mapping in identity.mappings:
            identity_sets.setdefault(mapping.symbol, set()).add(identity.security_id)
    security_ids = {
        symbol: next(iter(identifiers))
        for symbol, identifiers in identity_sets.items()
        if len(identifiers) == 1
    }
    for record, projection, payloads, status in sources:
        if not isinstance(record.request, CorporateActionsRequest):
            continue
        action_sources += 1
        statuses.append(status)
        ids: set[str] = set()
        for payload in payloads:
            inventory = payload.get("corporate_actions")
            if not isinstance(inventory, dict):
                malformed += 1
                continue
            for category, rows in inventory.items():
                if not isinstance(rows, list):
                    malformed += 1
                    continue
                label = category if category in recognized else "unknown"
                categories[label] += len(rows)
                observed += len(rows)
                if category not in known:
                    unsupported += len(rows)
                for row in rows:
                    if not isinstance(row, dict):
                        malformed += 1
                        continue
                    identifier = row.get("id")
                    if isinstance(identifier, str):
                        if identifier in ids:
                            duplicate += 1
                        ids.add(identifier)
                    try:
                        ex_date = date.fromisoformat(row["ex_date"])
                        if not candidate.manifest.start <= ex_date <= candidate.manifest.end:
                            outside += 1
                    except (KeyError, TypeError, ValueError):
                        malformed += 1
        if record.request.types != "all":
            _add(findings, "actions", "filtered_action_inventory", "RESTRICTED", record)
            statuses.append("RESTRICTED")
        ambiguous_identity = any(
            len(identity_sets.get(symbol, set())) > 1 for symbol in record.request.symbols
        )
        if ambiguous_identity:
            _add(
                findings,
                "identity",
                "action_identity_requires_date_resolution",
                "RESTRICTED",
                record,
            )
            statuses.append("RESTRICTED")
        if record.complete and not ambiguous_identity:
            try:
                normalize_corporate_actions(projection, security_ids=security_ids)
            except HistoricalAcquisitionError as exc:
                _add(findings, "actions", "action_normalization_" + exc.code, "FAIL", record)
                statuses.append("FAIL")
    if not action_sources:
        _add(findings, "actions", "action_query_unavailable", "RESTRICTED")
        statuses.append("RESTRICTED")
    for count, code in (
        (unsupported, "unsupported_corporate_actions"),
        (malformed, "malformed_corporate_actions"),
        (duplicate, "duplicate_corporate_actions"),
    ):
        if count:
            _add(findings, "actions", code, "FAIL", count=count)
            statuses.append("FAIL")
    return ActionInventorySummary(
        observed_records=observed,
        category_counts=tuple(sorted(categories.items())),
        unsupported_records=unsupported,
        outside_candidate_ex_dates=outside,
        malformed_records=malformed,
        duplicate_records=duplicate,
        status=_worst(statuses),
    )


def qualify_historical_candidate(candidate: HistoricalCandidate) -> HistoricalQualificationReport:
    """Aggregate content defects and research gates without modifying private bytes."""
    manifest = candidate.manifest
    findings: list[QualificationFinding] = []
    coverage: list[FeedCoverage] = []
    technical: list[Status] = []
    sources = []
    for record, projection in zip(manifest.acquisitions, candidate.acquisitions, strict=True):
        payloads, status = _source_pages(candidate, record, findings)
        sources.append((record, projection, payloads, status))
        if isinstance(record.request, HistoricalBarsRequest):
            if record.role == "candidate" and (
                record.request.feed != manifest.feed
                or record.request.symbols != manifest.symbols
                or record.request.start != manifest.start
                or record.request.end != manifest.end
            ):
                _add(findings, "coverage", "primary_request_scope_mismatch", "FAIL", record)
                status = "FAIL"
            result = _bar_coverage(candidate, record, payloads, status, findings)
            coverage.append(result)
            if record.role in {"pilot", "candidate"}:
                technical.append(result.status)
            if record.normalization_error_code is not None:
                _add(
                    findings,
                    "ohlcv",
                    "normalization_" + record.normalization_error_code,
                    "FAIL",
                    record,
                )
                if record.role in {"pilot", "candidate"}:
                    technical.append("FAIL")
    blocked = False
    for decision, name in (
        (manifest.calendar_evidence, "calendar"),
        (manifest.action_inventory, "action_inventory"),
        (manifest.reconciliation, "reconciliation"),
    ):
        blocked |= _decision(decision, name, findings)
    for name in (
        "entitlement",
        "storage",
        "retention",
        "raw_redistribution",
        "derived_publication",
    ):
        permission = getattr(manifest.license, name)
        if permission != "confirmed":
            private_gate = name in {"entitlement", "storage", "retention"}
            _add(
                findings,
                "entitlement",
                name + "_" + permission,
                "FAIL" if private_gate and permission == "prohibited" else "RESTRICTED",
            )
            blocked |= private_gate
    blocked |= _identity_findings(candidate, findings)
    if manifest.kind == "synthetic":
        _add(findings, "scope", "synthetic_input", "RESTRICTED")
        blocked = True
    elif manifest.availability.mode == "synthetic":
        _add(findings, "availability", "synthetic_availability_in_historical_candidate", "FAIL")
        blocked = True
    elif manifest.availability.mode == "observed":
        _add(findings, "availability", "historical_first_publication_unverified", "RESTRICTED")
        blocked = True
    else:
        _add(findings, "availability", "historical_availability_reconstructed", "RESTRICTED")
    if manifest.feed == "iex":
        _add(findings, "scope", "iex_venue_limited", "RESTRICTED")
    action_summary = _actions(candidate, sources, findings)
    blocked |= action_summary.status != "PASS"
    primary = [
        item
        for item in coverage
        if item.role == "candidate"
        and item.feed == manifest.feed
        and item.adjustment == "raw"
        and item.start <= manifest.start
        and item.end >= manifest.end
        and set(item.symbols) == set(manifest.symbols)
    ]
    if not primary:
        _add(findings, "coverage", "full_primary_candidate_unavailable", "RESTRICTED")
        blocked = True
    if not technical:
        technical.append("FAIL")
        _add(findings, "coverage", "primary_bars_unavailable", "FAIL")
    findings.sort(key=lambda f: (f.category, f.code, f.role or "", f.feed or "", f.count))
    overall = _worst([f.status for f in findings])
    technical_status = _worst(technical)
    next_phase: Literal["READY", "RESTRICTED", "BLOCKED"] = (
        "BLOCKED"
        if blocked or overall == "FAIL"
        else "RESTRICTED"
        if overall == "RESTRICTED"
        else "READY"
    )
    return HistoricalQualificationReport(
        kind=manifest.kind,
        candidate_manifest_sha256=candidate.manifest_sha256,
        source_file_sha256=tuple(sorted({file.sha256 for file in manifest.files})),
        feed=manifest.feed,
        start=manifest.start,
        end=manifest.end,
        symbols=manifest.symbols,
        feed_coverage=tuple(
            sorted(
                coverage,
                key=lambda item: (
                    item.role,
                    item.feed,
                    item.adjustment,
                    item.start,
                    item.end,
                    item.symbols,
                ),
            )
        ),
        action_inventory=action_summary,
        findings=tuple(findings),
        status=overall,
        technical_status=technical_status,
        next_phase=next_phase,
    )


def qualification_report_bytes(report: HistoricalQualificationReport) -> bytes:
    """Canonical public aggregate report; source prices, rates and opaque IDs are absent."""
    return canonical_json(report.model_dump(mode="json"))

"""Local, integrity-checked, candidate-bound replay of frozen adverse AI evidence.

The v1 policy uses the existing strict parser and deterministic scorer with only
negative events. Raw scores, multipliers and favorable assertions have no authority.
Missing/invalid analysis is neutral; altered bytes or invalid manifests fail explicitly.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, Field, ValidationError, model_validator

from packages.ai.dedupe import normalize_article, normalize_text, normalize_url
from packages.ai.models import (
    AI_SCHEMA_VERSION,
    AICitation,
    AIEvent,
    AIProviderFailure,
    AITradeResearchOutput,
    NormalizedNewsArticle,
    ProviderNewsArticle,
)
from packages.ai.parser import parse_ai_trade_research_or_fallback
from packages.ai.scoring import apply_deterministic_ai_policy
from packages.research.models import ResearchDecision, ResearchModel, ResearchSignalSet


class FrozenAIIntegrityError(ValueError):
    """The frozen bundle's declared structure or bytes cannot be verified."""


class FrozenAIFile(ResearchModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class FrozenAIVersion(ResearchModel):
    """A versioned, hashed local provenance descriptor, not necessarily model weights."""

    version: str = Field(min_length=1)
    file: FrozenAIFile


class FrozenAIArticle(ResearchModel):
    article_id: str = Field(min_length=1)
    observed_available_at: AwareDatetime
    file: FrozenAIFile


class FrozenCitationBinding(ResearchModel):
    citation_id: str = Field(min_length=1)
    article_id: str = Field(min_length=1)


class FrozenAIRecord(ResearchModel):
    record_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]*$")
    decision_at: AwareDatetime
    analysis_at: AwareDatetime
    output_available_at: AwareDatetime
    output: FrozenAIFile | None = None
    citation_bindings: tuple[FrozenCitationBinding, ...] = ()
    provider_failure: AIProviderFailure | None = None

    @model_validator(mode="after")
    def temporal_contract(self) -> Self:
        if self.analysis_at > self.output_available_at:
            raise ValueError("analysis_must_precede_output_availability")
        if self.provider_failure is not None and self.provider_failure.symbol != self.symbol:
            raise ValueError("provider_failure_symbol_mismatch")
        return self


class FrozenAIManifest(ResearchModel):
    schema_version: Literal["frozen-ai-evidence/v1"]
    evidence_id: str = Field(min_length=1)
    kind: Literal["synthetic", "historical"]
    source: str = Field(min_length=1)
    license: str = Field(min_length=1)
    frozen_at: AwareDatetime
    model: FrozenAIVersion
    prompt: FrozenAIVersion
    output_schema: FrozenAIVersion
    scoring_policy_version: Literal["research-ai-negative-only/v1"]
    hard_block_confidence_min: float = Field(default=0.7, ge=0.7, le=0.7)
    articles: tuple[FrozenAIArticle, ...] = ()
    records: tuple[FrozenAIRecord, ...] = ()

    @model_validator(mode="after")
    def frozen_availability(self) -> Self:
        if any(article.observed_available_at > self.frozen_at for article in self.articles):
            raise ValueError("article_availability_after_freeze")
        if any(record.output_available_at > self.frozen_at for record in self.records):
            raise ValueError("output_availability_after_freeze")
        return self


class LoadedAIArticle(ResearchModel):
    metadata: FrozenAIArticle
    article: NormalizedNewsArticle | None = None
    issue: str | None = None


class LoadedAIRecord(ResearchModel):
    metadata: FrozenAIRecord
    raw_output: str | None = None
    issue: str | None = None


class FrozenAIEvidence(ResearchModel):
    manifest: FrozenAIManifest | None = None
    manifest_sha256: str | None = None
    articles: tuple[LoadedAIArticle, ...] = ()
    records: tuple[LoadedAIRecord, ...] = ()
    warnings: tuple[str, ...] = ()


class AIReplayDiagnostic(ResearchModel):
    decision_id: str
    symbol: str
    cutoff: datetime
    original_quantity: int
    resulting_quantity: int
    reason: str
    fallback: bool
    output_valid: bool = False
    record_id: str | None = None
    output_sha256: str | None = None
    ai_score: int = 50
    size_multiplier: float = 1.0
    article_count: int = 0
    adverse_event_count: int = 0


class AIReplayResult(ResearchModel):
    signals: ResearchSignalSet
    diagnostics: tuple[AIReplayDiagnostic, ...]
    warnings: tuple[str, ...] = ()


def _read_verified(root: Path, file: FrozenAIFile) -> bytes | None:
    relative = Path(file.path)
    if relative.is_absolute() or ".." in relative.parts:
        raise FrozenAIIntegrityError(f"unsafe_local_path:{file.path}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise FrozenAIIntegrityError(f"unsafe_local_path:{file.path}")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise FrozenAIIntegrityError(f"unreadable_local_file:{file.path}") from exc
    if len(raw) != file.size_bytes or hashlib.sha256(raw).hexdigest() != file.sha256:
        raise FrozenAIIntegrityError(f"file_integrity_mismatch:{file.path}")
    return raw


def load_frozen_ai_evidence(path: Path) -> FrozenAIEvidence:
    """Verify local bytes only. A missing corpus is an explicitly neutral input.

    The manifest freezes provenance descriptors, raw provider article JSON, raw
    structured output bytes and availability metadata. No acquisition is attempted.
    """
    try:
        raw_manifest = path.read_bytes()
    except FileNotFoundError:
        return FrozenAIEvidence(warnings=("missing_evidence",))
    except OSError as exc:
        raise FrozenAIIntegrityError("unreadable_manifest") from exc
    try:
        manifest = FrozenAIManifest.model_validate_json(raw_manifest)
    except (ValueError, ValidationError) as exc:
        raise FrozenAIIntegrityError("invalid_manifest") from exc
    root = path.parent.resolve()
    for descriptor in (manifest.model, manifest.prompt, manifest.output_schema):
        if _read_verified(root, descriptor.file) is None:
            raise FrozenAIIntegrityError(f"missing_provenance_file:{descriptor.file.path}")

    warnings: list[str] = []
    article_metadata: dict[str, FrozenAIArticle] = {}
    articles: list[LoadedAIArticle] = []
    for metadata in sorted(manifest.articles, key=lambda article: article.article_id):
        if metadata.article_id in article_metadata:
            if article_metadata[metadata.article_id] != metadata:
                raise FrozenAIIntegrityError("conflicting_article_id")
            warnings.append("duplicate_article")
            continue
        article_metadata[metadata.article_id] = metadata
        raw_article = _read_verified(root, metadata.file)
        if raw_article is None:
            articles.append(LoadedAIArticle(metadata=metadata, issue="missing_article"))
            continue
        try:
            provider_article = ProviderNewsArticle.model_validate_json(raw_article)
            article = normalize_article(provider_article).model_copy(
                update={"raw_payload_hash": metadata.file.sha256}
            )
        except (ValueError, ValidationError):
            articles.append(LoadedAIArticle(metadata=metadata, issue="invalid_article"))
            continue
        if article.published_at > metadata.observed_available_at:
            articles.append(
                LoadedAIArticle(metadata=metadata, issue="invalid_article_availability")
            )
            continue
        articles.append(LoadedAIArticle(metadata=metadata, article=article))

    record_metadata: dict[str, FrozenAIRecord] = {}
    records: list[LoadedAIRecord] = []
    for record in sorted(manifest.records, key=lambda record: record.record_id):
        if record.record_id in record_metadata:
            if record_metadata[record.record_id] != record:
                raise FrozenAIIntegrityError("conflicting_record_id")
            warnings.append("duplicate_record")
            continue
        record_metadata[record.record_id] = record
        raw_output = _read_verified(root, record.output) if record.output is not None else None
        if raw_output is None:
            records.append(LoadedAIRecord(metadata=record, issue="missing_output"))
            continue
        try:
            decoded = raw_output.decode("utf-8")
        except UnicodeDecodeError:
            records.append(LoadedAIRecord(metadata=record, issue="invalid_output_encoding"))
            continue
        records.append(LoadedAIRecord(metadata=record, raw_output=decoded))
    return FrozenAIEvidence(
        manifest=manifest,
        manifest_sha256=hashlib.sha256(raw_manifest).hexdigest(),
        articles=tuple(articles),
        records=tuple(records),
        warnings=tuple(sorted(set(warnings))),
    )


def _neutral(
    decision: ResearchDecision,
    cutoff: datetime,
    reason: str,
    *,
    record: FrozenAIRecord | None = None,
    fallback: bool = True,
    output_valid: bool = False,
) -> tuple[ResearchDecision, AIReplayDiagnostic]:
    return decision, AIReplayDiagnostic(
        decision_id=decision.decision_id,
        symbol=decision.symbol,
        cutoff=cutoff,
        original_quantity=decision.quantity,
        resulting_quantity=decision.quantity,
        reason=reason,
        fallback=fallback,
        output_valid=output_valid,
        record_id=record.record_id if record else None,
        output_sha256=record.output.sha256 if record and record.output else None,
    )


def _citation_matches(citation: AICitation, article: NormalizedNewsArticle) -> bool:
    return (
        citation.raw_payload_hash == article.raw_payload_hash
        and normalize_url(citation.canonical_url) == article.normalized_canonical_url
        and normalize_text(citation.title) == article.normalized_title
        and normalize_text(citation.source) == article.normalized_source
        and citation.provider == article.provider
        and citation.published_at == article.published_at
    )


def _bound_adverse_events(
    output: AITradeResearchOutput,
    record: FrozenAIRecord,
    evidence: FrozenAIEvidence,
    cutoff: datetime,
) -> tuple[tuple[AIEvent, ...], int, str | None]:
    articles = {article.metadata.article_id: article for article in evidence.articles}
    bindings = {binding.citation_id: binding.article_id for binding in record.citation_bindings}
    if len(bindings) != len(record.citation_bindings):
        return (), 0, "duplicate_citation_binding"
    citation_keys: dict[str, str] = {}
    for citation in output.citations:
        if citation.published_at > cutoff:
            return (), 0, "future_citation"
        bound = articles.get(bindings.get(citation.citation_id, ""))
        if bound is None:
            return (), 0, "missing_citation_binding"
        if bound.issue is not None:
            return (), 0, bound.issue
        article = bound.article
        assert article is not None
        if article.published_at > cutoff or bound.metadata.observed_available_at > cutoff:
            return (), 0, "article_not_available"
        if bound.metadata.observed_available_at > record.analysis_at:
            return (), 0, "article_not_available_at_analysis"
        if article.symbol != record.symbol or not _citation_matches(citation, article):
            return (), 0, "citation_article_mismatch"
        citation_keys[citation.citation_id] = article.dedupe_key

    # Bind every assertion before filtering direction: an output that consulted
    # future/unbound material cannot supply a clean as-of adverse analysis.
    seen_events: set[tuple[str, str, tuple[str, ...], datetime]] = set()
    negative: list[AIEvent] = []
    for event in output.events:
        if event.published_at > cutoff:
            return (), 0, "future_event"
        if event.published_at > record.analysis_at:
            return (), 0, "event_after_analysis"
        if event.direction != "negative":
            continue
        keys = tuple(sorted({citation_keys[citation_id] for citation_id in event.citation_ids}))
        identity = (event.event_type, event.direction, keys, event.published_at)
        if identity not in seen_events:
            seen_events.add(identity)
            negative.append(event)
    return tuple(negative), len(set(citation_keys.values())), None


def _replay_candidate(
    decision: ResearchDecision,
    evidence: FrozenAIEvidence,
    decision_cutoff: datetime,
    neutral_control: bool,
) -> tuple[ResearchDecision, AIReplayDiagnostic]:
    cutoff = min(decision.decision_at, decision_cutoff)
    if not decision.accepted:
        return _neutral(decision, cutoff, "deterministic_rejection_preserved", fallback=False)
    if neutral_control:
        return _neutral(decision, cutoff, "neutral_control", fallback=False)
    if decision.action != "buy":
        return _neutral(decision, cutoff, "exit_not_overlaid", fallback=False)
    if decision.decision_at > decision_cutoff:
        return _neutral(decision, cutoff, "decision_after_cutoff")
    manifest = evidence.manifest
    if manifest is None:
        return _neutral(decision, cutoff, "missing_evidence")
    candidates = tuple(
        record
        for record in evidence.records
        if record.metadata.decision_id == decision.decision_id
        and record.metadata.symbol == decision.symbol
        and record.metadata.decision_at == decision.decision_at
    )
    if not candidates:
        return _neutral(decision, cutoff, "no_candidate_evidence")
    available = tuple(
        record
        for record in candidates
        if record.metadata.analysis_at <= cutoff and record.metadata.output_available_at <= cutoff
    )
    if not available:
        return _neutral(decision, cutoff, "no_asof_evidence")
    loaded = max(
        available,
        key=lambda record: (
            record.metadata.output_available_at,
            record.metadata.analysis_at,
            record.metadata.record_id,
        ),
    )
    record = loaded.metadata
    if record.provider_failure is not None:
        return _neutral(decision, cutoff, "provider_failure", record=record)
    if loaded.issue is not None:
        return _neutral(decision, cutoff, loaded.issue, record=record)
    assert loaded.raw_output is not None
    output = parse_ai_trade_research_or_fallback(
        loaded.raw_output,
        symbol=decision.symbol,
        analysis_at=record.analysis_at,
        prompt_version=manifest.prompt.version,
        schema_version=manifest.output_schema.version,
        model_version=manifest.model.version,
    )
    if output.fallback:
        return _neutral(decision, cutoff, output.fallback_reason, record=record)
    if (
        output.symbol != record.symbol
        or output.analysis_at != record.analysis_at
        or output.model_version != manifest.model.version
        or output.prompt_version != manifest.prompt.version
        or output.schema_version != manifest.output_schema.version
        or output.schema_version != AI_SCHEMA_VERSION
    ):
        return _neutral(decision, cutoff, "output_metadata_mismatch", record=record)
    negative, article_count, issue = _bound_adverse_events(output, record, evidence, cutoff)
    if issue:
        return _neutral(decision, cutoff, issue, record=record)
    if not negative:
        return _neutral(
            decision, cutoff, "no_adverse_events", record=record, fallback=False, output_valid=True
        )
    # Only verified negative events enter the existing policy. Neither the raw
    # multiplier/block flag/score nor a mixed-news label carries independent authority.
    policy_input = output.model_copy(
        update={
            "events": negative,
            "hard_block": False,
            "hard_block_reason": None,
            "size_multiplier": 1.0,
            "ai_score": 50,
            "news_state": "found",
        }
    )
    policy = apply_deterministic_ai_policy(
        policy_input, as_of=cutoff, hard_block_confidence_min=manifest.hard_block_confidence_min
    )
    numerator, denominator = policy.size_multiplier.as_integer_ratio()
    quantity = min(decision.quantity, decision.quantity * numerator // denominator)
    changed = quantity != decision.quantity
    reason = "adverse_neutral"
    result = decision
    if changed:
        reason = "adverse_block" if quantity == 0 else "adverse_reduction"
        result = decision.model_copy(
            update={
                "accepted": quantity > 0,
                "quantity": quantity,
                "reason_codes": (*decision.reason_codes, f"research_ai_{reason}"),
            }
        )
    return result, AIReplayDiagnostic(
        decision_id=decision.decision_id,
        symbol=decision.symbol,
        cutoff=cutoff,
        original_quantity=decision.quantity,
        resulting_quantity=quantity,
        reason=reason,
        fallback=False,
        output_valid=True,
        record_id=record.record_id,
        output_sha256=record.output.sha256 if record.output else None,
        ai_score=policy.ai_score,
        size_multiplier=policy.size_multiplier,
        article_count=article_count,
        adverse_event_count=len(negative),
    )


def replay_ai_evidence(
    signals: ResearchSignalSet,
    evidence: FrozenAIEvidence,
    decision_cutoff: datetime,
    *,
    neutral_control: bool = False,
) -> AIReplayResult:
    """Replay once per input candidate, retaining order and exact neutral decisions.

    Each candidate uses min(global cutoff, its own timestamp). The latest eligible
    frozen output wins once; malformed later evidence never selects an older winner.
    Diagnostic rows retain rejected candidates and all fallback reasons.
    """
    if decision_cutoff.tzinfo is None:
        raise ValueError("decision_cutoff_requires_offset")
    decisions: list[ResearchDecision] = []
    diagnostics: list[AIReplayDiagnostic] = []
    for decision in signals.decisions:
        replayed, diagnostic = _replay_candidate(
            decision, evidence, decision_cutoff, neutral_control
        )
        decisions.append(replayed)
        diagnostics.append(diagnostic)
    return AIReplayResult(
        signals=ResearchSignalSet(decisions=tuple(decisions)),
        diagnostics=tuple(diagnostics),
        warnings=evidence.warnings,
    )


def apply_research_ai_overlay(
    signals: ResearchSignalSet,
    evidence: FrozenAIEvidence,
    decision_cutoff: datetime,
) -> ResearchSignalSet:
    return replay_ai_evidence(signals, evidence, decision_cutoff).signals

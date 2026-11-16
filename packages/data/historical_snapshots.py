"""Read-only v2 snapshots and cutoff-specific feature views. No acquisition fallback."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import (
    Context,
    DecimalException,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    localcontext,
)
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from packages.data.corporate_actions import CorporateAction, SplitAction, validate_actions
from packages.data.historical_models import (
    HistoricalBar,
    HistoricalSnapshotFile,
    HistoricalSnapshotManifest,
    SymbolMapping,
    utc,
)
from packages.data.quality import SnapshotError


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _decode(data: bytes) -> object:
    return json.loads(data, object_pairs_hook=_no_duplicate_keys)


def _file(root: Path, entry: HistoricalSnapshotFile) -> bytes:
    relative = Path(entry.path)
    if relative.is_absolute() or ".." in relative.parts:
        raise SnapshotError("unsafe_path", entry.path)
    path = root / relative
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise SnapshotError("unsafe_or_missing_file", entry.path)
    data = path.read_bytes()
    if len(data) != entry.size_bytes:
        raise SnapshotError("size_mismatch", entry.path)
    if hashlib.sha256(data).hexdigest() != entry.sha256:
        raise SnapshotError("hash_mismatch", entry.path)
    return data


@dataclass(frozen=True)
class FeaturePriceView:
    cutoff: datetime
    basis: str
    bars: tuple[HistoricalBar, ...]
    action_ids: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalSnapshot:
    manifest: HistoricalSnapshotManifest
    manifest_sha256: str
    raw_bars: tuple[HistoricalBar, ...]
    actions: tuple[CorporateAction, ...]
    warnings: tuple[str, ...]

    def mapping_for(self, security_id: str, session: date) -> SymbolMapping:
        matches = [
            mapping
            for security in self.manifest.securities
            if security.security_id == security_id
            for mapping in security.mappings
            if mapping.start <= session <= mapping.end
        ]
        if len(matches) != 1:
            raise SnapshotError("unknown_or_ambiguous_identity", security_id)
        return matches[0]

    def feature_view(self, cutoff: datetime, *, basis: str) -> FeaturePriceView:
        cutoff = utc(cutoff)
        corrected = self.manifest.revision.correction_observed_at
        if corrected is not None and corrected > cutoff:
            raise ValueError("revision_not_available_at_cutoff")
        if basis not in {"raw", "split_asof"}:
            raise ValueError("unsupported_feature_basis")
        sessions = {s.date: s for s in self.manifest.sessions}
        splits = (
            tuple(
                action
                for action in self.actions
                if isinstance(action, SplitAction) and sessions[action.ex_date].open_at <= cutoff
            )
            if basis == "split_asof"
            else ()
        )
        if any(a.available_at > cutoff for a in splits):
            raise ValueError("action_unavailable_for_feature_view")
        if any(self.mapping_for(a.security_id, a.ex_date).available_at > cutoff for a in splits):
            raise SnapshotError("action_identity_unavailable")
        rows = []
        try:
            with localcontext(
                Context(prec=50, traps=[Inexact, InvalidOperation, DivisionByZero, Overflow])
            ):
                for bar in self.raw_bars:
                    if (
                        bar.available_at > cutoff
                        or sessions[bar.date].close_at > cutoff
                        or self.mapping_for(bar.security_id, bar.date).available_at > cutoff
                    ):
                        continue
                    prices = {name: getattr(bar, name) for name in ("open", "high", "low", "close")}
                    volume = bar.volume
                    for action in splits:
                        if action.security_id == bar.security_id and bar.date < action.ex_date:
                            prices = {
                                k: v * action.denominator / action.numerator
                                for k, v in prices.items()
                            }
                            volume = volume * action.numerator / action.denominator
                    rows.append(bar.model_copy(update={**prices, "volume": volume}))
        except DecimalException as exc:
            raise ValueError("inexact_feature_adjustment") from exc
        return FeaturePriceView(cutoff, basis, tuple(rows), tuple(a.action_id for a in splits))


def load_historical_snapshot(
    manifest_path: Path, *, expected_sha256: str | None = None
) -> HistoricalSnapshot:
    """Load v2 only. A caller can pin the root manifest hash to detect revisions.

    A complete action inventory is an explicit source attestation, not inferred
    from price jumps. Hash verification proves frozen bytes, not vendor truth.
    """
    try:
        if any(p.is_symlink() for p in (manifest_path, *manifest_path.parents)):
            raise SnapshotError("unsafe_manifest_path")
        raw = manifest_path.read_bytes()
    except OSError as exc:
        raise SnapshotError("missing_manifest") from exc
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise SnapshotError("manifest_hash_mismatch")
    try:
        manifest = HistoricalSnapshotManifest.model_validate(_decode(raw))
    except (ValidationError, ValueError, UnicodeError) as exc:
        raise SnapshotError("invalid_historical_manifest", "schema or provenance") from exc
    if manifest.kind == "historical" and any(
        getattr(manifest.license, name) != "confirmed"
        for name in ("entitlement", "storage", "retention")
    ):
        raise SnapshotError("unconfirmed_data_rights")
    if any(a.mocked != (manifest.kind == "synthetic") for a in manifest.acquisitions):
        raise SnapshotError("acquisition_kind_mismatch")
    if any((a.provider == "synthetic") != a.mocked for a in manifest.acquisitions):
        raise SnapshotError("acquisition_provider_mismatch")
    receipts = {a.acquisition_id: a for a in manifest.acquisitions}
    rows: list[HistoricalBar] = []
    actions: tuple[CorporateAction, ...] = ()
    try:
        for entry in manifest.files:
            receipt = receipts.get(entry.acquisition_id)
            endpoint = "/v2/stocks/bars" if entry.role == "raw_bars" else "/v1/corporate-actions"
            if receipt is None or receipt.endpoint != endpoint:
                raise SnapshotError("file_acquisition_mismatch")
            content = _decode(_file(manifest_path.parent, entry))
            if entry.role == "raw_bars":
                rows = TypeAdapter(list[HistoricalBar]).validate_python(content)
                if any(b.acquisition_id != entry.acquisition_id for b in rows):
                    raise SnapshotError("bar_acquisition_mismatch")
            else:
                actions = validate_actions(
                    TypeAdapter(tuple[CorporateAction, ...]).validate_python(content)
                )
                if any(a.available_at > receipt.acquired_at for a in actions):
                    raise SnapshotError("action_availability_after_acquisition")
                if any(
                    a.availability_basis == "observed"
                    and a.available_at < receipt.request_started_at
                    for a in actions
                ):
                    raise SnapshotError("observed_action_precedes_acquisition")
    except (ValidationError, ValueError, UnicodeError, OSError) as exc:
        if isinstance(exc, SnapshotError):
            raise
        raise SnapshotError("invalid_historical_records", "schema or action evidence") from exc
    snapshot = HistoricalSnapshot(
        manifest, digest, tuple(sorted(rows, key=lambda b: (b.security_id, b.date))), actions, ()
    )
    warnings = _validate_contents(snapshot)
    return HistoricalSnapshot(manifest, digest, snapshot.raw_bars, actions, warnings)


def _validate_contents(snapshot: HistoricalSnapshot) -> tuple[str, ...]:
    manifest = snapshot.manifest
    sessions = {s.date: s for s in manifest.sessions}
    receipts = {a.acquisition_id: a for a in manifest.acquisitions}
    securities = {s.security_id for s in manifest.securities}
    warnings = [f"dataset_kind:{manifest.kind}", "v2_raw_execution_explicit_actions"]
    identities: dict[tuple[str, date], str] = {}
    for security in manifest.securities:
        for session in manifest.sessions:
            mapping = snapshot.mapping_for(security.security_id, session.date)
            key = (mapping.symbol, session.date)
            if key in identities:
                raise SnapshotError("ambiguous_symbol_identity", mapping.symbol)
            identities[key] = security.security_id
            if mapping.available_at > manifest.frozen_at:
                raise SnapshotError("mapping_after_freeze")
            if manifest.kind == "historical" and mapping.availability_basis == "synthetic":
                raise SnapshotError("synthetic_identity_in_historical_input")
            if mapping.point_in_time_status == "uncertain":
                if manifest.identity_policy == "require_confirmed":
                    raise SnapshotError("uncertain_identity", security.security_id)
                warnings.append(f"uncertain_identity:{security.security_id}")
    observed: set[tuple[str, date]] = set()
    availability_basis = {
        "observed": "observed",
        "reconstructed": "assumed",
        "synthetic": "synthetic",
    }[manifest.historical_availability.mode]
    for bar in snapshot.raw_bars:
        if bar.availability_basis != availability_basis:
            raise SnapshotError("availability_basis_mismatch")
        key = (bar.security_id, bar.date)
        if key in observed:
            raise SnapshotError("duplicate_session", f"{bar.security_id}:{bar.date}")
        observed.add(key)
        market_session = sessions.get(bar.date)
        if market_session is None or bar.security_id not in securities:
            raise SnapshotError("unexpected_session_or_security")
        mapping = snapshot.mapping_for(bar.security_id, bar.date)
        if mapping.symbol != bar.symbol:
            raise SnapshotError("symbol_mapping_mismatch")
        receipt = receipts[bar.acquisition_id]
        if bar.availability_basis == "observed" and bar.available_at < receipt.request_started_at:
            raise SnapshotError("observed_availability_precedes_acquisition")
        if bar.symbol not in receipt.symbols or not receipt.start <= bar.date <= receipt.end:
            raise SnapshotError("observation_outside_query")
        if not market_session.close_at <= bar.available_at <= receipt.acquired_at:
            raise SnapshotError("invalid_historical_availability")
        if bar.volume != bar.volume.to_integral_value():
            raise SnapshotError("fractional_raw_volume")
        if manifest.kind == "historical" and bar.availability_basis == "synthetic":
            raise SnapshotError("synthetic_availability_in_historical_input")
    missing = {(sid, day) for sid in securities for day in sessions} - observed
    exclusions = {(e.security_id, e.date) for e in manifest.exclusions}
    if missing != exclusions or (missing and manifest.missing_session_policy == "reject"):
        raise SnapshotError("undeclared_or_rejected_missing_session")
    warnings.extend(f"missing_session:{sid}:{day}" for sid, day in sorted(missing))
    if tuple(sorted(a.action_id for a in snapshot.actions)) != manifest.expected_action_ids:
        raise SnapshotError("action_inventory_mismatch")
    action_receipt = receipts[
        next(f.acquisition_id for f in manifest.files if f.role == "corporate_actions")
    ]
    for action in snapshot.actions:
        if action.availability_basis != availability_basis:
            raise SnapshotError("availability_basis_mismatch")
        if action.ex_date not in sessions or action.security_id not in securities:
            raise SnapshotError("action_outside_coverage_or_identity")
        if snapshot.mapping_for(action.security_id, action.ex_date).symbol != action.symbol:
            raise SnapshotError("action_symbol_mapping_mismatch")
        if action.symbol not in action_receipt.symbols:
            raise SnapshotError("action_outside_query")
        if manifest.kind == "historical" and action.availability_basis == "synthetic":
            raise SnapshotError("synthetic_action_in_historical_input")
    return tuple(sorted(set(warnings)))

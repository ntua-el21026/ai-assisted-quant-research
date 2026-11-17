"""Frozen opt-in R4-B plans and bounded, nonexecuting credential-file parsing.

Loading a plan is offline and never discovers credentials. The credential helper
reads only its explicit argument; it does not source shell code or inspect ambient
environment variables. Callers own authorization for any later provider operation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, ValidationError, field_validator, model_validator

from packages.data.alpaca_historical import CorporateActionsRequest, HistoricalBarsRequest
from packages.data.historical_models import SHA_PATTERN, HistoricalModel
from packages.data.research_calendar import ResearchCalendar, load_research_calendar

_MAX_PLAN_BYTES = 128 * 1024
_MAX_CREDENTIAL_BYTES = 16 * 1024
_CREDENTIAL_NAMES = {"APCA_API_KEY_ID", "APCA_API_SECRET_KEY"}
_CREDENTIAL_TOKEN = re.compile(r"[A-Za-z0-9._+/=\-]{1,4096}")


class AcquisitionBudget(HistoricalModel):
    max_attempts: int = Field(strict=True, ge=1, le=100)
    max_received_body_bytes: int = Field(strict=True, ge=1, le=250 * 1024 * 1024)
    max_local_bytes: int = Field(strict=True, ge=1, le=1024**3)
    max_elapsed_seconds: float = Field(strict=True, gt=0, le=900)
    min_interval_seconds: float = Field(strict=True, ge=0.35, le=60)
    timeout_seconds: float = Field(strict=True, gt=0, le=120)


class AcquisitionStage(HistoricalModel):
    acquisition_id: str = Field(pattern=r"^[a-z][a-z0-9\-]{0,79}$")
    role: Literal["preflight", "pilot", "candidate", "diagnostic"]
    request_kind: Literal["bars", "actions"]
    request: HistoricalBarsRequest | CorporateActionsRequest

    @model_validator(mode="after")
    def request_consistency(self) -> Self:
        if isinstance(self.request, HistoricalBarsRequest):
            if (
                self.request_kind != "bars"
                or self.request.feed != "iex"
                or self.request.asof != "-"
            ):
                raise ValueError("stage_requires_explicit_iex_raw_symbol_mapping")
            if self.role != "diagnostic" and self.request.adjustment != "raw":
                raise ValueError("primary_raw_prices_required")
        elif self.request_kind != "actions" or self.request.types != "all":
            raise ValueError("all_action_types_required")
        return self


class AcquisitionPlan(HistoricalModel):
    schema_version: Literal["historical-acquisition-plan/v1"]
    checkpoint: Literal["R4-B"]
    plan_id: str = Field(min_length=1)
    provider: Literal["alpaca"]
    feed: Literal["iex"]
    account_plan: Literal["Basic"]
    account_type: Literal["paper_only"]
    symbols: tuple[str, ...] = Field(min_length=1)
    candidate_start: date
    candidate_end: date
    selection_rationale: str = Field(min_length=1)
    rights_statement: str = Field(min_length=1)
    entitlement_sources: tuple[str, ...] = Field(min_length=1)
    budget: AcquisitionBudget
    calendar_path: str = Field(min_length=1)
    calendar_sha256: str = Field(pattern=SHA_PATTERN)
    stages: tuple[AcquisitionStage, ...] = Field(min_length=1)

    @field_validator("calendar_path")
    @classmethod
    def safe_calendar_path(cls, value: str) -> str:
        path = Path(value)
        if (
            path.is_absolute()
            or "\\" in value
            or "\x00" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
        ):
            raise ValueError("unsafe_calendar_path")
        return value

    @model_validator(mode="after")
    def stage_order_and_scope(self) -> Self:
        if self.candidate_start > self.candidate_end:
            raise ValueError("invalid_candidate_interval")
        if self.symbols != tuple(sorted(set(self.symbols))) or any(
            re.fullmatch(r"[A-Z][A-Z0-9.-]{0,19}", symbol) is None for symbol in self.symbols
        ):
            raise ValueError("invalid_plan_symbols")
        if len({stage.acquisition_id for stage in self.stages}) != len(self.stages):
            raise ValueError("duplicate_stage_identity")
        order = {"preflight": 0, "pilot": 1, "candidate": 2, "diagnostic": 3}
        ranks = [order[stage.role] for stage in self.stages]
        if ranks != sorted(ranks):
            raise ValueError("invalid_stage_order")
        for role in ("preflight", "pilot", "candidate"):
            stages = [stage for stage in self.stages if stage.role == role]
            if [stage.request_kind for stage in stages] != ["bars", "actions"]:
                raise ValueError("primary_stages_require_bars_then_actions")
            for stage in stages:
                if stage.request.symbols != self.symbols:
                    raise ValueError("primary_stage_universe_mismatch")
                if isinstance(stage.request, HistoricalBarsRequest):
                    if not (
                        self.candidate_start
                        <= stage.request.start
                        <= stage.request.end
                        <= self.candidate_end
                    ):
                        raise ValueError("primary_stage_outside_candidate")
                    if role == "candidate" and (
                        stage.request.start != self.candidate_start
                        or stage.request.end != self.candidate_end
                    ):
                        raise ValueError("candidate_stage_interval_mismatch")
        return self


@dataclass(frozen=True)
class RegisteredAcquisitionPlan:
    plan: AcquisitionPlan
    calendar: ResearchCalendar
    sha256: str
    raw_bytes: bytes


@dataclass(frozen=True)
class AlpacaCredentials:
    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)


def _bounded_regular_file(path: Path, maximum: int) -> bytes:
    if any(entry.is_symlink() for entry in (path, *path.parents)):
        raise ValueError("unsafe_file")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as stream:
        details = os.fstat(stream.fileno())
        if not stat.S_ISREG(details.st_mode) or details.st_size > maximum:
            raise ValueError("invalid_file")
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("file_limit")
    return raw


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def load_acquisition_plan(path: Path) -> RegisteredAcquisitionPlan:
    """Validate the explicit checkpoint scope and hash-pin its local official calendar."""
    try:
        raw = _bounded_regular_file(path, _MAX_PLAN_BYTES)
        payload = json.loads(raw, object_pairs_hook=_unique_keys)
        plan = AcquisitionPlan.model_validate(payload)
        calendar_path = path.parent / plan.calendar_path
        if any(entry.is_symlink() for entry in (calendar_path, *calendar_path.parents)):
            raise ValueError("unsafe_calendar")
        calendar = load_research_calendar(calendar_path, expected_sha256=plan.calendar_sha256)
        if not (
            date(2020, 1, 1) <= plan.candidate_start <= plan.candidate_end <= date(2025, 12, 31)
        ):
            raise ValueError("candidate_outside_qualified_calendar")
        return RegisteredAcquisitionPlan(plan, calendar, hashlib.sha256(raw).hexdigest(), raw)
    except (OSError, ValueError, ValidationError, UnicodeError, RecursionError):
        raise ValueError("invalid_acquisition_plan") from None


def load_alpaca_credentials(path: Path) -> AlpacaCredentials:
    """Parse two literal credential assignments without shell evaluation or writes.

    The supported subset accepts optional ``export`` and balanced single/double
    quotes around a nonempty ASCII token. Shell operators, substitution, escapes,
    inline comments, duplicate/unknown variables and oversized inputs are rejected.
    Secret values and filenames never appear in raised error messages or repr.
    """
    try:
        raw = _bounded_regular_file(path, _MAX_CREDENTIAL_BYTES)
        values: dict[str, str] = {}
        for line in raw.decode("utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            if text.startswith("export ") or text.startswith("export\t"):
                text = text[6:].lstrip()
            match = re.fullmatch(r"([A-Z_][A-Z0-9_]*)\s*=\s*(.*)", text)
            if match is None:
                raise ValueError
            name, value = match.groups()
            if name not in _CREDENTIAL_NAMES or name in values:
                raise ValueError
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError
                value = value[1:-1]
            if _CREDENTIAL_TOKEN.fullmatch(value) is None:
                raise ValueError
            values[name] = value
        if set(values) != _CREDENTIAL_NAMES:
            raise ValueError
        return AlpacaCredentials(values["APCA_API_KEY_ID"], values["APCA_API_SECRET_KEY"])
    except (OSError, ValueError, UnicodeError):
        raise ValueError("credentials_unavailable") from None

"""Plain serializable contracts for optional local research orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ResearchWorkflowRequest:
    experiment_id: str
    config_path: str
    dataset_manifest_path: str
    state_dir: str
    mode: Literal["run", "evaluate"] = "evaluate"
    include_final: bool = False
    input_fingerprint: str = ""


@dataclass(frozen=True)
class ResearchWorkflowResult:
    experiment_id: str
    request_sha256: str
    run_id: str
    deterministic_sha256: str
    artifact_dir: str
    state: Literal["COMMITTED"] = "COMMITTED"


@dataclass(frozen=True)
class ResearchStateCheck:
    experiment_id: str
    run_id: str
    state: str
    deterministic_sha256: str
    artifact_count: int

"""Optional local reconciliation around unchanged offline research runners.

SQLite transactions and artifact renames are separate commits. A verified PREPARED
checkpoint anchors the complete expected bytes before final publication. Recovery
advances only an exact matching state; incomplete unanchored attempts are retained.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from packages.data.snapshots import load_dataset_snapshot
from packages.research.ai_replay import FrozenAIEvidence, load_frozen_ai_evidence
from packages.research.artifacts import _sync_directory, canonical_json
from packages.research.config import parse_research_config
from packages.research.reliability_models import (
    ResearchStateCheck,
    ResearchWorkflowRequest,
    ResearchWorkflowResult,
)
from packages.research.research_ledger import (
    LedgerRecord,
    PreparedResult,
    ResearchConflict,
    ResearchLedger,
    ResearchStateCorruption,
    SQLiteResearchLedger,
)
from packages.research.runner import _source_identity, evaluate_research, run_research
from packages.research.validation import load_matrix_config

FaultInjector = Callable[[str], None]


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _no_symlinks(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ResearchStateCorruption("symlink_in_research_state")


def _request_contract(request: ResearchWorkflowRequest) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", request.experiment_id):
        raise ResearchConflict("invalid_experiment_id")
    if request.mode not in {"run", "evaluate"} or (request.mode == "run" and request.include_final):
        raise ResearchConflict("invalid_research_mode")
    config_path, dataset_path = Path(request.config_path), Path(request.dataset_manifest_path)
    if not all(p.is_absolute() for p in (config_path, dataset_path, Path(request.state_dir))):
        raise ResearchConflict("absolute_local_paths_required")
    raw = config_path.read_bytes()
    evidence = FrozenAIEvidence()
    if request.mode == "run":
        config = parse_research_config(raw)
        baseline = None
    else:
        config = load_matrix_config(config_path)
        if hashlib.sha256(raw).hexdigest() != config.registration_sha256:
            raise ResearchConflict("configuration_changed_during_validation")
        baseline = config.baseline_input_sha256
        if config._ai_path:
            evidence = load_frozen_ai_evidence(config._ai_path)
    snapshot = load_dataset_snapshot(dataset_path)
    if config.dataset_manifest_sha256 != snapshot.manifest_sha256:
        raise ResearchConflict("dataset_manifest_hash_mismatch")
    source_root = Path(__file__).resolve().parents[2]
    return {
        "schema_version": "research-workflow-request/v1",
        "mode": request.mode,
        "include_final": request.include_final,
        "configuration": {
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "effective_sha256": _digest(config.model_dump(mode="json")),
            "baseline_input_sha256": baseline,
        },
        "dataset_manifest_sha256": snapshot.manifest_sha256,
        "ai_evidence_sha256": evidence.manifest_sha256,
        "ai_resolved_evidence_sha256": evidence.resolved_sha256,
        "source": _source_identity(),
        "orchestration_files": {
            p.relative_to(source_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((source_root / "apps/workers/app").rglob("*.py"))
        },
        "environment": {
            "python": platform.python_version(),
            "precision": "Python binary64 floats, integer shares",
            "dependencies": {
                d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
            },
        },
    }


def prepare_workflow_request(
    experiment_id: str,
    config_path: Path,
    dataset_manifest_path: Path,
    state_dir: Path,
    *,
    mode: Literal["run", "evaluate"] = "evaluate",
    include_final: bool = False,
) -> ResearchWorkflowRequest:
    """Pin content/source/environment before submitting work; no execution or writes."""
    request = ResearchWorkflowRequest(
        experiment_id,
        str(config_path.absolute()),
        str(dataset_manifest_path.absolute()),
        str(state_dir.absolute()),
        mode,
        include_final,
    )
    return replace(request, input_fingerprint=_digest(_request_contract(request)))


def _workspace(path: Path) -> bool:
    _no_symlinks(path)
    marker = path / "research-state.json"
    expected = canonical_json({"schema_version": "local-research-state/v1"})
    if path.exists() and not marker.exists() and any(path.iterdir()):
        raise ResearchStateCorruption("unowned_state_directory")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    _no_symlinks(marker)
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        if marker.read_bytes() != expected:
            raise ResearchStateCorruption("invalid_state_directory_marker") from None
        return False
    else:
        with os.fdopen(fd, "wb") as stream:
            stream.write(expected)
            stream.flush()
            os.fsync(stream.fileno())
        _sync_directory(path)
        return True


@contextmanager
def _ownership(root: Path, key: str) -> Iterator[None]:
    control = root / "control"
    _no_symlinks(control)
    control.mkdir(exist_ok=True)
    fd = os.open(control / f"{key}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("experiment_execution_busy") from exc
        yield
    finally:
        os.close(fd)  # Kernel ownership is released on close and abrupt process death.


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ResearchStateCorruption("duplicate_json_key")
        result[key] = value
    return result


def _json_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw, object_pairs_hook=_pairs)
        if not isinstance(value, dict) or canonical_json(value) != raw:
            raise ResearchStateCorruption("noncanonical_artifact_json")
        return value
    except (ValueError, OSError) as exc:
        raise ResearchStateCorruption(f"unverifiable_artifact_json:{path.name}") from exc


def _artifact_index(path: Path) -> tuple[str, dict[str, str], str]:
    _no_symlinks(path)
    if not path.is_dir():
        raise ResearchStateCorruption("missing_artifact_directory")
    index = _json_file(path / "hashes.json")
    if (
        set(index) != {"schema_version", "sha256"}
        or index["schema_version"] != "research-hashes/v1"
    ):
        raise ResearchStateCorruption("invalid_artifact_index")
    hashes = index["sha256"]
    required = {"manifest.json", "config.snapshot.json", "comparisons.json", "report.md"}
    if not isinstance(hashes, dict) or not required.issubset(hashes):
        raise ResearchStateCorruption("incomplete_artifact_index")
    for name, digest in hashes.items():
        relative = Path(name)
        if (
            not name
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != name
            or name in {"runtime.json", "hashes.json"}
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise ResearchStateCorruption("unsafe_artifact_index")
    expected = set(hashes) | {"runtime.json", "hashes.json"}
    actual, directories = set(), set()
    for entry in path.rglob("*"):
        mode = entry.lstat().st_mode
        if stat.S_ISREG(mode):
            actual.add(entry.relative_to(path).as_posix())
        elif stat.S_ISDIR(mode):
            directories.add(entry.relative_to(path).as_posix())
        else:
            raise ResearchStateCorruption("nonregular_artifact_entry")
    expected_dirs = {
        parent.as_posix()
        for name in expected
        for parent in Path(name).parents
        if parent != Path(".")
    }
    if actual != expected or directories != expected_dirs:
        raise ResearchStateCorruption("artifact_inventory_mismatch")
    for name, digest in hashes.items():
        if hashlib.sha256((path / name).read_bytes()).hexdigest() != digest:
            raise ResearchStateCorruption(f"artifact_hash_mismatch:{name}")
    runtime = _json_file(path / "runtime.json")
    if (
        runtime.get("schema_version") != "research-runtime/v1"
        or runtime.get("deterministic") is not False
    ):
        raise ResearchStateCorruption("invalid_runtime_metadata")
    manifest = _json_file(path / "manifest.json")
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{64}", run_id):
        raise ResearchStateCorruption("invalid_artifact_run_id")
    if manifest.get("artifacts_sha256") != {
        k: v for k, v in hashes.items() if k != "manifest.json"
    }:
        raise ResearchStateCorruption("manifest_index_disagreement")
    return run_id, hashes, _digest(hashes)


def _bind_manifest(path: Path, contract: dict[str, Any]) -> None:
    manifest = _json_file(path / "manifest.json")
    configuration = contract["configuration"]
    pairs = {
        "source": contract["source"],
        "dataset_manifest_sha256": contract["dataset_manifest_sha256"],
        "config_sha256": configuration["effective_sha256"],
    }
    if contract["mode"] == "run":
        pairs["config_input_sha256"] = configuration["input_sha256"]
    else:
        pairs.update(
            {
                "registration_sha256": configuration["input_sha256"],
                "baseline_input_sha256": configuration["baseline_input_sha256"],
                "ai_resolved_evidence_sha256": contract["ai_resolved_evidence_sha256"],
                "ai_evidence_sha256": contract["ai_evidence_sha256"],
                "final_evaluation_requested": contract["include_final"],
            }
        )
    if any(manifest.get(key) != value for key, value in pairs.items()):
        raise ResearchStateCorruption("artifact_request_identity_mismatch")
    environment = manifest.get("environment", {})
    current = contract["environment"]
    # R1 records four distributions using requirement spellings, while metadata
    # names can contain underscores. Compare normalized names without changing
    # either established artifact format or its environment fingerprint.
    dependencies = {
        re.sub(r"[-_.]+", "-", key).lower(): value for key, value in current["dependencies"].items()
    }
    if (
        environment.get("python") != current["python"]
        or environment.get("precision") != current["precision"]
        or any(
            dependencies.get(re.sub(r"[-_.]+", "-", k).lower()) != v
            for k, v in environment.get("dependencies", {}).items()
        )
    ):
        raise ResearchStateCorruption("artifact_environment_mismatch")


def _verify(path: Path, record: LedgerRecord) -> ResearchStateCheck:
    prepared = record.prepared
    if prepared is None:
        raise ResearchStateCorruption("missing_prepared_checkpoint")
    run_id, hashes, digest = _artifact_index(path)
    if (
        run_id != prepared.run_id
        or hashes != prepared.artifact_hashes
        or digest != prepared.deterministic_sha256
    ):
        raise ResearchStateCorruption("artifact_checkpoint_mismatch")
    _bind_manifest(path, json.loads(record.request_json))
    return ResearchStateCheck(record.experiment_id, run_id, record.state, digest, len(hashes))


def verify_research_run_state(
    run_id: str,
    artifact_dir: Path,
    ledger: ResearchLedger,
) -> ResearchStateCheck:
    """Read-only verification against a durable checkpoint; never repairs artifacts."""
    record = ledger.find_run(run_id)
    if record is None or record.state not in {"PREPARED", "PUBLISHED", "COMMITTED"}:
        raise ResearchStateCorruption("unverifiable_run_state")
    return _verify(artifact_dir, record)


def execute_research_experiment(
    request: ResearchWorkflowRequest,
    *,
    fault: FaultInjector | None = None,
) -> ResearchWorkflowResult:
    """Execute/reconcile once observably, with at-least-once private computation."""

    def checkpoint(phase: str) -> None:
        if fault is not None:
            fault(phase)

    contract = _request_contract(request)
    if _digest(contract) != request.input_fingerprint:
        raise ResearchConflict("frozen_input_fingerprint_changed")
    root = Path(request.state_dir)
    if any(
        p.is_relative_to(root)
        for p in (Path(request.config_path), Path(request.dataset_manifest_path))
    ):
        raise ResearchConflict("inputs_inside_mutable_state_directory")
    initialized_here = _workspace(root)
    key = hashlib.sha256(request.experiment_id.encode()).hexdigest()
    with _ownership(root, key):
        ledger_path = root / "experiments.sqlite3"
        _no_symlinks(ledger_path)
        if not initialized_here and not ledger_path.exists():
            raise ResearchStateCorruption("missing_research_ledger")
        ledger = SQLiteResearchLedger(ledger_path)
        owned_attempts = root / "attempts" / key
        _no_symlinks(owned_attempts)
        if ledger.get(request.experiment_id) is None and owned_attempts.exists():
            raise ResearchStateCorruption("experiment_history_missing_from_ledger")
        checkpoint("before_register")
        record = ledger.register(
            request.experiment_id, request.input_fingerprint, canonical_json(contract).decode()
        )
        checkpoint("after_register")
        if record.state == "FAILED":
            raise ResearchStateCorruption("experiment_failed_closed")
        try:
            if record.state in {"REGISTERED", "RUNNING"}:
                checkpoint("before_execution")
                record = ledger.start_attempt(request.experiment_id)
                stage_relpath = f"attempts/{key}/{record.attempt_count:08d}/artifacts"
                stage = root / stage_relpath
                _no_symlinks(stage)
                stage.parent.mkdir(parents=True, exist_ok=False)
                if request.mode == "run":
                    summary = run_research(
                        Path(request.config_path), Path(request.dataset_manifest_path), stage
                    )
                else:
                    summary = evaluate_research(
                        Path(request.config_path),
                        Path(request.dataset_manifest_path),
                        stage,
                        include_final=request.include_final,
                    )
                checkpoint("after_execution")
                if _request_contract(request) != contract:
                    raise ResearchConflict("frozen_inputs_changed_during_execution")
                run_id, hashes, digest = _artifact_index(stage)
                _bind_manifest(stage, contract)
                if (run_id, digest) != (summary.run_id, summary.deterministic_sha256):
                    raise ResearchStateCorruption("runner_summary_mismatch")
                checkpoint("before_prepare")
                record = ledger.prepare(
                    request.experiment_id,
                    PreparedResult(run_id, digest, hashes, stage_relpath, f"runs/{run_id}"),
                )
                checkpoint("after_prepare")
            prepared = record.prepared
            if prepared is None:
                raise ResearchStateCorruption("missing_prepared_checkpoint")
            stage, final = root / prepared.stage_relpath, root / prepared.output_relpath
            _no_symlinks(stage)
            _no_symlinks(final)
            if record.state == "PREPARED":
                if stage.exists() and final.exists():
                    raise ResearchStateCorruption("contradictory_stage_and_final")
                if not final.exists():
                    _verify(stage, record)
                    _no_symlinks(final.parent)
                    final.parent.mkdir(exist_ok=True)
                    checkpoint("before_publish")
                    stage.rename(final)
                    checkpoint("after_publish_rename")
                    _sync_directory(final.parent)
                    _sync_directory(stage.parent)
                _verify(final, record)
                checkpoint("before_published")
                record = ledger.mark_published(request.experiment_id)
                checkpoint("after_published")
            if stage.exists():
                raise ResearchStateCorruption("unexpected_prepared_stage")
            _verify(final, record)
            if record.state == "PUBLISHED":
                checkpoint("before_commit")
                record = ledger.commit(request.experiment_id)
                checkpoint("after_commit")
            if record.state != "COMMITTED":
                raise ResearchStateCorruption("invalid_terminal_state")
            return ResearchWorkflowResult(
                request.experiment_id,
                record.request_sha256,
                prepared.run_id,
                prepared.deterministic_sha256,
                str(final),
            )
        except ResearchStateCorruption:
            if record.state != "COMMITTED":
                ledger.fail(request.experiment_id, "persisted_state_unverifiable")
            raise
        except ValueError as exc:
            ledger.fail(request.experiment_id, "deterministic_execution_error")
            raise ResearchStateCorruption("deterministic_execution_error") from exc

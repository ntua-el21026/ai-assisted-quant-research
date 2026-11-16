"""Offline R2 matrix artifact, paired-control, final-isolation and rollback evidence."""

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

CONFIG = Path("experiments/configs/ablations.yaml")
DATASET = Path("tests/fixtures/market_snapshot/manifest.json")


def invoke(output: Path, *, include_final: bool = False):
    command = [
        sys.executable,
        "-m",
        "packages.research.cli",
        "evaluate",
        "--config",
        str(CONFIG),
        "--dataset",
        str(DATASET),
        "--output",
        str(output),
    ]
    if include_final:
        command.append("--include-final")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": os.defpath, "PYTHONHASHSEED": "931"},
    )


def test_evaluate_twice_publishes_complete_hashed_paired_matrix(tmp_path: Path) -> None:
    first, second = tmp_path / "one", tmp_path / "two"
    a, b = invoke(first), invoke(second)
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    index = json.loads((first / "hashes.json").read_text())["sha256"]
    for name, digest in index.items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == digest
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert (first / "hashes.json").read_bytes() == (second / "hashes.json").read_bytes()
    assert "runtime.json" not in index
    manifest = json.loads((first / "manifest.json").read_text())
    assert manifest["schema_version"] == "research-matrix-artifacts/v1"
    assert manifest["case_count"] == 32
    assert manifest["final_evaluation_included"] is False
    matrix = json.loads((first / "matrix.json").read_text())
    assert len(matrix["cases"]) == 32
    for case in matrix["cases"]:
        root = first / case["artifact_path"]
        assert all(
            (root / name).is_file()
            for name in (
                "manifest.json",
                "config.snapshot.json",
                "trades.csv",
                "equity.csv",
                "metrics.json",
                "comparisons.json",
                "ai_replay.json",
                "uncertainty.json",
                "report.md",
            )
        )
        metrics = json.loads((root / "metrics.json").read_text())
        assert metrics["schema_version"] == "research-metrics/v2"
        assert metrics["values"]["total_return"] is not None
        assert set(metrics["undefined"]) == {k for k, v in metrics["values"].items() if v is None}
    comparisons = json.loads((first / "comparisons.json").read_text())
    assert len(comparisons["pairs"]) == 16
    assert any(pair["changed_decisions"] > 0 for pair in comparisons["pairs"])
    assert "Synthetic demonstration" in (first / "report.md").read_text()


def test_final_evaluation_requires_opt_in_and_is_isolated(tmp_path: Path) -> None:
    result = invoke(tmp_path / "final", include_final=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "final/manifest.json").read_text())
    assert manifest["case_count"] == 48 and manifest["final_evaluation_included"] is True
    from packages.data.snapshots import load_dataset_snapshot
    from packages.research.validation import load_matrix_config, run_experiment_matrix

    snapshot = load_dataset_snapshot(DATASET)
    config = load_matrix_config(CONFIG)
    cutoff = snapshot.sessions[207].date
    changed = replace(
        snapshot,
        feature_bars_by_symbol={
            s: tuple(
                b
                if b.date <= cutoff
                else b.model_copy(
                    update={"open": 777.0, "high": 778.0, "low": 776.0, "close": 777.0}
                )
                for b in bars
            )
            for s, bars in snapshot.feature_bars_by_symbol.items()
        },
    )
    assert run_experiment_matrix(snapshot, config) == run_experiment_matrix(changed, config)


def test_missing_optional_ai_is_recorded_neutral_without_requests(tmp_path: Path) -> None:
    from packages.research.runner import evaluate_research

    values = yaml.safe_load(CONFIG.read_bytes())
    values["baseline_config"] = str(Path("experiments/configs/baseline.yaml").absolute())
    values["matrix"]["ai_manifest"] = "missing-ai.json"
    path = tmp_path / "missing.yaml"
    path.write_text(yaml.safe_dump(values))
    output = tmp_path / "neutral"
    evaluate_research(path, DATASET, output)
    matrix = json.loads((output / "matrix.json").read_text())
    assert matrix["evidence_sha256"] is None
    pairs = json.loads((output / "comparisons.json").read_text())["pairs"]
    assert all(p["changed_decisions"] == 0 for p in pairs)
    assert any("missing_evidence" in w for w in matrix["warnings"])


def test_nested_publication_rolls_back_without_false_success(tmp_path: Path, monkeypatch) -> None:
    from packages.research.runner import evaluate_research

    original = Path.write_bytes

    def fail(path: Path, data: bytes) -> int:
        if path.name == "metrics.json":
            raise OSError("injected nested artifact failure")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail)
    with pytest.raises(OSError, match="injected"):
        evaluate_research(CONFIG, DATASET, tmp_path / "atomic")
    assert not list(tmp_path.iterdir())


def test_offline_matrix_prohibits_provider_and_broker_imports(tmp_path: Path) -> None:
    code = """
import importlib.abc,socket,sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.startswith(('packages.broker','packages.paper','packages.ai.openai',
                                'packages.ai.providers','temporalio')):
            raise AssertionError('forbidden runtime import '+fullname)
sys.meta_path.insert(0,Guard())
def forbidden(*args,**kwargs): raise AssertionError('network forbidden')
socket.socket.connect=forbidden
socket.create_connection=forbidden
from pathlib import Path
from packages.research.runner import evaluate_research
evaluate_research(Path(sys.argv[1]),Path(sys.argv[2]),Path(sys.argv[3]))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(CONFIG), str(DATASET), str(tmp_path / "offline")],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": os.defpath},
    )
    assert result.returncode == 0, result.stderr


def test_invalid_registration_fails_before_publication(tmp_path: Path) -> None:
    from packages.research.runner import evaluate_research

    values = yaml.safe_load(CONFIG.read_bytes())
    values["baseline_config"] = str(Path("experiments/configs/baseline.yaml").absolute())
    values["baseline_config_sha256"] = "0" * 64
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(values))
    with pytest.raises(ValueError, match="baseline_config_hash"):
        evaluate_research(path, DATASET, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_nested_writer_rejects_path_escape_and_respects_existing_lock(tmp_path: Path) -> None:
    from packages.research.artifacts import publish_artifacts

    with pytest.raises(ValueError, match="artifact_path"):
        publish_artifacts(tmp_path / "bad", {"../escape.json": b"{}"}, b"{}")
    assert not (tmp_path / "escape.json").exists()
    lock = tmp_path / ".locked.lock"
    lock.write_text("other writer")
    with pytest.raises(FileExistsError):
        publish_artifacts(tmp_path / "locked", {"manifest.json": b"{}"}, b"{}")
    assert lock.read_text() == "other writer" and not (tmp_path / "locked").exists()


def test_each_case_records_effective_ablation_and_runtime_versions(tmp_path: Path) -> None:
    from packages.research.runner import evaluate_research

    output = tmp_path / "provenance"
    evaluate_research(CONFIG, DATASET, output)
    parent = json.loads((output / "manifest.json").read_text())
    case = next(
        c
        for c in json.loads((output / "matrix.json").read_text())["cases"]
        if c["variant_id"] == "without_volume"
    )
    local = output / case["artifact_path"]
    effective = json.loads((local / "config.snapshot.json").read_text())
    manifest = json.loads((local / "manifest.json").read_text())
    assert effective["ablation"]["disabled_filters"] == ["volume"]
    assert manifest["environment"] == parent["environment"]
    assert manifest["seed"] == 0
    assert manifest["registration_sha256"] == parent["registration_sha256"]

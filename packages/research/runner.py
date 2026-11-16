"""Compose local snapshot, causal strategy, accounting and versioned R1 artifacts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from packages.backtesting.execution import run_causal_backtest
from packages.data.snapshots import load_dataset_snapshot
from packages.research.artifacts import (
    canonical_csv,
    canonical_json,
    content_hashes,
    publish_artifacts,
)
from packages.research.config import parse_research_config
from packages.research.signals import generate_research_signals


@dataclass(frozen=True)
class ExperimentRunSummary:
    run_id: str
    output_dir: Path
    deterministic_sha256: str


def _source_identity() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    files = sorted((root / "packages").rglob("*.py")) + [root / "pyproject.toml", root / "uv.lock"]
    fingerprints = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
    }
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    return {
        "code_revision": revision.stdout.strip() if revision.returncode == 0 else "unavailable",
        "sha256": hashlib.sha256(canonical_json(fingerprints)).hexdigest(),
        "files": fingerprints,
    }


def run_research(
    config_path: Path,
    dataset_manifest_path: Path,
    output_dir: Path,
) -> ExperimentRunSummary:
    started = datetime.now(UTC)
    clock = time.perf_counter()
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"output_exists: {output_dir.name}")
    raw_config = config_path.read_bytes()
    config = parse_research_config(raw_config)
    snapshot = load_dataset_snapshot(dataset_manifest_path)
    if snapshot.manifest_sha256 != config.dataset_manifest_sha256:
        raise ValueError("dataset_manifest_hash_mismatch")
    if not set(config.approved_symbols).issubset(snapshot.feature_bars_by_symbol):
        raise ValueError("approved_symbols_missing_from_snapshot")
    if config.regime.proxy not in snapshot.feature_bars_by_symbol:
        raise ValueError("regime_proxy_missing_from_snapshot")
    if (
        config.date_start < snapshot.sessions[0].date
        or config.date_end > snapshot.sessions[-1].date
    ):
        raise ValueError("research_range_outside_snapshot")
    effective = config.model_dump(mode="json")
    source = _source_identity()
    dependencies = {
        d: importlib.metadata.version(d)
        for d in ("pydantic", "pydantic-core", "PyYAML", "structlog")
    }
    environment = {
        "python": platform.python_version(),
        "dependencies": dependencies,
        "precision": "Python binary64 floats, integer shares",
    }
    identity = {
        "schema_version": "research-artifacts/v1",
        "source": source,
        "config_sha256": hashlib.sha256(canonical_json(effective)).hexdigest(),
        "config_input_sha256": hashlib.sha256(raw_config).hexdigest(),
        "dataset_manifest_sha256": snapshot.manifest_sha256,
        "environment": environment,
    }
    run_id = hashlib.sha256(canonical_json(identity)).hexdigest()
    signals = generate_research_signals(snapshot, config)
    result = run_causal_backtest(snapshot, signals, config)
    final = result.equity_curve[-1]
    account = {
        "initial_cash": config.initial_cash,
        "final_equity": final.equity,
        "final_cash": final.cash,
        "gross_exposure": final.gross_exposure,
        "realized_pnl": sum(t.pnl for t in result.trades),
        "unrealized_pnl": sum(p.unrealized_pnl for p in result.open_positions),
        "total_fees": sum(e.fee for e in result.order_events),
        "slippage_cost": sum(e.slippage_cost for e in result.order_events),
        "open_positions": [p.model_dump(mode="json") for p in result.open_positions],
        "closed_trades": [t.model_dump(mode="json") for t in result.trades],
    }
    metrics = {
        "schema_version": "research-metrics/v1",
        "values": result.metrics.model_dump(),
        "accounting": account,
        "units": {
            "cash_equity_pnl_costs": "USD",
            "returns_exposure": "fraction",
            "trade_count": "closed round trips",
        },
        "definitions": {
            "total_return": "final equity / initial cash - 1",
            "max_drawdown": "minimum equity / running peak - 1; signed",
            "average_exposure": "mean daily gross market value / equity",
            "trade_pnl": "exit proceeds less entry notional and both fees",
            "costs": "adverse bps per side; fee on slipped notional; no market-impact model",
        },
        "undefined": {
            k: (
                "deferred_to_R2"
                if k in ("sharpe", "sortino")
                else "insufficient_closed_trades_or_zero_loss_denominator"
            )
            for k, v in result.metrics.model_dump().items()
            if v is None
        },
    }
    events = [e.model_dump(mode="json") for e in result.order_events]
    equity = [{**p.model_dump(mode="json"), "benchmark_equity": None} for p in result.equity_curve]
    warnings = sorted(
        set(
            (
                *snapshot.warnings,
                *result.warnings,
                "R1_compatible_run_mode_use_evaluate_for_R2_statistics_and_AI",
                "full_or_none_orders_no_volume_participation_or_partial_fills",
                "earnings_missing_is_entry_blocking_for_equities",
                "delistings_and_terminal_liquidation_not_modeled",
                "taxes_interest_market_impact_omitted",
            )
        )
    )
    label = (
        "Synthetic demonstration"
        if snapshot.manifest.kind == "synthetic"
        else "Historical backtest"
    )
    report = f"""# {label} — R1 data and simulation

Run ID: `{run_id}`. Experiment: `{config.experiment_id}`.

Source content SHA-256: `{source["sha256"]}`.
Dataset: `{snapshot.dataset_id}`; manifest SHA-256 `{snapshot.manifest_sha256}`.
This is a simulation and is not proof of profitability.

The run validates the offline strategy/risk-to-accounting path. Features use only bars
available one minute after the explicit session close. Entries use the exact next
calendar session open with adverse slippage; missing prices are unfilled. Opening stops
and exits precede opening entries, followed by intraday stops. Close-derived trailing
stops and routine exits become effective next session. Positions remain open at the end.
Risk sizing uses initial capital at decision time and actual opening capacity at fill.

| Accounting quantity (USD unless stated) | Value |
| --- | ---: |
| Initial cash | {config.initial_cash:.10f} |
| Final equity | {final.equity:.10f} |
| Realized P&L | {account["realized_pnl"]:.10f} |
| Unrealized P&L | {account["unrealized_pnl"]:.10f} |
| Fees | {account["total_fees"]:.10f} |
| Closed round trips (count) | {len(result.trades)} |
| Terminal positions (count) | {len(result.open_positions)} |

Core accounting metrics are in `metrics.json`. Sharpe/Sortino and aligned comparisons
are omitted in this R1-compatible mode; use `evaluate` for R2 reports.
`trades.csv` records all decision rejections, fills and unfilled orders;
`metrics.json` retains terminal positions. Synthetic inputs support engineering checks,
not market-performance, AI-uplift or untouched-holdout conclusions.

Warnings and limitations:

""" + "".join(f"- {w}\n" for w in warnings)
    files = {
        "config.snapshot.json": canonical_json(effective),
        "trades.csv": canonical_csv(
            (
                "order_id",
                "symbol",
                "action",
                "decision_session",
                "decision_at",
                "eligible_session",
                "session",
                "quantity",
                "status",
                "reason",
                "parent_entry_id",
                "decision_accepted",
                "decision_reason_codes",
                "reference_price",
                "stop_price",
                "breakout_level",
                "base_price",
                "fill_price",
                "fee",
                "slippage_cost",
            ),
            events,
        ),
        "equity.csv": canonical_csv(
            ("date", "equity", "cash", "gross_exposure", "benchmark_equity"), equity
        ),
        "metrics.json": canonical_json(metrics),
        "comparisons.json": canonical_json(
            {
                "schema_version": "research-comparisons/v1",
                "status": "deferred_to_R2",
                "references": [],
                "reason": (
                    "R1-compatible run format: data, causal decisions and accounting only; "
                    "use evaluate for R2 comparison artifacts"
                ),
            }
        ),
        "report.md": report.encode("utf-8"),
    }
    manifest = {
        **identity,
        "run_id": run_id,
        "experiment_id": config.experiment_id,
        "seed": config.seed,
        "execution_model": "research-execution/v1",
        "dataset": {
            "dataset_id": snapshot.dataset_id,
            "kind": snapshot.manifest.kind,
            "manifest_sha256": snapshot.manifest_sha256,
            "provenance": snapshot.manifest.model_dump(mode="json"),
        },
        "time_convention": (
            "explicit calendar offsets; EOD close + 1 minute; exact next session open"
        ),
        "warnings": warnings,
        "artifacts_sha256": content_hashes(files),
        "runtime_metadata": {"path": "runtime.json", "deterministic": False},
    }
    files["manifest.json"] = canonical_json(manifest)
    deterministic_sha256 = hashlib.sha256(canonical_json(content_hashes(files))).hexdigest()
    runtime = canonical_json(
        {
            "schema_version": "research-runtime/v1",
            "deterministic": False,
            "started_at_utc": started.isoformat(),
            "elapsed_seconds": time.perf_counter() - clock,
            "platform": platform.platform(),
            "python_executable": sys.executable,
        }
    )
    publish_artifacts(output_dir, files, runtime)
    return ExperimentRunSummary(run_id, output_dir, deterministic_sha256)


def evaluate_research(
    config_path: Path,
    dataset_manifest_path: Path,
    output_dir: Path,
    *,
    include_final: bool = False,
) -> ExperimentRunSummary:
    """Evaluate exactly a frozen local registration, then publish all cases atomically."""
    from packages.research.ai_replay import FrozenAIEvidence, load_frozen_ai_evidence
    from packages.research.matrix_artifacts import matrix_artifacts
    from packages.research.validation import load_matrix_config, run_experiment_matrix

    started = datetime.now(UTC)
    clock = time.perf_counter()
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"output_exists: {output_dir.name}")
    # The loader reads/validates each registration/base input once and retains both hashes.
    config = load_matrix_config(config_path)
    snapshot = load_dataset_snapshot(dataset_manifest_path)
    if snapshot.manifest_sha256 != config.dataset_manifest_sha256:
        raise ValueError("dataset_manifest_hash_mismatch")
    if not set(config.approved_symbols).issubset(snapshot.feature_bars_by_symbol):
        raise ValueError("approved_symbols_missing_from_snapshot")
    if config.regime.proxy not in snapshot.feature_bars_by_symbol:
        raise ValueError("regime_proxy_missing_from_snapshot")
    if (
        config.date_start < snapshot.sessions[0].date
        or config.date_end > snapshot.sessions[-1].date
    ):
        raise ValueError("research_range_outside_snapshot")
    evidence = (
        load_frozen_ai_evidence(config._ai_path)
        if config._ai_path is not None
        else FrozenAIEvidence(warnings=("missing_evidence",))
    )
    source = _source_identity()
    environment = {
        "python": platform.python_version(),
        "precision": "Python binary64 floats, integer shares",
        "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
    }
    identity = {
        "schema_version": "research-matrix-artifacts/v1",
        "source": source,
        "environment": environment,
        "registration_sha256": config.registration_sha256,
        "baseline_input_sha256": config.baseline_input_sha256,
        "config_sha256": hashlib.sha256(canonical_json(config.model_dump(mode="json"))).hexdigest(),
        "dataset_manifest_sha256": snapshot.manifest_sha256,
        "dataset_provenance": snapshot.manifest.model_dump(mode="json"),
        "ai_evidence_sha256": evidence.manifest_sha256,
        "declared_ai_evidence_sha256": config.matrix.ai_manifest_sha256,
        "ai_provenance": evidence.manifest.model_dump(mode="json") if evidence.manifest else None,
        "seed": config.seed,
        "final_evaluation_requested": include_final,
        "execution_model": "research-execution/v1",
        "metrics_version": "research-metrics/v2",
    }
    run_id = hashlib.sha256(canonical_json(identity)).hexdigest()
    matrix = run_experiment_matrix(snapshot, config, include_final=include_final, evidence=evidence)
    files = matrix_artifacts(matrix, config, identity, run_id)
    digest = hashlib.sha256(canonical_json(content_hashes(files))).hexdigest()
    runtime = canonical_json(
        {
            "schema_version": "research-runtime/v1",
            "deterministic": False,
            "started_at_utc": started.isoformat(),
            "elapsed_seconds": time.perf_counter() - clock,
            "platform": platform.platform(),
            "python_executable": sys.executable,
        }
    )
    publish_artifacts(output_dir, files, runtime)
    return ExperimentRunSummary(run_id, output_dir, digest)

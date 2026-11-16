"""Synthetic-only qualification of v2 data, action accounting and benchmarks.

This is a numerical infrastructure example, not a strategy backtest. Ordinary
research run/evaluate and their optional R3 workflow remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Context, Decimal, DecimalException, Inexact, localcontext
from pathlib import Path

from packages.backtesting.corporate_actions import (
    AccountingPosition,
    PendingOrder,
    PortfolioActionState,
    apply_session_actions,
)
from packages.data.historical_snapshots import HistoricalSnapshot, load_historical_snapshot
from packages.research.artifacts import canonical_json, content_hashes, publish_artifacts
from packages.research.historical_benchmarks import (
    ReturnConvention,
    evaluate_historical_benchmark,
)
from packages.research.runner import ExperimentRunSummary, _source_identity


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    return value


def _accounting_points(
    snapshot: HistoricalSnapshot, security_id: str, initial_cash: Decimal
) -> list[dict[str, object]]:
    """Initial analytical allocation; never simulates orders, risk checks or stops.

    The pending order and protective level are inert probes of split conversion.
    Their fills/trigger behavior remains the unchanged research simulator's job.
    """
    state = PortfolioActionState(cash=initial_cash)
    actions = tuple(a for a in snapshot.actions if a.security_id == security_id)
    bars = {b.date: b for b in snapshot.raw_bars if b.security_id == security_id}
    points: list[dict[str, object]] = []
    try:
        with localcontext(Context(prec=50)) as context:
            context.traps[Inexact] = True
            for index, session in enumerate(snapshot.manifest.sessions):
                bar = bars.get(session.date)
                if bar is None:
                    raise ValueError("missing_demo_execution_price")
                mapping = snapshot.mapping_for(security_id, session.date)
                if (
                    mapping.available_at > session.open_at
                    or mapping.point_in_time_status != "confirmed"
                ):
                    raise ValueError("demo_identity_unavailable")
                # Identity-preserving renames change labels, never economic quantities.
                state = state.model_copy(
                    update={
                        "positions": tuple(
                            p.model_copy(update={"symbol": mapping.symbol}) for p in state.positions
                        ),
                        "pending_orders": tuple(
                            o.model_copy(update={"symbol": mapping.symbol})
                            for o in state.pending_orders
                        ),
                    }
                )
                state = apply_session_actions(
                    state,
                    actions,
                    session=session.date,
                    as_of=session.open_at,
                    fractional_policy="exact",
                )
                if index == 0:
                    state = state.model_copy(
                        update={
                            "cash": Decimal(0),
                            "positions": (
                                AccountingPosition(
                                    security_id=security_id,
                                    symbol=bar.symbol,
                                    quantity=initial_cash / bar.open,
                                    cost_basis=initial_cash,
                                    stop_price=bar.open * Decimal("0.9"),
                                ),
                            ),
                            "pending_orders": (
                                PendingOrder(
                                    order_id="synthetic-inert-order",
                                    security_id=security_id,
                                    symbol=bar.symbol,
                                    quantity=Decimal(1),
                                    limit_price=bar.open,
                                    stop_price=bar.open * Decimal("0.9"),
                                ),
                            ),
                        }
                    )
                receivable = sum(
                    (e.cash_amount for e in state.entitlements if not e.paid), Decimal(0)
                )
                dividends = sum((e.cash_amount for e in state.entitlements), Decimal(0))
                marked = state.positions[0].quantity * bar.close
                equity = state.cash + receivable + marked
                price_pnl = marked - state.positions[0].cost_basis
                if equity != initial_cash + price_pnl + dividends:
                    raise ValueError("demo_accounting_conservation_failed")
                points.append(
                    {
                        "date": session.date.isoformat(),
                        "equity": str(equity),
                        "market_value": str(marked),
                        "dividend_receivable": str(receivable),
                        "price_pnl": str(price_pnl),
                        "dividend_income": str(dividends),
                        "state": state.model_dump(mode="json"),
                    }
                )
    except DecimalException as exc:
        raise ValueError("inexact_synthetic_demo_accounting") from exc
    return points


def run_historical_synthetic(
    dataset_manifest_path: Path, output_dir: Path, *, security_id: str, initial_cash: Decimal
) -> ExperimentRunSummary:
    """Publish synthetic engineering evidence; refuse historical input before its files."""
    if not isinstance(initial_cash, Decimal) or not initial_cash.is_finite() or initial_cash <= 0:
        raise ValueError("invalid_initial_cash")
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError("output_exists")
    raw_manifest = dataset_manifest_path.read_bytes()
    if json.loads(raw_manifest).get("kind") != "synthetic":
        raise ValueError("synthetic_inputs_only")
    snapshot = load_historical_snapshot(
        dataset_manifest_path, expected_sha256=hashlib.sha256(raw_manifest).hexdigest()
    )
    if security_id not in {s.security_id for s in snapshot.manifest.securities}:
        raise ValueError("unknown_demo_security")
    started, clock = datetime.now(UTC), time.perf_counter()
    config = {
        "schema_version": "historical-infrastructure-config/v1",
        "kind": "synthetic",
        "security_id": security_id,
        "initial_cash": str(initial_cash),
        "fractional_policy": "exact_finite_decimal_action_ledger",
        "allocation": "fixed_first_open_fractional_allocation_no_strategy_decisions",
        "inert_stop_fraction": "0.9",
        "inert_pending_order_quantity": "1",
        "seed": None,
        "randomness": "none",
    }
    source = _source_identity()
    identity = {
        "schema_version": "historical-infrastructure-artifacts/v1",
        "kind": "synthetic",
        "source": source,
        "config_sha256": hashlib.sha256(canonical_json(config)).hexdigest(),
        "dataset_manifest_sha256": snapshot.manifest_sha256,
        "environment": {
            "python": platform.python_version(),
            "dependencies": {
                name: importlib.metadata.version(name) for name in ("pydantic", "pydantic-core")
            },
            "precision": (
                "finite Decimal ledger 50; exact rational benchmarks with 50-digit reporting"
            ),
        },
    }
    run_id = hashlib.sha256(canonical_json(identity)).hexdigest()
    accounting = _accounting_points(snapshot, security_id, initial_cash)
    conventions: tuple[ReturnConvention, ...] = (
        "price_return",
        "total_return_cash",
        "total_return_reinvest",
    )
    benchmarks = {
        convention: evaluate_historical_benchmark(
            snapshot, security_id, initial_cash, convention=convention
        )
        for convention in conventions
    }
    cash_curve = benchmarks["total_return_cash"].points
    if any(
        Decimal(str(point["equity"])) != reference.equity
        for point, reference in zip(accounting, cash_curve, strict=True)
    ):
        raise ValueError("independent_benchmark_accounting_disagreement")
    features = [
        {
            "decision_at": session.decision_at.isoformat(),
            "basis": basis,
            "action_ids": list(view.action_ids),
            "bars": [bar.model_dump(mode="json") for bar in view.bars],
        }
        for session in snapshot.manifest.sessions
        for basis in ("raw", "split_asof")
        for view in (snapshot.feature_view(session.decision_at, basis=basis),)
    ]
    files = {
        "config.snapshot.json": canonical_json(config),
        "accounting.json": canonical_json(
            {
                "schema_version": "synthetic-action-accounting/v1",
                "kind": "synthetic",
                "points": accounting,
                "assumptions": (
                    "Analytical initial allocation; no fills, stop triggers, risk "
                    "or strategy decisions. Pending order is inert."
                ),
            }
        ),
        "benchmarks.json": canonical_json(
            {
                "schema_version": "action-aware-benchmarks/v1",
                "kind": "synthetic",
                "results": {key: _jsonable(asdict(value)) for key, value in benchmarks.items()},
            }
        ),
        "features.json": canonical_json({"kind": "synthetic", "views": features}),
        "comparisons.json": canonical_json(
            {
                "kind": "synthetic",
                "action_ledger_equals_cash_total_return_curve": True,
                "comparison": (
                    "Independent rational analytical comparator versus "
                    "finite-Decimal action ledger; not a strategy comparison."
                ),
            }
        ),
        "report.md": (
            f"# Synthetic R4-A infrastructure qualification\n\nRun ID: `{run_id}`.\n\n"
            "Original artificial prices/actions verify accounting and provenance only.\n"
            "This is not a historical study, strategy backtest or AI-uplift result.\n\n"
            "| Convention | Terminal synthetic equity (USD) |\n| --- | ---: |\n"
            + "".join(
                f"| {name} | {value.points[-1].equity} |\n" for name, value in benchmarks.items()
            )
            + "\nDividends are receivables on ex-date and cash on payment. "
            "Reinvestment assumes payment-open cash availability.\n"
            "The pending order/stop are inert split-conversion probes, "
            "without risk-policy or fill simulation.\n"
            "R1/R2 strategy, numerical thresholds and R3 workflows are unchanged.\n"
            "Historical acquisition, data-rights clearance and empirical R4 remain pending.\n"
        ).encode(),
    }
    manifest = {
        **identity,
        "run_id": run_id,
        "execution_model": "synthetic-action-qualification/v1",
        "dataset": {"kind": "synthetic", "provenance": snapshot.manifest.model_dump(mode="json")},
        "warnings": list(snapshot.warnings),
        "artifacts_sha256": content_hashes(files),
        "runtime_metadata": {"path": "runtime.json", "deterministic": False},
    }
    files["manifest.json"] = canonical_json(manifest)
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


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Synthetic-only R4-A numerical qualification")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--security-id", required=True)
    parser.add_argument("--initial-cash", required=True)
    args = parser.parse_args(argv)
    try:
        initial = Decimal(args.initial_cash)
    except DecimalException:
        parser.error("invalid_initial_cash")
    summary = run_historical_synthetic(
        args.dataset, args.output, security_id=args.security_id, initial_cash=initial
    )
    print(
        json.dumps(
            {
                "run_id": summary.run_id,
                "output_dir": str(summary.output_dir),
                "deterministic_sha256": summary.deterministic_sha256,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

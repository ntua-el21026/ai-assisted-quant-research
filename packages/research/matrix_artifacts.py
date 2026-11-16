"""Versioned R2 result tables and reports derived exclusively from matrix records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from packages.backtesting.models import ResearchOrderEvent
from packages.research.artifacts import canonical_csv, canonical_json, content_hashes
from packages.research.validation import (
    ExperimentMatrixResult,
    MatrixCaseResult,
    MatrixResearchConfig,
)


def _case_files(
    case: MatrixCaseResult, config: MatrixResearchConfig, run_id: str, identity: Mapping[str, Any]
) -> dict[str, bytes]:
    result = case.result
    benchmark_names = ("spy_buy_and_hold", "spy_exposure_adjusted", "equal_weight")
    equity = [
        {
            **p.model_dump(mode="json"),
            **{
                name: (
                    case.benchmarks.curves[name][i].equity
                    if name in case.benchmarks.curves
                    else None
                )
                for name in benchmark_names
            },
        }
        for i, p in enumerate(result.equity_curve)
    ]
    accounting = {
        "initial_cash": config.initial_cash,
        "final_cash": result.equity_curve[-1].cash,
        "final_equity": result.equity_curve[-1].equity,
        "closed_trades": [t.model_dump(mode="json") for t in result.trades],
        "open_positions": [p.model_dump(mode="json") for p in result.open_positions],
    }
    metrics = {
        "schema_version": "research-metrics/v2",
        **case.metrics.model_dump(mode="json"),
        "accounting": accounting,
    }
    label = (
        "Synthetic demonstration"
        if "dataset_kind:synthetic" in config_label(case)
        else "Historical backtest"
    )
    report = f"""# {label} — registered R2 case

Parent run: `{run_id}`. Case: `{case.case_id}`. Pair: `{case.pair_id}`.
Fold `{case.fold.fold_id}` ({case.fold.role}), variant `{case.variant_id}`,
costs `{case.cost_id}`, AI policy `{case.ai_policy}`.
Evaluation {case.fold.evaluation_start} through {case.fold.evaluation_end}; training ends
{case.fold.train_end}. Parameters are registered and fixed; there is no fitting or ranking.

| Metric | Value |
| --- | ---: |
| Net P&L (USD) | {case.metrics.values["net_pnl"]} |
| Total return (fraction) | {case.metrics.values["total_return"]} |
| Signed maximum drawdown (fraction) | {case.metrics.values["max_drawdown"]} |
| Closed trades | {case.metrics.values["trade_count"]} |
| Terminal open positions | {case.metrics.values["open_position_count"]} |

The authoritative metric definitions, units, undefined reasons and conventions are in
`metrics.json`. `comparisons.json` retains exactly aligned, frictionless price-return
comparators. These do not represent dividend-inclusive historical SPY results.
`uncertainty.json` reports conditional resampling or explicit insufficiency reasons.
`ai_replay.json` retains candidate-level validity, coverage and fallback reasons.
All daily fills/positions follow research-execution/v1. BacktestResult's legacy metric
field is not used as an R2 statistical report. Backtests are not proof of profitability.
"""
    files = {
        "config.snapshot.json": canonical_json(
            {
                "research": case.effective_config,
                "fold": case.fold.model_dump(mode="json"),
                "variant_id": case.variant_id,
                "ablation": next(
                    a.model_dump(mode="json")
                    for a in config.matrix.ablations
                    if a.variant_id == case.variant_id
                ),
                "cost_id": case.cost_id,
                "ai_policy": case.ai_policy,
                "ai_execution_policy": "neutral-shadow-entry/v1",
                "metrics": config.matrix.metrics.model_dump(mode="json"),
                "resampling": config.matrix.resampling.model_dump(mode="json"),
            }
        ),
        "trades.csv": canonical_csv(
            tuple(ResearchOrderEvent.model_fields),
            [e.model_dump(mode="json") for e in result.order_events],
        ),
        "equity.csv": canonical_csv(
            ("date", "equity", "cash", "gross_exposure", *benchmark_names), equity
        ),
        "metrics.json": canonical_json(metrics),
        "comparisons.json": canonical_json(
            {"schema_version": "research-benchmarks/v1", **case.benchmarks.model_dump(mode="json")}
        ),
        "ai_replay.json": canonical_json(
            {
                "schema_version": "research-ai-replay/v1",
                "policy": case.ai_policy,
                "execution_policy": "neutral-shadow-entry/v1",
                "resolved_evidence_sha256": identity["ai_resolved_evidence_sha256"],
                "evidence_resolution": identity["ai_evidence_resolution"],
                "diagnostics": [d.model_dump(mode="json") for d in case.ai_diagnostics],
            }
        ),
        "uncertainty.json": canonical_json(case.uncertainty),
        "report.md": report.encode(),
    }
    files["manifest.json"] = canonical_json(
        {
            "schema_version": "research-matrix-case/v1",
            "parent_run_id": run_id,
            "case_id": case.case_id,
            "pair_id": case.pair_id,
            "fold_id": case.fold.fold_id,
            "variant_id": case.variant_id,
            "cost_id": case.cost_id,
            "ai_policy": case.ai_policy,
            "source": identity["source"],
            "environment": identity["environment"],
            "seed": config.seed,
            "registration_sha256": config.registration_sha256,
            "dataset_manifest_sha256": identity["dataset_manifest_sha256"],
            "ai_evidence_sha256": identity["ai_evidence_sha256"],
            "ai_resolved_evidence_sha256": identity["ai_resolved_evidence_sha256"],
            "ai_evidence_resolution": identity["ai_evidence_resolution"],
            "metric_settings": config.matrix.metrics.model_dump(mode="json"),
            "artifacts_sha256": content_hashes(files),
        }
    )
    return files


def config_label(case: MatrixCaseResult) -> tuple[str, ...]:
    return case.benchmarks.warnings


def matrix_artifacts(
    matrix: ExperimentMatrixResult,
    config: MatrixResearchConfig,
    identity: Mapping[str, Any],
    run_id: str,
) -> dict[str, bytes]:
    files = {}
    summaries = []
    for case in matrix.cases:
        prefix = f"cases/{case.case_id}"
        files.update(
            {
                f"{prefix}/{name}": data
                for name, data in _case_files(case, config, run_id, identity).items()
            }
        )
        eligible = [
            d for d in case.ai_diagnostics if d.reason != "deterministic_rejection_preserved"
        ]
        summaries.append(
            {
                "case_id": case.case_id,
                "pair_id": case.pair_id,
                "artifact_path": prefix,
                "fold": case.fold.model_dump(mode="json"),
                "variant_id": case.variant_id,
                "cost_id": case.cost_id,
                "ai_policy": case.ai_policy,
                "metrics": case.metrics.values,
                "ai_coverage": {
                    "eligible_decisions": len(eligible),
                    "valid_outputs": sum(d.output_valid for d in eligible),
                    "neutral_fallbacks": sum(d.fallback for d in eligible),
                    "changed_decisions": sum(
                        d.original_quantity != d.resulting_quantity for d in eligible
                    ),
                },
            }
        )
    paired: dict[str, dict[str, MatrixCaseResult]] = {}
    for case in matrix.cases:
        paired.setdefault(case.pair_id, {})[case.ai_policy] = case
    pairs = []
    for pair_id, members in sorted(paired.items()):
        if "AI_NEUTRAL" not in members or "AI_NEGATIVE_ONLY" not in members:
            continue
        neutral, adverse = members["AI_NEUTRAL"], members["AI_NEGATIVE_ONLY"]
        deltas = {}
        for key in (
            "total_return",
            "max_drawdown",
            "sharpe",
            "sortino",
            "average_exposure",
            "trade_count",
            "turnover",
            "transaction_cost",
        ):
            left, right = neutral.metrics.values[key], adverse.metrics.values[key]
            deltas[key] = right - left if right is not None and left is not None else None
        pairs.append(
            {
                "pair_id": pair_id,
                "neutral_case_id": neutral.case_id,
                "negative_case_id": adverse.case_id,
                "delta_negative_minus_neutral": deltas,
                "changed_decisions": sum(
                    d.original_quantity != d.resulting_quantity for d in adverse.ai_diagnostics
                ),
            }
        )
    files["config.snapshot.json"] = canonical_json(config.model_dump(mode="json"))
    files["folds.json"] = canonical_json(
        {
            "schema_version": "research-folds/v1",
            "folds": [
                f.model_dump(mode="json")
                for f in {c.fold.fold_id: c.fold for c in matrix.cases}.values()
            ],
            "final_evaluation_included": matrix.final_evaluation_included,
            "selection_policy": matrix.selection_policy,
        }
    )
    files["matrix.json"] = canonical_json(
        {
            "schema_version": matrix.schema_version,
            "cases": summaries,
            "selection_policy": matrix.selection_policy,
            "final_evaluation_included": matrix.final_evaluation_included,
            "warnings": matrix.warnings,
            "evidence_sha256": matrix.evidence_sha256,
            "resolved_evidence_sha256": matrix.resolved_evidence_sha256,
        }
    )
    files["comparisons.json"] = canonical_json(
        {
            "schema_version": "research-matrix-comparisons/v1",
            "pairs": pairs,
            "selection_policy": matrix.selection_policy,
            "note": ("Paired observations; no ranking, superiority or AI-benefit claim"),
        }
    )
    label = (
        "Synthetic demonstration"
        if any("dataset_kind:synthetic" in c.benchmarks.warnings for c in matrix.cases)
        else "Historical backtest"
    )
    rows = "".join(
        f"| `{c.case_id[:12]}` | {c.fold.role} | {c.variant_id} | {c.cost_id} | "
        f"{c.ai_policy} | {c.metrics.values['total_return']} |\n"
        for c in matrix.cases
    )
    files["report.md"] = (
        f"""# {label} — R2 registered experiment matrix

Run ID: `{run_id}`. Cases: {len(matrix.cases)}.
Final evaluation included: {matrix.final_evaluation_included}.
Selection policy: `{matrix.selection_policy}`. Holdout label: `{config.matrix.holdout_status}`.

| Case prefix | Split | Variant | Costs | AI policy | Total return (fraction) |
| --- | --- | --- | --- | --- | ---: |
"""
        + rows
        + """
The complete condition IDs, data/config/source/AI fingerprints and artifact hashes are in
`manifest.json`, `matrix.json` and `hashes.json`. Each case directory contains metric
conventions, trades/equity, exact aligned benchmarks, AI diagnostics and conditional
uncertainty estimates. Undefined values are null with reasons, including insufficient
closed trades/months. Annualization uses the registered minimum sample length.

Parameters, folds and costs are predeclared; there is no fit, search, winning-case selection
or final-period tuning. Each fold resets capital/positions; full anchored history supplies
causal recursive indicators, with at least 200 prior observations. Final evaluation is
separately registered and opt-in. The baseline keeps its frozen CAUTION simplification;
explicit ablations change only the registered filter component (regime ablation includes
its sizing multiplier), preserving numerical portfolio safeguards and stops.

AI can only remove or reduce existing deterministic candidates. Paired control runs use the
same data, weights, budgets and costs. A neutral execution shadow gates entries at the
eligible opening, preventing replacement trades after a veto. Executed entry identities
are a subset of the control, with no greater quantity or session gross USD exposure.
Equity-normalized exposure ratios can differ because each portfolio has its own equity
denominator; they are reported separately from this notional constraint. These comparisons do not
establish AI predictive benefit. The public reference news/model outputs are hand-authored synthetic
illustrations, not real provider or model observations. No external services are called.

Benchmarks use raw declared action/dividend-free prices, frictionless fractional units and
zero cash yield; the exposure comparator uses prior EOD exposure and is analytical. It is
not an executable trading strategy. Turnover uses both-side filled notional / initial
capital. Conditional trade/month resampling is not a future-market confidence guarantee;
small samples, nonstationarity, selection bias and multiple comparisons limit interpretation.
Taxes, interest, impact, corporate actions/dividends and delistings remain unmodeled. The
framework is in development; R3 recovery and R4 real-data research are not implemented here.
"""
    ).encode()
    manifest = {
        **identity,
        "run_id": run_id,
        "case_count": len(matrix.cases),
        "final_evaluation_included": matrix.final_evaluation_included,
        "selection_policy": matrix.selection_policy,
        "warnings": matrix.warnings,
        "artifacts_sha256": content_hashes(files),
        "runtime_metadata": {"path": "runtime.json", "deterministic": False},
    }
    files["manifest.json"] = canonical_json(manifest)
    return files

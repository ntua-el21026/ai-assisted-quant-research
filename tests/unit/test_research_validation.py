"""Fixed chronological registration, bounded ablations and conditional uncertainty."""

from pathlib import Path

import pytest
import yaml

from packages.data.snapshots import load_dataset_snapshot
from packages.research.models import ResearchConfig


def matrix_config(**updates):
    from packages.research.validation import MatrixResearchConfig

    values = yaml.safe_load(Path("experiments/configs/baseline.yaml").read_bytes())
    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    values["matrix"] = {
        "schema_version": "experiment-matrix/v1",
        "walk_forward": {
            "initial_train_sessions": 200,
            "evaluation_sessions": 4,
            "warmup_sessions": 200,
            "final_start": str(snapshot.sessions[208].date),
            "final_end": str(snapshot.sessions[209].date),
        },
        "ablations": [
            {"variant_id": "baseline", "disabled_filters": []},
            {"variant_id": "without_volume", "disabled_filters": ["volume"]},
        ],
        "costs": [
            {"cost_id": "baseline", "execution": values["execution"]},
            {
                "cost_id": "stress",
                "execution": {
                    **values["execution"],
                    "entry_slippage_bps": 25,
                    "stop_slippage_bps": 40,
                },
            },
        ],
        "ai_policies": ["AI_NEUTRAL", "AI_NEGATIVE_ONLY"],
        "resampling": {"iterations": 20, "confidence_level": 0.95, "minimum_units": 2},
        "metrics": {},
        "holdout_status": "synthetic_engineering_only",
        "max_cases": 64,
        "ai_manifest": None,
        "ai_manifest_sha256": None,
    }
    values["matrix"].update(updates)
    return MatrixResearchConfig.model_validate(values)


def test_walk_forward_is_anchored_and_never_silently_reads_final_evaluation() -> None:
    from packages.research.validation import build_walk_forward_folds

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    config = matrix_config()
    dates = tuple(s.date for s in snapshot.sessions)
    folds = build_walk_forward_folds(config, dates)
    assert len(folds) == 2
    assert folds[0].train_start == dates[0]
    assert folds[0].train_end == dates[199]
    assert (folds[0].evaluation_start, folds[0].evaluation_end) == (dates[200], dates[203])
    assert (folds[1].train_end, folds[1].evaluation_start, folds[1].evaluation_end) == (
        dates[203],
        dates[204],
        dates[207],
    )
    assert folds[0].warmup_start == dates[0]
    assert folds[1].warmup_start == dates[0]
    assert folds[1].minimum_warmup_start == dates[4]
    assert all(f.train_end < f.evaluation_start <= f.evaluation_end < dates[208] for f in folds)
    assert folds == build_walk_forward_folds(config, dates)
    final = build_walk_forward_folds(config, dates, include_final=True)[-1]
    assert final.role == "final_evaluation"
    assert (final.evaluation_start, final.evaluation_end) == (dates[208], dates[209])


def test_calendar_and_registration_fail_closed() -> None:
    from packages.research.validation import build_walk_forward_folds

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    dates = tuple(s.date for s in snapshot.sessions)
    with pytest.raises(ValueError, match="sorted_unique"):
        build_walk_forward_folds(matrix_config(), dates + (dates[-1],))
    with pytest.raises(ValueError, match="warmup"):
        matrix_config(
            walk_forward={
                "initial_train_sessions": 20,
                "evaluation_sessions": 4,
                "warmup_sessions": 200,
            }
        )
    with pytest.raises(ValueError, match="protective|unsupported"):
        matrix_config(ablations=[{"variant_id": "unsafe", "disabled_filters": ["protective_stop"]}])
    with pytest.raises(ValueError, match="baseline"):
        matrix_config(ablations=[{"variant_id": "arbitrary", "disabled_filters": []}])


def test_matrix_is_paired_bounded_and_has_no_parameter_selection() -> None:
    from packages.research.validation import run_experiment_matrix

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    matrix = run_experiment_matrix(snapshot, matrix_config())
    assert len(matrix.cases) == 16
    assert matrix.final_evaluation_included is False
    assert matrix.selection_policy == "fixed_registered_parameters_no_fitting_or_ranking"
    neutral = {c.pair_id: c for c in matrix.cases if c.ai_policy == "AI_NEUTRAL"}
    negative = {c.pair_id: c for c in matrix.cases if c.ai_policy == "AI_NEGATIVE_ONLY"}
    assert neutral.keys() == negative.keys()
    for key in neutral:
        assert neutral[key].result == negative[key].result
        assert neutral[key].fold == negative[key].fold
        assert neutral[key].effective_config == negative[key].effective_config
    assert len({c.case_id for c in matrix.cases}) == 16
    with pytest.raises(ValueError, match="case_budget"):
        run_experiment_matrix(snapshot, matrix_config(max_cases=1))


def test_seeded_uncertainty_has_independent_constant_fixtures_and_null_reasons() -> None:
    from packages.research.resampling import bootstrap_trade_pnl, monte_carlo_trade_order

    first = bootstrap_trade_pnl(
        (1.0, 1.0), initial_cash=100, seed=7, iterations=20, confidence_level=0.95, minimum_units=2
    )
    assert first["intervals"]["net_pnl"] == {"lower": 2.0, "median": 2.0, "upper": 2.0}
    assert first["intervals"]["total_return"] == {"lower": 0.02, "median": 0.02, "upper": 0.02}
    assert first == bootstrap_trade_pnl(
        (1.0, 1.0), initial_cash=100, seed=7, iterations=20, confidence_level=0.95, minimum_units=2
    )
    absent = bootstrap_trade_pnl(
        (), initial_cash=100, seed=7, iterations=20, confidence_level=0.95, minimum_units=2
    )
    assert absent["intervals"] is None and absent["undefined_reason"] == "insufficient_trade_units"
    order = monte_carlo_trade_order(
        (10.0, -5.0),
        initial_cash=100,
        seed=7,
        iterations=20,
        confidence_level=0.95,
        minimum_units=2,
    )
    assert order["intervals"]["total_return"] == {"lower": 0.05, "median": 0.05, "upper": 0.05}
    assert order["intervals"]["max_drawdown"]["lower"] == pytest.approx(-0.05)


def test_monthly_block_bootstrap_requires_actual_month_units() -> None:
    from datetime import date

    from packages.research.resampling import monthly_block_bootstrap

    settings = dict(
        initial_cash=100, seed=11, iterations=20, confidence_level=0.95, minimum_units=2
    )
    short = monthly_block_bootstrap((date(2025, 1, 2), date(2025, 1, 3)), (0.1, -0.1), **settings)
    assert short["undefined_reason"] == "insufficient_month_units"
    values = monthly_block_bootstrap((date(2025, 1, 2), date(2025, 2, 3)), (0.0, 0.0), **settings)
    assert values["intervals"]["total_return"] == {"lower": 0.0, "median": 0.0, "upper": 0.0}
    assert values["iterations"] == 20 and values["sample_units"] == 2


def test_registered_baseline_and_settings_cannot_silently_change() -> None:
    from packages.research.validation import load_matrix_config

    config = load_matrix_config(Path("experiments/configs/ablations.yaml"))
    baseline = next(c for c in config.matrix.costs if c.cost_id == "baseline")
    assert baseline.execution == config.execution
    altered = [c.model_dump() for c in config.matrix.costs]
    altered[0]["execution"]["entry_slippage_bps"] = 123
    with pytest.raises(ValueError, match="baseline_cost"):
        matrix_config(costs=altered)


def test_volume_ablation_is_real_but_never_labels_a_failed_filter_as_passed() -> None:
    from dataclasses import replace

    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    config = ResearchConfig.model_validate(
        yaml.safe_load(Path("experiments/configs/baseline.yaml").read_bytes())
    )
    bars = {
        s: tuple(b.model_copy(update={"volume": 1000000}) for b in bs)
        for s, bs in snapshot.feature_bars_by_symbol.items()
    }
    changed = replace(snapshot, feature_bars_by_symbol=bars)
    baseline = generate_research_signals(changed, config)
    ablated = generate_research_signals(changed, config, disabled_filters=frozenset({"volume"}))
    target = snapshot.sessions[199].date
    before = next(
        d for d in baseline.decisions if d.symbol == "QQQ" and d.decision_session == target
    )
    after = next(d for d in ablated.decisions if d.symbol == "QQQ" and d.decision_session == target)
    assert not before.accepted and "volume_ratio_filter_failed" in before.reason_codes
    assert after.accepted and "research_ablation:volume" in after.reason_codes
    assert "volume_ratio_filter_passed" not in after.reason_codes


def test_ablation_controls_are_refused_for_operational_candidates() -> None:
    from packages.data.features import compute_feature_rows
    from packages.data.models import UniverseMember
    from packages.strategy.models import EarningsBlackoutEvaluation
    from packages.strategy.signals import evaluate_candidate

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    config = ResearchConfig.model_validate(
        yaml.safe_load(Path("experiments/configs/baseline.yaml").read_bytes())
    )
    feature = compute_feature_rows(
        snapshot.feature_bars_by_symbol["QQQ"],
        benchmark_bars=snapshot.feature_bars_by_symbol["SPY"],
    )[199]
    with pytest.raises(ValueError, match="research_only"):
        evaluate_candidate(
            feature,
            universe_member=UniverseMember(
                symbol="QQQ",
                universe="live",
                as_of=feature.date,
                included=True,
                point_in_time_available=False,
                optimistic_backtest_warning=True,
            ),
            strategy_config=config.strategy,
            regime="RISK_ON",
            earnings=EarningsBlackoutEvaluation(
                status="clear",
                as_of=feature.date,
                allow_entries=True,
                reason_codes=("fixture_clear",),
            ),
            prior_high_20=160,
            disabled_filters=("volume",),
        )

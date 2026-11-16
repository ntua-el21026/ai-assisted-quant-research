"""Fold provenance reflects the full recursive prefix before configured training."""

from pathlib import Path

from packages.data.snapshots import load_dataset_snapshot
from packages.research.feature_cache import CausalFeatureCache
from packages.research.validation import build_walk_forward_folds, load_matrix_config


def test_later_configured_training_start_retains_actual_snapshot_warmup_provenance() -> None:
    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    dates = tuple(session.date for session in snapshot.sessions)
    registered = load_matrix_config(Path("experiments/configs/ablations.yaml"))
    config = type(registered).model_validate(
        {**registered.model_dump(mode="json"), "date_start": dates[1]}
    )
    folds = build_walk_forward_folds(config, dates, include_final=True)
    assert {fold.role for fold in folds} == {"rolling_oos_development", "final_evaluation"}
    assert all(fold.train_start == dates[1] for fold in folds)
    assert all(fold.warmup_start == dates[0] for fold in folds)
    assert folds[0].minimum_warmup_start == dates[1]
    assert folds[0].train_end == dates[200]
    assert folds[0].evaluation_start == dates[201]

    cache = CausalFeatureCache(
        snapshot, config.strategy.atr_period, through_date=folds[-1].evaluation_end
    )
    assert cache.dates[0] == folds[0].warmup_start
    train_end_index = cache.dates.index(folds[0].train_end)
    prefix = cache.history("SPY", train_end_index, snapshot.sessions[train_end_index].decision_at)
    assert prefix[0].date == dates[0] < config.date_start
    assert len(prefix) == 201

    # Different actual recursive history must change fold identity even when all
    # configured train/evaluation dates are identical.
    shorter_history = build_walk_forward_folds(config, dates[1:], include_final=True)
    assert [fold.evaluation_start for fold in folds] == [
        fold.evaluation_start for fold in shorter_history
    ]
    assert all(
        full.fold_id != shorter.fold_id
        for full, shorter in zip(folds, shorter_history, strict=True)
    )

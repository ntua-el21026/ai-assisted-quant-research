"""Negative news cannot release capacity for trades absent from the paired control."""

from pathlib import Path

from packages.data.snapshots import load_dataset_snapshot
from packages.research.validation import load_matrix_config, run_experiment_matrix


def test_registered_ai_fills_are_control_subsets_with_bounded_notional_exposure() -> None:
    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    config = load_matrix_config(Path("experiments/configs/ablations.yaml"))
    matrix = run_experiment_matrix(snapshot, config)
    neutral = {c.pair_id: c for c in matrix.cases if c.ai_policy == "AI_NEUTRAL"}
    changed = 0
    for negative in (c for c in matrix.cases if c.ai_policy == "AI_NEGATIVE_ONLY"):
        control = neutral[negative.pair_id]
        control_fills = {
            (e.session, e.order_id): e.quantity
            for e in control.result.order_events
            if e.action == "buy" and e.status == "filled"
        }
        for event in negative.result.order_events:
            if event.action == "buy" and event.status == "filled":
                assert (event.session, event.order_id) in control_fills
                assert event.quantity <= control_fills[(event.session, event.order_id)]
        for n, c in zip(negative.result.equity_curve, control.result.equity_curve, strict=True):
            assert n.date == c.date
            assert n.gross_exposure <= c.gross_exposure
        changed += negative.result != control.result
    assert changed > 0

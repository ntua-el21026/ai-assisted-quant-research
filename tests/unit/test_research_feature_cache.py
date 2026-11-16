"""Strict decision parity against the frozen post-correction, pre-optimization implementation."""

import importlib.util
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from packages.data.snapshots import load_dataset_snapshot
from packages.research.models import ResearchConfig


def reference_generator():
    path = Path("tests/reference/research_signals_before_r2_optimization.py")
    spec = importlib.util.spec_from_file_location("frozen_research_reference", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate_research_signals


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "delayed_current",
        "delayed_history",
        "missing_symbol",
        "missing_proxy",
        "reversed",
        "risk_off_caution",
    ],
)
def test_cached_signals_equal_every_reference_decision(change: str) -> None:
    from packages.research.feature_cache import CausalFeatureCache
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    config = ResearchConfig.model_validate(
        yaml.safe_load(Path("experiments/configs/baseline.yaml").read_bytes())
    )
    bars = dict(snapshot.feature_bars_by_symbol)
    availability = dict(snapshot.availability_by_key)
    if change == "delayed_current":
        s = snapshot.sessions[199]
        availability[("QQQ", s.date)] = snapshot.sessions[201].decision_at
    elif change == "delayed_history":
        s = snapshot.sessions[5]
        availability[("SPY", s.date)] = snapshot.sessions[201].decision_at
    elif change in ("missing_symbol", "missing_proxy"):
        symbol = "QQQ" if change == "missing_symbol" else "SPY"
        bars[symbol] = tuple(b for b in bars[symbol] if b.date != snapshot.sessions[5].date)
    elif change == "reversed":
        bars = dict(reversed(tuple(bars.items())))
    elif change == "risk_off_caution":
        proxy = list(bars["SPY"])
        for i, c in ((199, 80.0), (200, 110.0), (201, 80.0), (202, 110.0)):
            proxy[i] = proxy[i].model_copy(
                update={"open": c, "high": c + 1, "low": c - 1, "close": c}
            )
        bars["SPY"] = tuple(proxy)
        config = config.model_copy(
            update={
                "regime": config.regime.model_copy(
                    update={
                        "risk_off_confirm_closes": 1,
                        "risk_on_confirm_closes": 1,
                        "rv20_risk_on_max": 10.0,
                        "rv20_risk_off_min": 20.0,
                    }
                )
            }
        )
    snapshot = replace(snapshot, feature_bars_by_symbol=bars, availability_by_key=availability)
    expected = reference_generator()(snapshot, config)
    cache = CausalFeatureCache(snapshot, config.strategy.atr_period, through_date=config.date_end)
    actual = generate_research_signals(snapshot, config, feature_cache=cache)
    assert actual == expected
    assert actual.model_dump_json() == expected.model_dump_json()


def test_future_mutation_and_delayed_availability_leave_cached_prefix_unchanged() -> None:
    from packages.research.feature_cache import CausalFeatureCache
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    config = ResearchConfig.model_validate(
        yaml.safe_load(Path("experiments/configs/baseline.yaml").read_bytes())
    )
    cutoff = snapshot.sessions[201].date
    changed = replace(
        snapshot,
        feature_bars_by_symbol={
            s: tuple(
                b
                if b.date <= cutoff
                else b.model_copy(
                    update={"open": 999.0, "high": 1000.0, "low": 998.0, "close": 999.0}
                )
                for b in bars
            )
            for s, bars in snapshot.feature_bars_by_symbol.items()
        },
    )
    first = generate_research_signals(
        snapshot,
        config,
        feature_cache=CausalFeatureCache(
            snapshot, config.strategy.atr_period, through_date=config.date_end
        ),
    )
    second = generate_research_signals(
        changed,
        config,
        feature_cache=CausalFeatureCache(
            changed, config.strategy.atr_period, through_date=config.date_end
        ),
    )
    assert tuple(d for d in first.decisions if d.decision_session <= cutoff) == tuple(
        d for d in second.decisions if d.decision_session <= cutoff
    )


def test_cache_enforces_snapshot_period_and_end_date_identity() -> None:
    from packages.research.feature_cache import CausalFeatureCache
    from packages.research.signals import generate_research_signals

    snapshot = load_dataset_snapshot(Path("tests/fixtures/market_snapshot/manifest.json"))
    config = ResearchConfig.model_validate(
        yaml.safe_load(Path("experiments/configs/baseline.yaml").read_bytes())
    )
    short = CausalFeatureCache(
        snapshot, config.strategy.atr_period, through_date=snapshot.sessions[200].date
    )
    with pytest.raises(ValueError, match="cache_range"):
        generate_research_signals(snapshot, config, feature_cache=short)
    cache = CausalFeatureCache(snapshot, config.strategy.atr_period, through_date=config.date_end)
    with pytest.raises(ValueError, match="cache_snapshot"):
        generate_research_signals(replace(snapshot), config, feature_cache=cache)

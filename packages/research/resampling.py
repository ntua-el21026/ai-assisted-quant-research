"""Seeded conditional resampling of realized synthetic/historical simulation records.

These distributions condition on the observed path. They are not independent future-market
confidence guarantees, strategy reruns, or a correction for multiple hypothesis testing.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from datetime import date
from typing import Any


def _validate(
    initial_cash: float,
    iterations: int,
    confidence_level: float,
    minimum_units: int,
    values: Sequence[float],
) -> None:
    if (
        not math.isfinite(initial_cash)
        or initial_cash <= 0
        or not 1 <= iterations <= 100000
        or not 0 < confidence_level < 1
        or minimum_units < 2
        or any(not math.isfinite(v) for v in values)
    ):
        raise ValueError("invalid_resampling_configuration_or_values")


def _path_metrics(pnls: Sequence[float], initial: float) -> dict[str, float]:
    equity = peak = initial
    drawdown = 0.0
    for pnl in pnls:
        equity = max(0.0, equity + pnl) if equity > 0 else 0.0
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    return {
        "net_pnl": equity - initial,
        "total_return": (equity - initial) / initial,
        "max_drawdown": drawdown,
    }


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _summary(
    method: str,
    samples: Sequence[dict[str, float]],
    *,
    seed: int,
    iterations: int,
    confidence_level: float,
    units: int,
    undefined: str | None = None,
) -> dict[str, Any]:
    alpha = (1 - confidence_level) / 2
    intervals = (
        {
            name: {
                "lower": _quantile([s[name] for s in samples], alpha),
                "median": _quantile([s[name] for s in samples], 0.5),
                "upper": _quantile([s[name] for s in samples], 1 - alpha),
            }
            for name in samples[0]
        }
        if samples
        else None
    )
    return {
        "schema_version": "conditional-resampling/v1",
        "method": method,
        "seed": seed,
        "iterations": iterations,
        "confidence_level": confidence_level,
        "sample_units": units,
        "intervals": intervals,
        "undefined_reason": undefined,
        "assumptions": [
            "conditional_on_observed_path_not_future_guarantee",
            "linear_interpolated_percentile_interval",
            "small_samples_and_multiple_comparisons_limit_inference",
            "closed_trade_sequences_exclude_terminal_unrealized_pnl",
            "zero_equity_is_absorbing_no_negative_capital",
        ],
    }


def bootstrap_trade_pnl(
    pnls: tuple[float, ...],
    *,
    initial_cash: float,
    seed: int,
    iterations: int,
    confidence_level: float,
    minimum_units: int = 2,
) -> dict[str, Any]:
    _validate(initial_cash, iterations, confidence_level, minimum_units, pnls)
    rng = random.Random(seed)
    samples = (
        [
            _path_metrics(tuple(rng.choice(pnls) for _ in pnls), initial_cash)
            for _ in range(iterations)
        ]
        if len(pnls) >= minimum_units
        else []
    )
    return _summary(
        "closed_trade_pnl_bootstrap",
        samples,
        seed=seed,
        iterations=iterations,
        confidence_level=confidence_level,
        units=len(pnls),
        undefined=None if samples else "insufficient_trade_units",
    )


def monte_carlo_trade_order(
    pnls: tuple[float, ...],
    *,
    initial_cash: float,
    seed: int,
    iterations: int,
    confidence_level: float,
    minimum_units: int = 2,
) -> dict[str, Any]:
    _validate(initial_cash, iterations, confidence_level, minimum_units, pnls)
    rng = random.Random(seed)
    samples = []
    if len(pnls) >= minimum_units:
        for _ in range(iterations):
            order = list(pnls)
            rng.shuffle(order)
            samples.append(_path_metrics(order, initial_cash))
    return _summary(
        "closed_trade_order_permutation",
        samples,
        seed=seed,
        iterations=iterations,
        confidence_level=confidence_level,
        units=len(pnls),
        undefined=None if samples else "insufficient_trade_units",
    )


def monthly_block_bootstrap(
    dates: tuple[date, ...],
    returns: tuple[float, ...],
    *,
    initial_cash: float,
    seed: int,
    iterations: int,
    confidence_level: float,
    minimum_units: int = 2,
) -> dict[str, Any]:
    _validate(initial_cash, iterations, confidence_level, minimum_units, returns)
    if (
        len(dates) != len(returns)
        or dates != tuple(sorted(set(dates)))
        or any(r < -1 for r in returns)
    ):
        raise ValueError("invalid_monthly_return_calendar")
    months: dict[tuple[int, int], list[float]] = {}
    for d, r in zip(dates, returns, strict=True):
        months.setdefault((d.year, d.month), []).append(r)
    blocks = tuple(tuple(v) for v in months.values())
    samples = []
    rng = random.Random(seed)
    if len(blocks) >= minimum_units:
        for _ in range(iterations):
            selected: list[float] = []
            while len(selected) < len(returns):
                selected.extend(rng.choice(blocks))
            equity = peak = initial_cash
            drawdown = 0.0
            for r in selected[: len(returns)]:
                equity *= 1 + r
                if not math.isfinite(equity):
                    return _summary(
                        "calendar_month_return_blocks",
                        [],
                        seed=seed,
                        iterations=iterations,
                        confidence_level=confidence_level,
                        units=len(blocks),
                        undefined="numerical_overflow",
                    )
                peak = max(peak, equity)
                drawdown = min(drawdown, equity / peak - 1)
            samples.append(
                {
                    "net_pnl": equity - initial_cash,
                    "total_return": (equity - initial_cash) / initial_cash,
                    "max_drawdown": drawdown,
                }
            )
    report = _summary(
        "calendar_month_return_blocks",
        samples,
        seed=seed,
        iterations=iterations,
        confidence_level=confidence_level,
        units=len(blocks),
        undefined=None if samples else "insufficient_month_units",
    )
    report["assumptions"] += [
        "within_month_order_preserved",
        "observed_partial_calendar_months_are_blocks",
        "blocks_sampled_with_replacement_last_block_truncated_to_original_session_count",
    ]
    return report

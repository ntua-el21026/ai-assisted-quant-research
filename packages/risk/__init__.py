"""Deterministic risk checks, sizing, and kill-switch contracts."""

from importlib import import_module
from typing import TYPE_CHECKING

from packages.risk.checks import evaluate_new_risk_order
from packages.risk.kill_switch import (
    new_risk_allowed,
    pause_all_autonomous_actions,
    pause_new_risk,
    request_force_flat,
    require_manual_review,
    risk_reducing_exits_allowed,
    running_state,
)
from packages.risk.models import (
    KillSwitchSnapshot,
    NewRiskOrderInput,
    PositionSizingInput,
    PositionSizingResult,
    RiskAssessment,
    RiskCheckResult,
)
from packages.risk.sizing import calculate_position_size

__all__ = [
    "KillSwitchSnapshot",
    "NewRiskOrderInput",
    "PositionSizingInput",
    "PositionSizingResult",
    "RiskAssessment",
    "RiskCheckResult",
    "ShortAccountSnapshot",
    "ShortAssetSnapshot",
    "ShortEntryRiskInput",
    "ShortEntryRiskResult",
    "calculate_position_size",
    "evaluate_new_risk_order",
    "evaluate_short_entry_risk",
    "new_risk_allowed",
    "pause_all_autonomous_actions",
    "pause_new_risk",
    "request_force_flat",
    "require_manual_review",
    "risk_reducing_exits_allowed",
    "running_state",
]


if TYPE_CHECKING:
    from packages.risk.shorts import (
        ShortAccountSnapshot,
        ShortAssetSnapshot,
        ShortEntryRiskInput,
        ShortEntryRiskResult,
        evaluate_short_entry_risk,
    )


def __getattr__(name: str) -> object:
    # Optional legacy short simulation imports execution/broker contracts. Keep those
    # dependencies out of the canonical long-only research import path.
    if name in {
        "ShortAccountSnapshot",
        "ShortAssetSnapshot",
        "ShortEntryRiskInput",
        "ShortEntryRiskResult",
        "evaluate_short_entry_risk",
    }:
        value: object = getattr(import_module("packages.risk.shorts"), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

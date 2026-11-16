"""Stable, local snapshot quality errors and explicit calendar checks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from packages.data.models import AdjustedDailyBar


class SnapshotError(ValueError):
    """A stable error code precedes diagnostic details."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def check_missing_sessions(
    bars: Mapping[str, Sequence[AdjustedDailyBar]],
    sessions: Sequence[date],
    policy: str,
) -> tuple[str, ...]:
    warnings: list[str] = []
    for symbol in sorted(bars):
        observed = {bar.date for bar in bars[symbol]}
        for session in sessions:
            if session not in observed:
                message = f"missing_session:{symbol}:{session}"
                if policy == "reject":
                    raise SnapshotError("missing_session", message)
                warnings.append(message)
    return tuple(warnings)

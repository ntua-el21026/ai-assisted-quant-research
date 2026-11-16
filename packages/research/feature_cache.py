"""Reusable causal indicator arrays with explicit prefix completeness/availability gates.

The existing indicator functions are forward recurrences or trailing windows. Precomputation
changes their invocation count, not the observations on which any row depends. No row can be
consumed before every required prefix observation is available at that decision cutoff.
"""

from __future__ import annotations

from datetime import date, datetime

from packages.data.features import compute_feature_rows
from packages.data.models import AdjustedDailyBar, FeatureRow
from packages.data.snapshots import DatasetSnapshot
from packages.strategy.models import RegimeObservation
from packages.strategy.regime import realized_volatility_20


class CausalFeatureCache:
    def __init__(
        self,
        snapshot: DatasetSnapshot,
        atr_period: int,
        *,
        through_date: date,
        proxy_symbol: str = "SPY",
    ) -> None:
        self.snapshot = snapshot
        self.atr_period = atr_period
        self.through_date = through_date
        self.proxy_symbol = proxy_symbol
        self.sessions = tuple(s for s in snapshot.sessions if s.date <= through_date)
        self.dates = tuple(s.date for s in self.sessions)
        self._all_bars = {
            s: tuple(b for b in bars if b.date <= through_date)
            for s, bars in snapshot.feature_bars_by_symbol.items()
        }
        self._prefix: dict[str, tuple[AdjustedDailyBar, ...]] = {}
        self._available: dict[str, tuple[datetime, ...]] = {}
        self._signal_features: dict[str, tuple[FeatureRow, ...]] = {}
        self._exit_features: dict[str, tuple[FeatureRow, ...]] = {}
        for symbol, bars in self._all_bars.items():
            prefix = []
            latest: list[datetime] = []
            for expected, bar in zip(self.dates, bars, strict=False):
                if expected != bar.date:
                    break
                prefix.append(bar)
                stamp = snapshot.availability_by_key[(symbol, bar.date)]
                latest.append(max(stamp, latest[-1]) if latest else stamp)
            self._prefix[symbol] = tuple(prefix)
            self._available[symbol] = tuple(latest)
        proxy = self._prefix.get(proxy_symbol, ())
        for symbol, bars in self._prefix.items():
            count = min(len(bars), len(proxy))
            features = (
                compute_feature_rows(
                    bars[:count], benchmark_bars=proxy[:count], atr_window=atr_period
                )
                if count
                else ()
            )
            self._signal_features[symbol] = features
            self._exit_features[symbol] = (
                features
                if count == len(bars)
                else compute_feature_rows(bars, atr_window=atr_period)
            )
        proxy_features = self._exit_features.get(proxy_symbol, ())
        volatility = realized_volatility_20([b.close for b in proxy]) if proxy else ()
        self.regime_observations = tuple(
            RegimeObservation(
                symbol=proxy_symbol,
                date=f.date,
                close=f.close,
                sma_fast=f.sma_50,
                sma_slow=f.sma_200,
                rv20=rv,
            )
            for f, rv in zip(proxy_features, volatility, strict=True)
        )

    def validate(
        self, snapshot: DatasetSnapshot, atr_period: int, through_date: date, proxy_symbol: str
    ) -> None:
        if snapshot is not self.snapshot:
            raise ValueError("cache_snapshot_mismatch")
        if atr_period != self.atr_period or proxy_symbol != self.proxy_symbol:
            raise ValueError("cache_period_or_proxy_mismatch")
        if through_date > self.through_date:
            raise ValueError("cache_range_insufficient")

    def complete(self, symbol: str, index: int, cutoff: datetime) -> bool:
        stamps = self._available.get(symbol, ())
        return index < len(stamps) and stamps[index] <= cutoff

    def history(self, symbol: str, index: int, cutoff: datetime) -> tuple[AdjustedDailyBar, ...]:
        if self.complete(symbol, index, cutoff):
            return self._prefix[symbol][: index + 1]
        session = self.dates[index]
        return tuple(
            b
            for b in self._all_bars.get(symbol, ())
            if b.date <= session and self.snapshot.availability_by_key[(symbol, b.date)] <= cutoff
        )

    def features(
        self, symbol: str, index: int, cutoff: datetime, *, for_exit: bool = False
    ) -> tuple[FeatureRow, ...]:
        if not self.complete(symbol, index, cutoff):
            return ()
        if not for_exit and not self.complete(self.proxy_symbol, index, cutoff):
            return ()
        rows = (self._exit_features if for_exit else self._signal_features).get(symbol, ())
        return rows[: index + 1]

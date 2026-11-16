"""Measure declared synthetic scales offline; setup is excluded from measured core execution.

All bars are original arithmetic data on an artificial weekday calendar, not market observations.
The generated source manifest/config and results are ignored local research inputs and evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from packages.backtesting.execution import run_causal_backtest
from packages.data.snapshots import DatasetSnapshot, load_dataset_snapshot
from packages.research.models import ResearchConfig


def prepare_synthetic_scale(root: Path, sessions: int, symbols: int) -> tuple[Path, Path]:
    if sessions < 201 or symbols < 2 or symbols > 50:
        raise ValueError("benchmark requires >=201 sessions and 2..50 synthetic symbols")
    root.mkdir(parents=True, exist_ok=False)
    dates: list[date] = []
    current = date(2012, 1, 2)
    while len(dates) < sessions:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    calendar = []
    zone = ZoneInfo("America/New_York")
    for d in dates:
        calendar.append(
            {
                "date": d.isoformat(),
                "open_at": datetime(d.year, d.month, d.day, 9, 30, tzinfo=zone)
                .astimezone(UTC)
                .isoformat(),
                "close_at": datetime(d.year, d.month, d.day, 16, tzinfo=zone)
                .astimezone(UTC)
                .isoformat(),
            }
        )
    names = ("SPY", *(f"SYN{i:03d}" for i in range(1, symbols)))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("symbol", "date", "open", "high", "low", "close", "volume", "available_at"))
    for number, symbol in enumerate(names):
        for i, s in enumerate(calendar):
            close = (
                (100 + 0.015 * i)
                if number == 0
                else (100 + number + 0.025 * i + (4 if i % 61 >= 56 else 0))
            )
            writer.writerow(
                (
                    symbol,
                    s["date"],
                    f"{close:.6f}",
                    f"{close + 1:.6f}",
                    f"{close - 1:.6f}",
                    f"{close:.6f}",
                    3000000 if i % 61 == 56 else 1000000,
                    (datetime.fromisoformat(s["close_at"]) + timedelta(seconds=30)).isoformat(),
                )
            )
    raw = stream.getvalue().encode()
    (root / "bars.csv").write_bytes(raw)
    template = json.loads(Path("tests/fixtures/market_snapshot/manifest.json").read_bytes())
    template.update(
        dataset_id=f"synthetic-scale-{sessions}x{symbols}-v1",
        source="Original arithmetic synthetic scalability fixture/v1; no market observations",
        coverage_start=dates[0].isoformat(),
        coverage_end=dates[-1].isoformat(),
        frozen_at=(
            datetime.fromisoformat(calendar[-1]["close_at"]) + timedelta(days=1)
        ).isoformat(),
        symbols=list(names),
        sessions=calendar,
        universe_source="Artificial labels and fixed ETF-like metadata, not historical securities",
        files=[
            {
                "path": "bars.csv",
                "format": "csv",
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        ],
    )
    manifest = json.dumps(template, sort_keys=True, indent=2) + "\n"
    (root / "manifest.json").write_text(manifest)
    config = yaml.safe_load(Path("experiments/configs/baseline.yaml").read_bytes())
    config.update(
        experiment_id=f"synthetic-scale-{sessions}x{symbols}",
        hypothesis="Engineering scalability and deterministic parity only; no market inference",
        dataset_manifest_sha256=hashlib.sha256(manifest.encode()).hexdigest(),
        date_start=dates[0].isoformat(),
        date_end=dates[-1].isoformat(),
        approved_symbols=list(names),
        etf_symbols=list(names),
        sectors={s: f"synthetic-sector-{i % 4}" for i, s in enumerate(names)},
    )
    (root / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=True))
    return root / "manifest.json", root / "config.yaml"


def benchmark(
    snapshot: DatasetSnapshot, config: ResearchConfig, repeats: int, implementation: str
) -> dict[str, object]:
    from packages.research import signals as module

    if implementation == "reference":
        source = Path("tests/reference/research_signals_before_r2_optimization.py")
        spec = importlib.util.spec_from_file_location("frozen_performance_reference", source)
        if spec is None or spec.loader is None:
            raise ValueError("missing_frozen_reference")
        reference = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reference)
        generator = reference.generate_research_signals
    else:
        source = Path("packages/research/signals.py")
        generator = module.generate_research_signals
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    script_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    core_times: list[float] = []
    records = []
    for attempt in range(repeats):
        start = time.perf_counter()
        signals = generator(snapshot, config)
        after_signals = time.perf_counter()
        result = run_causal_backtest(snapshot, signals, config)
        end = time.perf_counter()
        record = {
            "attempt": attempt,
            "signal_seconds": after_signals - start,
            "simulation_seconds": end - after_signals,
            "core_seconds": end - start,
            "decisions": len(signals.decisions),
            "trades": len(result.trades),
            "decision_sha256": hashlib.sha256(signals.model_dump_json().encode()).hexdigest(),
        }
        records.append(record)
        core_times.append(end - start)
        print(json.dumps(record, sort_keys=True), flush=True)
    return {
        "schema_version": "research-performance/v1",
        "kind": "synthetic_engineering_only",
        "implementation": implementation,
        "generator_source_sha256": source_sha256,
        "code_revision": revision,
        "sessions": len(snapshot.sessions),
        "symbols": len(snapshot.feature_bars_by_symbol),
        "repeats": repeats,
        "observations": records,
        "median_core_seconds": statistics.median(core_times),
        "setup_and_artifact_export_excluded": True,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "dataset_manifest_sha256": snapshot.manifest_sha256,
        "source_script_sha256": script_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, required=True)
    parser.add_argument("--symbols", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--implementation", choices=("reference", "current"), default="current")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    manifest, config_path = prepare_synthetic_scale(
        args.output / "input", args.sessions, args.symbols
    )
    snapshot = load_dataset_snapshot(manifest)
    config = ResearchConfig.model_validate(yaml.safe_load(config_path.read_bytes()))
    result = benchmark(snapshot, config, args.repeats, args.implementation)
    (args.output / "performance.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n"
    )
    print("Saved", args.output / "performance.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

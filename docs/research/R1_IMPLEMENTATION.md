# R1 implementation and verification contract

R1 implements Tasks 1–4 of the [approved plan](../superpowers/plans/2026-11-16-ai-assisted-quant-research.md).
R2–R4 remain pending. This synthetic demonstration does not establish historical-market
performance, AI benefit, or local Temporal recovery correctness.

The typed interfaces are `load_dataset_snapshot(Path) -> DatasetSnapshot`,
`generate_research_signals(snapshot, ResearchConfig) -> ResearchSignalSet`,
`run_causal_backtest(snapshot, signals, config) -> BacktestResult`, and
`run_research(config_path, dataset_manifest_path, output_dir) -> ExperimentRunSummary`.
The causal backtester lives in `packages.backtesting.execution`.

## Data and decisions

The [snapshot format](../../datasets/README.md) specifies integrity, licensing, availability
and calendar checks. The explicit calendar is an input, not inferred from observed rows.
Both series use raw prices and require declared action/dividend-free coverage. Unsupported
mixed/adjusted prices and corporate-action policies fail validation. There is no acquisition
or missing-input download fallback.

The adapter traverses calendar sessions chronologically. It calls the existing feature
function only with bars available by close plus one minute. A complete calendar prefix is
required for features and relative-strength alignment; a missing/delayed observation blocks
that prefix until availability is restored. Two hundred observations are required for
SMA200. Breakouts compare against prior bars, excluding the current high. Relative-strength
ranks use only approved symbols with available data at that cutoff. Fixed universe/sector/ETF
metadata are declared assumptions, not reconstructed point-in-time membership.

Existing candidate/regime/earnings helpers and position sizing are reused. Unknown equity
earnings block entries; ETF exemptions are explicit. Earnings announcements have availability
timestamps. Decision quantity uses initial capital and the as-of regime multiplier; it never
uses a future fill price or future portfolio state. Actual portfolio capacity is checked at
execution. Accepted means eligible for simulation, not guaranteed filled. Every evaluated
symbol/session has an accepted or rejected decision with reasons.

The simulation risk adapter reuses numerical checks for positions, gross/deployable/sector
exposure, cash buffer, protective stops, risk per trade and daily/weekly/monthly loss limits.
Operational broker/autonomy/Temporal gates retain their existing semantics and are not
asserted by simulation. No safety flag is enabled. Legacy short exports are loaded lazily so
the offline long-only import path does not import broker adapters.

## Execution and compatibility

Orders execute at the exact next declared calendar session open, never an observed signal
close. Missing next-session prices are recorded unfilled with no silent later fill. Orders
outside the evaluation range and final-session decisions remain explicitly unfilled.

1. Opening gap stops and pending full-position exits execute first.
2. Opening buys execute in `(symbol, decision_id)` order. Duplicate IDs or same-symbol/action/
   eligible-session requests are rejected; held symbols and same-session reentry are blocked.
3. Intraday low-triggered stops execute after opening buys. Their proceeds cannot finance
   entries at that earlier open. A newly filled position can stop out during the same session.
4. Close marks establish equity. Existing exit and trailing-stop helpers use as-of history;
   resulting routine exits and stop changes become effective in the next session.

A stop crossed by the opening gap uses that open as its base; an intraday stop uses its stop
level. Adverse entry/routine/stop slippage and fees on slipped notional are explicit and
validated. Stops and routine exits use different cost settings. There are no targets, so
intraday target/stop ordering is not asserted. Execution is full-or-none with integer shares;
partial exit quantities are explicitly rejected. Liquidity participation and partial fills
are not modeled. Missing held-position prices fail the run instead of inventing a mark.

Cash, cost basis, realized/net-entry unrealized P&L and equity reconcile. Terminal open
positions remain marked and reported, with no artificial liquidation. Closed trade return
uses entry notional as its denominator, matching the existing trade contract. Risk limits
constrain new entries; passive exposure drift can occur after entry.

`run_backtest(BacktestInput, ...)` remains unchanged: its explicit signals use same-session
closes, sells close the whole position, and missing bars/duplicate entries are silently
ignored. The R1 runner exclusively uses `run_causal_backtest`. `BacktestResult` gains defaulted
`open_positions`, `order_events` and `warnings`, preserving old constructors and results.
Legacy numerical tests remain intact.

R1 reports total return, signed maximum drawdown, average exposure and closed-trade metrics
through existing helpers, with an initial-cash first session. Research Sharpe and Sortino are
explicitly null/deferred: correcting definitions, annualization and benchmarks belongs to
R2 Task 5. Comparison references and benchmark equity are likewise explicitly unavailable.
Zero-trade/zero-denominator values have null reasons; zero-return cash paths remain valid.

## Offline CLI and artifacts

```bash
uv sync --locked --group dev
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --output results/r1-example
```

The configuration includes its expected dataset-manifest SHA-256, frozen strategy/regime/risk
parameters, calendar date range, costs, fixed metadata and seed. Unknown configuration fields
are rejected; provider configuration and credentials are not consumed. Setup can fetch pinned
Python dependencies; the research command itself performs only local reads and writes.

The output path must be new. It contains `manifest.json`, `config.snapshot.json`, `trades.csv`,
`equity.csv`, `metrics.json`, `comparisons.json`, `report.md`, `hashes.json` and `runtime.json`.
The CSV named `trades.csv` is the complete order-event stream, including strategy rejections,
accepted fills, exit fills and unfilled orders. Closed round-trip P&L and terminal positions
are available in metrics; each fill includes decision/session timestamps, quantity, base/fill
price, fee, modeled slippage and reason. Results are generated and ignored, not hand-edited.

JSON uses sorted keys, UTF-8, finite numbers and fixed newlines; CSV uses fixed columns/order
and LF. Run identity hashes effective/input configuration, snapshot manifest, complete Python
source fingerprints, code revision and numerical/dependency versions. Relative source names
and file hashes identify working source even before a commit; the revision alone must not be
interpreted as proof of a clean tree. No elapsed time, host path or start timestamp enters
reproducible artifacts. Host/platform/start/duration/executable metadata lives exclusively in
`runtime.json`, explicitly excluded from result parity. Runtime-only differences cannot alter
the deterministic run ID.

`manifest.json` hashes the other required deterministic artifacts; `hashes.json` also covers
the manifest. It excludes itself and runtime metadata to avoid circular hashing. The CLI
returns the SHA-256 of the canonical complete artifact-hash mapping. Stage writes and fsync
precede a same-filesystem directory rename; a sibling exclusive lock prevents cooperating
writers from publishing to the same destination. Existing destinations are refused, including
symlinks. Exceptions before publication remove staging and lock files. Abrupt process death
may leave hidden staging/lock evidence for inspection; automatic crash recovery belongs to R3.

Independent accounting fixtures use a USD absolute tolerance of `1e-8`; canonical serialization
retains Python binary64 values. The reference input has 630 synthetic rows and an intentionally
non-exchange weekday calendar. Its single closed round trip is a software check, not a market
study. Interest, taxes, market impact, delistings, corporate actions and cash dividends are not
modeled. All current baseline values are disclosed starting assumptions, not tuned optima.

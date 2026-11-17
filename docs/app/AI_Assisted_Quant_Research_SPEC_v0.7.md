# AI-Assisted Quantitative Trading Research Framework

- **Specification:** v0.7 (research-scope transition)
- **Status:** R1–R4-B engineering reviewed; R4-B.2 targeted field resolution verified, independent acceptance pending; historical strategy research/release blocked
- **Owner:** Michail Athanasios Peppas
- **Target audience:** MSc Computer Science, Data Science, AI/ML and quantitative-finance reviewers
- **Execution environment:** Local, offline-first Python research software; no deployment

## 1. Authority and migration

This document is the **current source of truth** for the research framework's intended behavior, architecture, non-goals and completion criteria. It supersedes the operational objectives of [`Autonomous_AI_Trading_Bot_SPEC_v0.6.md`](Autonomous_AI_Trading_Bot_SPEC_v0.6.md), which remains unchanged as a historical specification. Earlier milestone reports, broker evidence, runbooks, deployment manifests and frozen-validation records likewise remain historical. Their old `GO`/`NO_GO` outcomes do not establish v0.7 research completeness.

The v0.7 change is a **product-scope change**. R1–R2 now implement the offline research
pipeline, and R3 adds optional local Temporal/SQLite reliability. The owner identifies
`60dd250` as the independently reviewed R1–R3 baseline. R4-A adds a separately authorized,
synthetic-only historical-data/action foundation; [its contracts](../research/R4A_IMPLEMENTATION.md)
and [verification](../research/R4A_VERIFICATION.md) do not establish empirical acceptance.
The owner independently accepted R4-A at `0dd0875` for synthetic engineering.
Separately authorized [R4-B](../research/R4B_IMPLEMENTATION.md) implements finite private
IEX acquisition and offline candidate qualification; its preflight stopped on an
unsupported special-dividend classification. No pilot, larger dataset or historical
strategy evaluation followed. Strict v2 admission, registered research hypotheses,
periods and numerical acceptance criteria are preserved.
R4-B engineering was independently accepted at `a6d3a09`. The separately authorized
[R4-B.1 correction](../research/R4B1_IMPLEMENTATION.md) distinguishes economic action
scope and enforces aggregate limits. It acquires the original IEX pilot with complete
bar coverage while preserving failed action/scientific gates. No larger dataset or
historical strategy experiment follows; strict v2 admission and this research protocol
remain unchanged.
Historical studies and overall release remain incomplete. See
[the architecture](../research/ARCHITECTURE.md), [the research protocol](../research/RESEARCH_PROTOCOL.md),
[R3 verification](../research/R3_VERIFICATION.md) and [the implementation plan](../superpowers/plans/2026-11-16-ai-assisted-quant-research.md).

[R4-B.2](../research/R4B2_DATA_QUALIFICATION.md) audits the immutable pilot without
new authenticated acquisition. A separately versioned, optional independent-evidence
receipt resolves three SPY currency fields; all remaining gates and original source
values are preserved. Pilot admission and R4-C remain blocked. Proxy-execution and
alternative-study options are proposals requiring separate review, not changes to this
specification's execution timing, calendar, hypotheses or empirical acceptance criteria.

For future work, this specification overrides contradictory requirements in older docs. Existing safety invariants remain binding unless this document explicitly tightens them. No new functionality is authorized merely because it appears in a legacy roadmap.

## 2. Mission and research questions

Build a **complete, reproducible research framework** for US equity/ETF end-of-day strategies, bounded AI-assisted news-risk analysis and local reliability experiments. The deliverable is inspectable research software, not a trading service or a performance promise.

- **RQ1 — Strategy robustness:** How do deterministic regime, trend, breakout, relative-strength and risk filters behave across historical periods and realistic cost assumptions versus transparent benchmarks?
- **RQ2 — Bounded AI influence:** Does a timestamp-valid, negative-only AI/news risk overlay change risk-adjusted outcomes relative to the same deterministic decisions with AI forced neutral? Report both improvements and deterioration.
- **RQ3 — Systems correctness:** Can locally orchestrated research jobs and simulated execution preserve idempotency, audit history and recoverable state under injected failures and replay?

The study must distinguish observations, assumptions, limitations and inferences. A negative or statistically inconclusive result is valid; positive backtest results are not proof of future profitability.

## 3. Scope and non-goals

### Required

1. Deterministic, offline execution from explicit historical data snapshots and experiment configuration.
2. A connected path from data normalization and features to candidate selection, bounded risk decisions, simulated order/fill accounting, portfolio equity and recorded results.
3. Correct, documented event-time and decision-availability semantics, with no look-ahead leakage.
4. Transparent baselines, time-aware development/out-of-sample splits, walk-forward evaluation, transaction-cost sensitivity, uncertainty analyses and ablations.
5. An optional offline AI overlay driven by frozen, provenance-bearing news/model outputs, including neutral and failure controls.
6. A compact local systems track: meaningful Temporal SDK workflow/replay tests, audit persistence, idempotency and injected failure recovery. It need not recreate the complete production workflow architecture.
7. Machine-readable artifacts, a technical report, local visualizations, reproducibility instructions and automated verification.

### Explicit non-goals

- **No deployment** to Vercel, a VPS, a managed worker, a live API or a production database.
- **No live or paper broker writes** from the v0.7 research pipeline. Existing historical paper-broker experiments must not be repeated as part of research completion.
- No autonomous broker execution, account connection requirement, live-trading readiness, Level 4/5 promotion, 56-day broker-connected validation clock or minimum number of real paper trades.
- No production Temporal Cloud schedules, secret manager, continuously running execution service or operational control dashboard.
- No promise of profits, optimized performance thresholds, automated strategy mutation, unbounded LLM decisions, HFT, options, futures, leverage or live short-selling.
- No mandatory large neural predictive model; existing bounded LLM news analysis is a research variable rather than an execution authority.

### Hard safety boundaries

- Research commands run with **no broker credentials**, do not import a broker-write runtime as a side effect, and never submit, cancel or replace broker orders.
- No AI component can construct or dispatch real orders, increase deterministic position size, disable stops or modify risk limits. Invalid or missing AI outputs produce a recorded neutral fallback.
- External provider access is never required for default tests or to replay a published experiment. Optional read-only ingestion or model-output collection must be a separate, explicitly invoked preparation command, with no implicit network calls from the canonical experiment runner.
- Do not print, save or commit API keys, account identifiers, private broker payloads or privileged URLs.
- Existing paper/live configuration flags remain disabled; do not relax them as part of the research migration.

## 4. Intended architecture

The canonical research path is:

1. **Dataset snapshot:** validate schema, provenance, timestamp, symbols, calendar, price basis and integrity hashes.
2. **Feature generation:** compute causal indicators using observations available at the decision timestamp.
3. **Candidate/decision engine:** apply the existing deterministic strategy/regime/risk logic and record rejected candidates as well as accepted decisions.
4. **Optional AI overlay:** apply frozen, as-of-valid and non-increasing AI news-risk information; otherwise use neutral.
5. **Simulator:** execute only modeled orders under explicit next-session timing, costs, fills, stops and portfolio limits.
6. **Evaluation:** benchmark equity and trades across designated splits, ablations and sensitivity scenarios.
7. **Artifacts:** write an auditable manifest, results, data-quality warnings, research tables, plots and report locally.

The separate **systems track** exercises local Temporal workflows, simulated side effects, ledger persistence, replay and failure recovery; it may call the deterministic research core but must not communicate with real broker or cloud services. The research core must remain usable without a Temporal server.

Use the existing Python 3.12+ and `uv.lock` ecosystem, established `packages/` layout, Pytest, SQLite repositories and local Temporal SDK test environment. Add dependencies only when justified by a concrete tested requirement. Preserve existing public APIs or provide explicit migration tests.

## 5. Historical data and temporal correctness

### Snapshot contract

Every research dataset needs a versioned manifest containing at least:

- Dataset ID, provider/source, retrieval or freeze timestamp, coverage dates, symbol list and market/time-zone convention.
- File paths, format, size and SHA-256 digest; normalization version and required OHLCV fields.
- Price basis (raw tradable prices versus adjusted research prices), corporate-action/dividend policy, missing-data policy and trading-calendar assumptions.
- Universe-membership source, known survivorship/selection bias and any data-provider licensing or redistribution restriction.
- Validation result for sorted, unique (symbol, session) rows, prices/volumes, missing sessions and unexpected gaps.

Default tests must include a small, license-safe synthetic fixture. Real historical input may come from a user-provided or separately downloaded snapshot. Do not commit redistributable data without permission under its actual license. A reproducible public example must be available even when private/licensed historical inputs are absent.

### Causal trading semantics

- Indicators and news may use only data available at the recorded decision time. Distinguish event/publication time, provider availability and decision time when relevant.
- An EOD signal based on session `t` closing data cannot be executed at the same session's already-observed close. The research default fills **no earlier than the next eligible session**, with an explicit, tested price/ordering convention.
- Prefer tradable raw prices for simulated fills and adjusted data for return/feature continuity, with a consistent corporate-action treatment. Reject or conspicuously qualify datasets that cannot support the selected convention.
- Handle non-trading days, missing next-session prices, gaps through stops, insufficient warm-up history, delistings/coverage gaps and simultaneous orders deterministically.
- Any ambiguity in OHLC-only intraday stop/target ordering must follow a documented conservative rule. Do not claim tick-level execution fidelity from daily bars.
- Record all rejected trades, data exclusions and unfilled orders, not only successful trades.

## 6. Strategy, simulation and portfolio accounting

The initial research baseline reuses the existing approved US equity/ETF universe and deterministic regime, breakout, relative-strength, liquidity, earnings and ATR-style logic. Original v0.6 parameters are a documented **starting baseline**, not a newly certified optimum. Parameter changes require a versioned experiment and must not be silently fitted on the final holdout.

The primary study is **unleveraged long-only** to make accounting, benchmarks and causal validation tractable. Existing paper-only short and long scale-in contracts may be retained as separately labeled research extensions after the primary study is correct; they are not completion blockers unless explicitly adopted as an experiment.

Simulation must cover:

- Explicit cash, positions, cost basis, realized/unrealized P&L, fees/slippage, exposure and equity; no fabricated fills or negative shares.
- Position sizing and deterministic risk constraints, including maximum simultaneous exposure and rejection explanations.
- Entry/exit timing, stop behavior, gap handling, no-next-bar behavior, repeated signals and final open positions.
- Deterministic ordering for same-session multi-symbol actions and reproducible tie breaking.
- Accounting invariants validated on independent small hand-calculated fixtures.

The existing explicit-signal backtester may be refactored, versioned or wrapped, but its same-day-close behavior must not silently become the research default. Tests for the old API must remain meaningful, with a documented compatibility decision.

## 7. AI/news experiment policy

- Only deterministic shortlist candidates may be analyzed; do not scan the whole market through an LLM.
- Freeze normalized articles and structured AI outputs, with timestamps, source URLs/IDs where legally shareable, model/prompt/schema versions, content hashes, provider failure information and scoring policy.
- Enforce article availability as of the decision, structured-output validation, deduplication, provider budgets and neutral fallback.
- The v0.7 primary comparison is `AI_NEUTRAL` versus `AI_NEGATIVE_ONLY` on the same market path, parameters and eligible deterministic candidates. AI cannot add a trade or increase exposure.
- Compare return, drawdown, exposure, turnover and risk-adjusted metrics; report missing news coverage and selection bias.
- Default runs replay frozen AI evidence without external calls. If there is no adequate time-valid historical news/AI corpus, report that limitation and run only a clearly labeled illustrative or synthetic AI demonstration; do not invent an empirical AI benefit.

## 8. Research evaluation protocol

The detailed method is in [`RESEARCH_PROTOCOL.md`](../research/RESEARCH_PROTOCOL.md). Minimum requirements:

- Predeclare data availability, historical coverage, hypothesis, benchmark, primary metric, cost model, split boundaries and exclusion rules before reading final holdout results.
- Preserve the v0.6 suggested period structure (2012–2018 development, 2019–2023 rolling OOS development, 2024–freeze-date final evaluation) **as a proposal**, not as proof of an untouched lockbox. If prior strategy development used any purported holdout information, explicitly report this and do not label it untouched.
- Use SPY total-return and exposure-adjusted comparisons where data permits; disclose any incomplete benchmark or survivorship coverage.
- Run anchored/expanding walk-forward evaluation, a fixed cost-stress grid, predeclared ablations and reproducible bootstraps or Monte Carlo resampling. Keep in-sample optimization separate from OOS scoring.
- Report at least total/annualized return when defined, max drawdown, exposure, turnover, trade count, win rate, profit factor, Sharpe, Sortino and transaction-cost impact, with robust zero-trade/undefined-metric handling.
- Use consistent daily return treatment, documented annualization and an explicit risk-free/target-return assumption. Audit downside-deviation and P&L calculations against independent examples.
- Include uncertainty intervals and clear caveats about multiple testing, short samples, nonstationarity and realistic tradability.

**Completion is not contingent on beating SPY or reaching old Level 4 performance thresholds.** Valid methodology and faithfully reported findings are required.

## 9. Reproducibility and artifact contract

A canonical experiment run must accept a versioned configuration and an offline data snapshot, then produce a deterministic result directory such as `results/<run_id>/`, containing:

| Artifact | Required content |
| --- | --- |
| `manifest.json` | Code revision, config/data hashes, experiment ID, seed, platform/dependency versions, time convention, provenance and warnings |
| `config.snapshot.*` | Exact effective research configuration |
| `trades.csv` | Signals, simulated fills/exits, rejected/unfilled cases, costs, timestamps and reasons |
| `equity.csv` | Session equity, cash, exposures and benchmark-aligned values |
| `metrics.json` | Definitions, calculated metrics, undefined values and units |
| `comparisons.json` | Baseline/ablation/AI/benchmark comparison references, where applicable |
| `report.md` | Method, findings, tables, limitations and run identifiers |

Use canonical serialization, ordered records and fixed seeds. Two runs with the same inputs should yield byte-identical deterministic artifacts, excluding separately labeled non-deterministic runtime metadata. The implemented R1/R2 CLIs and schemas are documented in the architecture and checkpoint handoffs. A single documented offline command and a small public fixture must reproduce a complete illustrative run without credentials or network access.

Large, private, licensed or generated datasets belong outside Git; commit manifests, code, test fixtures and appropriately sized, licensed example results only.

## 10. Local systems/reliability track

Complete a bounded, meaningful subset of the existing Temporal and audit architecture:

1. A local research workflow with real typed activities and a deterministic result, not a placeholder checkpoint.
2. SQLite-backed idempotent checkpoints and immutable experiment identity; explicit incomplete/failed states.
3. Temporal SDK test-server execution and replay with an activity retry/failure scenario.
4. Duplicate run prevention, interruption/restart recovery and fail-closed reconciliation or audit inconsistency tests.
5. Evidence comparing recovered state to an independent expected reference and stating any untested production behaviors.

No Temporal Cloud, schedule seeding, production worker deployment, real broker lifecycle, Telegram delivery or managed database is required. Existing production-oriented classes may remain as documented historical scaffolding; do not describe them as completed research workflows.

## 11. Verification and quality gates

All tasks should use test-first implementation and small, reviewable commits. Minimum release gates:

1. Clean install from the pinned lockfile on the supported Python version; no credentials for offline demonstration.
2. Relevant unit, integration and Temporal-local tests pass; no skipped or failing tests misrepresented as passing.
3. Static checks (`ruff`, `mypy` for relevant scope, and project-specific checks) pass or have explicitly justified, documented exclusions.
4. Independent numerical fixtures verify cash/equity conservation, fees, next-session fills, stops, metrics, benchmark alignment and zero-trade behavior.
5. Tests prove no future-data access, no network/broker call from the offline runner, stable seed/order behavior and safe AI fallback.
6. The canonical offline run reproduces machine-readable artifacts; repeated runs match after excluding declared runtime-only metadata.
7. At least one properly sourced **real historical-data study** is required before claiming research completion. It must distinguish real from synthetic inputs, preserve hypotheses and report shortcomings. If appropriate historical inputs are unavailable, the software can be described as a reproducible framework, but the empirical research gate remains open.
8. README and reports do not claim autonomous execution, deployment, profitability, an untouched holdout without provenance or completed experiments that have not run.

GitHub Actions is not a completion requirement and must not be re-enabled or changed without separate user authorization. Local executed test logs are acceptable evidence.

## 12. Milestones and release condition

The design is delivered through **four Codex implementation checkpoints** after this documentation/specification transition:

| Checkpoint | Required result |
| --- | --- |
| R1 — Data and simulation | Provenance-bearing offline dataset loader, causal strategy-to-simulation pipeline, correct accounting and baseline results on a public fixture |
| R2 — Experiments and AI | Executable walk-forward, benchmark, cost/stress, Monte Carlo, ablation and bounded AI comparisons with stored artifacts |
| R3 — Systems reliability | Local Temporal/SQLite workflow, deterministic replay and failure/reconciliation demonstrations |
| R4 — Research release | A licensed/provenance-verified historical study, technical report, local visualization, full verification, updated portfolio-facing README |

Each checkpoint requires tests, a clean commit, evidence, and a short handoff with exactly what remains. The next checkpoint must not assume unverified claims from the previous one. The owner has separately authorized **one repository rename** to `ntua-el21026/ai-assisted-quant-research`, subject to GitHub authentication; R1 must verify its completion. Further renaming, deployment, turning on Actions, live/paper broker writes or removing history remain outside the authorized scope.

The project is **research-complete** only when all mandatory gates above are satisfied, a real historical study has been conducted and accurately qualified, and a reviewer can independently reproduce the public example. The full historical study may require separately licensed inputs; publishing its derived findings and reproducibility manifest does not imply that the underlying provider data can be redistributed. If a permitted dataset cannot be obtained, explicitly report **framework implemented; empirical research pending** instead of using a completed-research label. Until then, describe the project as **in development** or **research framework under implementation**.

# AI-Assisted Quantitative Trading Research Framework v0.7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task if those skills are available in your environment. Otherwise apply the same strict task-by-task, test-first and review-gated process. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a reproducible, offline AI-assisted quantitative research framework with a bounded local Temporal reliability demonstration and an evidence-led MSc portfolio release.

**Architecture:** Keep existing data, strategy, risk, AI and ledger modules and introduce a small research orchestration layer. Research runs consume frozen, integrity-checked datasets, generate causal decisions, simulate execution without broker calls, run controlled comparisons and write immutable artifacts. A separate local Temporal/SQLite workflow tests idempotency and recovery, not production trading.

**Tech Stack:** Python 3.12+, `uv`/`uv.lock`, Pydantic, Pytest, Ruff, mypy, SQLite, Temporal Python SDK local test server; static local reports. Add dependencies only with tested justification.

**Spec:** [`docs/app/AI_Assisted_Quant_Research_SPEC_v0.7.md`](../../app/AI_Assisted_Quant_Research_SPEC_v0.7.md); design at [`docs/superpowers/specs/2026-11-16-ai-assisted-quant-research-design.md`](../specs/2026-11-16-ai-assisted-quant-research-design.md); method at [`docs/research/RESEARCH_PROTOCOL.md`](../../research/RESEARCH_PROTOCOL.md).

## Global Constraints

- Work only on `main` unless the user explicitly changes the branch instruction; never force-push or rewrite published history.
- No deployment, CI/Actions activation, cloud schedules, live/paper broker writes, broker credentials or implicit external network calls from the canonical runner.
- No AI order authority, size increases or risk overrides. Missing/invalid AI evidence means neutral fallback and a recorded reason.
- Keep v0.2–v0.6 specs, historical milestones, broker evidence and safety records unchanged; do not claim they satisfy v0.7.
- Preserve stable public interfaces where possible; when changing a model or function, document compatibility and update its tests in the same commit.
- Default tests and one illustrative full run need only license-safe synthetic fixtures and no secrets.
- Treat EOD observation at session `t` as unavailable for an execution at that same already-observed close; next-session semantics are the research default.
- Do not fabricate historical data, news/AI outcomes, performance measurements, test passes, or provenance.
- Each task follows red/green verification, logical commits and a concise evidence handoff; never mark an unexecuted test as passing.
- Do not optimize, select or retune parameters on a declared final-evaluation period after inspecting its scores.

## Review Focus

The following especially damaging edge cases require explicit tests in the owning tasks:

1. Missing next eligible session or price after an EOD signal must produce a recorded unfilled/rejected result, not a same-day or later silently substituted fill (Task 3).
2. Mixed raw/adjusted price bases, duplicate sessions, bad OHLC or gaps must be rejected or explicitly qualified before simulation (Task 1).
3. Post-decision news and malformed or missing frozen AI output must not affect historical decisions or increase risk (Task 7).
4. Duplicate same-day orders and insufficient cash must not cause duplicate fills or impossible portfolio state (Task 3).
5. Interrupted artifact write or duplicate Temporal execution must not produce a falsely successful or inconsistent final run (Tasks 4 and 10).

---

## Codex checkpoint R1 — Data and simulation core

### Task 1: Versioned offline snapshot loader

**Files:**
- Create: `packages/data/snapshots.py`
- Create: `packages/data/quality.py`
- Create: `tests/fixtures/market_snapshot/manifest.json` and small hand-audited CSV input(s)
- Create: `datasets/README.md`
- Test: `tests/unit/test_research_snapshots.py`

**Interfaces:**
- Produce `DatasetSnapshot` (frozen typed model with `dataset_id`, `manifest_sha256`, `feature_bars_by_symbol`, `execution_bars_by_symbol`, `warnings`). Both bar mappings contain `tuple[AdjustedDailyBar, ...]`.
- Produce `load_dataset_snapshot(manifest_path: Path) -> DatasetSnapshot`, reading only local files, checking SHA-256 and documented price bases.
- Consume existing `packages.data.models.AdjustedDailyBar`; keep any separate price-series convention explicit.

- [ ] **Step 1:** Add tests: valid synthetic manifest loads deterministically; duplicate `(symbol,date)`, bad hash, mixed/undeclared price basis, invalid OHLC, missing file and unsorted rows are rejected with stable error codes.
- [ ] **Step 2:** Run `uv run --group dev pytest tests/unit/test_research_snapshots.py -q`; confirm new tests fail for missing implementation.
- [ ] **Step 3:** Implement the typed loader and quality gates, with no provider requests or fallback downloads.
- [ ] **Step 4:** Run the same tests; confirm pass, and run `uv run --group dev ruff check packages/data tests/unit/test_research_snapshots.py`.
- [ ] **Step 5:** Commit loader, fixture and format documentation; note input-license boundaries.

### Task 2: Causal feature-to-decision adapter

**Files:**
- Create: `packages/research/__init__.py`
- Create: `packages/research/models.py`
- Create: `packages/research/signals.py`
- Test: `tests/unit/test_research_signals.py`

**Interfaces:**
- Consume `DatasetSnapshot`, existing `packages.data.features.compute_feature_rows`, regime/candidate helpers in `packages.strategy`, and existing risk contracts.
- Produce `ResearchSignalSet` with accepted signals, rejected decisions, decision session and earliest eligible fill session for every candidate.
- Produce `generate_research_signals(snapshot: DatasetSnapshot, config: ResearchConfig) -> ResearchSignalSet`; define `ResearchConfig` in `packages/research/models.py` with explicit strategy/risk settings and research date range.

- [ ] **Step 1:** Test that inputs available only after `t` cannot influence decisions before `t`; insufficient warm-up, missing earnings data and symbol/risk exclusions receive deterministic reject reasons.
- [ ] **Step 2:** Run `uv run --group dev pytest tests/unit/test_research_signals.py -q` and see a meaningful red failure.
- [ ] **Step 3:** Reuse the existing deterministic helpers without copying their scoring/risk logic; emit time-stamped signals in sorted order.
- [ ] **Step 4:** Verify the new tests and affected existing `tests/unit/test_strategy_signals.py`, `tests/unit/test_regime.py` and `tests/unit/test_risk_checks.py`.
- [ ] **Step 5:** Commit a tested adapter and its contract; document any deliberate exclusion from the research baseline.

### Task 3: Causal execution simulator and numerical audit

**Files:**
- Modify: `packages/backtesting/models.py`
- Modify: `packages/backtesting/engine.py`
- Modify: `packages/backtesting/metrics.py` only where needed for correctness
- Create: `packages/backtesting/execution.py` if cohesive order/fill logic warrants extraction
- Test: `tests/unit/test_research_execution.py`; modify `tests/unit/test_backtesting_metrics.py` only for an explicit compatibility decision

**Interfaces:**
- Produce `run_causal_backtest(snapshot: DatasetSnapshot, signals: ResearchSignalSet, config: ResearchConfig) -> BacktestResult` in `packages/backtesting/engine.py` or a small adjacent module.
- Keep `run_backtest` behavior explicit and tested; do not silently change callers relying on same-day explicit-signal semantics.
- The current `BacktestResult` stores only closed trades, an equity curve and metrics. Extend it with backward-compatible defaults for open terminal positions and rejected/unfilled order events (or document a new typed research-result wrapper before implementing callers). Never silently omit these events from research artifacts.

- [ ] **Step 1:** Hand-calculate fixtures for next-open fills, gap-through-stop, fees/slippage, partial/missing bars, insufficient cash, duplicate orders, simultaneous symbols, open terminal positions and zero trades.
- [ ] **Step 2:** Run `uv run --group dev pytest tests/unit/test_research_execution.py -q`; verify red failures identify the missing causal simulator.
- [ ] **Step 3:** Implement deterministic fills and accounting with explicit trade/position state and rejection/unfilled reasons; preserve old test contracts or expose a clear versioned compatibility path.
- [ ] **Step 4:** Run new/affected backtesting and execution tests, plus Ruff; compare metrics and cash/equity against independent fixture calculations.
- [ ] **Step 5:** Commit a working simulation layer with timing/corporate-action limitations documented.

### Task 4: Canonical offline run and artifact writer

**Files:**
- Create: `packages/research/config.py`
- Create: `packages/research/runner.py`
- Create: `packages/research/artifacts.py`
- Create: `packages/research/cli.py`
- Create: `experiments/configs/baseline.yaml`
- Test: `tests/integration/test_research_cli.py`

**Interfaces:**
- Produce `run_research(config_path: Path, dataset_manifest_path: Path, output_dir: Path) -> ExperimentRunSummary`.
- Expose `uv run python -m packages.research.cli run --config ... --dataset ... --output ...`.
- Write the artifact contract from v0.7 §9 with canonical ordering and hashes; separate nondeterministic runtime metadata.

- [ ] **Step 1:** Add an offline CLI integration test for valid fixture output, invalid config, missing snapshot, rerun parity, partial write rollback and refusal of implicit provider/network access.
- [ ] **Step 2:** Run the integration test and confirm red failures.
- [ ] **Step 3:** Compose Tasks 1–3, implement atomic artifact staging/publication and a stable manifest without time-sensitive output drift.
- [ ] **Step 4:** Run the CLI twice on the fixture and compare deterministic artifact hashes; run all R1 tests and Ruff.
- [ ] **Step 5:** Commit a reproducible baseline run; hand over exact commands and evidence to the reviewer.

**R1 gate:** A fresh environment runs the fixture offline through actual strategy, risk and simulated accounting, producing correct reproducible artifacts. No historical performance claim is required yet.

## Codex checkpoint R2 — Experiments, statistics and bounded AI

### Task 5: Verified metrics and aligned benchmarks

**Files:**
- Modify: `packages/backtesting/metrics.py`
- Create: `packages/research/benchmarks.py`
- Test: `tests/unit/test_research_metrics_benchmarks.py`

**Interfaces:**
- Produce `evaluate_benchmarks(snapshot: DatasetSnapshot, result: BacktestResult, config: ResearchConfig) -> BenchmarkComparison`.
- Produce documented metric helpers with explicit daily calendar, risk-free assumption and `None` for undefined values.

- [ ] **Step 1:** Add hand-calculated tests for initial-equity baseline, daily Sharpe annualization, root-mean-square downside Sortino, drawdown convention, profit-factor no-loss/no-trade cases and aligned SPY/exposure baselines.
- [ ] **Step 2:** Run targeted tests to confirm failing cases against the current implementation.
- [ ] **Step 3:** Correct metrics and implement benchmark alignment without double-counting adjusted returns or future data.
- [ ] **Step 4:** Run new tests plus `tests/unit/test_backtesting_metrics.py` and report any intentional contract changes.
- [ ] **Step 5:** Commit independently verified metrics and benchmark output.

### Task 6: Executable time-aware validation and uncertainty

**Files:**
- Create: `packages/research/validation.py`
- Create: `packages/research/resampling.py`
- Create: `experiments/configs/ablations.yaml`
- Test: `tests/unit/test_research_validation.py`

**Interfaces:**
- Produce `build_walk_forward_folds(config: ResearchConfig, sessions: tuple[date, ...]) -> tuple[WalkForwardFold, ...]`.
- Produce `run_experiment_matrix(snapshot: DatasetSnapshot, config: ResearchConfig) -> ExperimentMatrixResult` with baseline, cost stresses, predeclared ablations and fixed-seed bootstrap summaries.

- [ ] **Step 1:** Test no overlap/leakage between fitting/evaluation, warm-up boundaries, missing sessions, stable fold IDs, identical-seed resamples and no silent final-holdout optimization.
- [ ] **Step 2:** Run the new tests and confirm red failures.
- [ ] **Step 3:** Implement fold building, stress and ablation matrix and seed-controlled resampling; use the existing strategy/simulator interfaces.
- [ ] **Step 4:** Verify tests on the synthetic fixture plus deterministic repeated matrix output; label short-sample uncertainty appropriately.
- [ ] **Step 5:** Commit experiment orchestration and versioned configs, without inventing statistical significance.

### Task 7: Frozen as-of AI replay and neutral-control experiments

**Files:**
- Create: `packages/research/ai_replay.py`
- Create: `tests/fixtures/ai_replay/` with license-safe structured examples
- Test: `tests/unit/test_research_ai_replay.py`

**Interfaces:**
- Produce `load_frozen_ai_evidence(path: Path) -> FrozenAIEvidence` and `apply_research_ai_overlay(signals: ResearchSignalSet, evidence: FrozenAIEvidence, decision_cutoff: datetime) -> ResearchSignalSet`.
- Consume existing `packages.ai` schema/scoring/fallback logic and preserve non-increasing risk.

- [ ] **Step 1:** Test AI neutral/on parity on empty evidence, post-cutoff news exclusion, malformed JSON neutral fallback, duplicate articles, missing citations and no new trade/size increase.
- [ ] **Step 2:** Run the tests and confirm red failures.
- [ ] **Step 3:** Implement offline-only replay with content hashes, source/version metadata, and structured adverse-risk decisions; no API calls.
- [ ] **Step 4:** Run AI unit tests and a paired neutral-versus-overlay fixture experiment with identical non-AI settings.
- [ ] **Step 5:** Commit the module and fixture, labeling any illustrative/synthetic evidence.

### Task 8: Integrated research matrix and complete artifact provenance

**Files:**
- Modify: `packages/research/runner.py`
- Modify: `packages/research/artifacts.py`
- Modify: `packages/research/cli.py`
- Test: `tests/integration/test_research_experiments.py`

**Interfaces:**
- Extend CLI with a documented `evaluate` subcommand (or explicit matrix configuration) that records fold, benchmark, AI and ablation artifacts under stable run IDs.

- [ ] **Step 1:** Write integration tests for paired experiment reproducibility, isolated final evaluation, baseline/AI consistency and missing optional AI evidence.
- [ ] **Step 2:** Verify failures before code changes.
- [ ] **Step 3:** Integrate Tasks 5–7 and publish manifest-indexed matrix comparisons atomically.
- [ ] **Step 4:** Run R1+R2 tests, both CLI paths and lint/type checks for touched modules; compare two run hashes.
- [ ] **Step 5:** Commit a reproducible experiment suite and reviewer-ready evidence manifest.

**R2 gate:** The same frozen dataset produces aligned baseline, benchmark, ablation, uncertainty and optional AI results without future leakage or hidden online dependencies.

## Codex checkpoint R3 — Local computing-systems reliability

### Task 9: Functional local research workflow

**Files:**
- Create: `apps/workers/app/workflows/research_experiment.py`
- Create: `apps/workers/app/activities/research.py`
- Test: `tests/temporal/test_research_workflow_local.py`

**Interfaces:**
- Produce `ResearchExperimentWorkflow.run(request: ResearchWorkflowRequest) -> ResearchWorkflowResult` with typed, deterministic activity contracts that invoke the actual offline research runner.
- Use Temporal SDK local test environment only; do not change existing cloud schedule seeding or broker activities.

- [ ] **Step 1:** Test local workflow execution, typed result, deterministic replay and non-use of broker/provider activities.
- [ ] **Step 2:** Run the Temporal test and see a missing-workflow failure.
- [ ] **Step 3:** Implement the smallest functional workflow and activity pair, keeping I/O in activities and orchestration deterministic.
- [ ] **Step 4:** Run new and existing Temporal SDK tests; capture a successful local replay record.
- [ ] **Step 5:** Commit the bounded workflow, clearly separated from historical production skeletons.

### Task 10: Idempotent audit checkpoints and failure/recovery evidence

**Files:**
- Create: `packages/research/reliability.py`
- Modify: `apps/workers/app/activities/research.py`
- Reuse: `packages/ledger/` SQLite repositories, extending schema only with tested justification
- Test: `tests/temporal/test_research_recovery.py`

**Interfaces:**
- Produce `verify_research_run_state(run_id: str, artifact_dir: Path, ledger: ResearchLedger) -> ResearchStateCheck` and idempotent activity checkpoint operations.
- Define `ResearchLedger` as a typed protocol backed by SQLite; no managed connection required.

- [ ] **Step 1:** Add tests for duplicate IDs, activity retry, simulated interruption, partial artifact, ledger/artifact mismatch and fail-closed repair behavior against a clean reference run.
- [ ] **Step 2:** Confirm red failures before implementation.
- [ ] **Step 3:** Implement transactionally safe checkpoints, result verification and a bounded recovery state machine; never generate a duplicate committed result.
- [ ] **Step 4:** Run local Temporal/recovery tests and existing ledger tests; record exact state parity and no-duplicate evidence.
- [ ] **Step 5:** Commit the evidence-producing recovery demonstration.

**R3 gate:** The local systems demo actually executes work, replays deterministically and preserves correct state under named faults, with zero external broker/cloud calls.

## Codex checkpoint R4 — Results and portfolio release

### Task 11: Derived reports and local results visualization

**Files:**
- Create: `packages/research/reporting.py`
- Create: `docs/research/RESULTS.md` only after actual experiments execute
- Modify: `apps/dashboard/` only if a static generated result viewer is justified
- Test: `tests/integration/test_research_reporting.py`

**Interfaces:**
- Produce `render_research_report(result_dir: Path, output_path: Path) -> Path` consuming only validated artifacts, with source IDs for all tables and plots.

- [ ] **Step 1:** Add tests for exact metric provenance, missing artifacts, undefined metric labels, escaping/no secret exposure and synthetic-versus-historical labeling.
- [ ] **Step 2:** Run targeted tests and confirm red failures.
- [ ] **Step 3:** Generate a readable research report and optional static local viewer from recorded artifacts; no browser backend or trading control surface.
- [ ] **Step 4:** Run the report fixture test, inspect generated output and compare all displayed figures to `metrics.json`.
- [ ] **Step 5:** Commit the report generator and tests, not fabricated historical results.

### Task 12: Execute approved studies and verify the release

**Files:**
- Modify: `README.md` to report verified status/results
- Modify: `docs/README.md` and `docs/research/RESEARCH_PROTOCOL.md` only to document actual method choices
- Create: `docs/research/REPRODUCIBILITY.md`
- Create: a versioned, license-safe reference result under `results/reference/` if permitted (the directory is ignored by default; explicitly review and stage only approved output files)
- Test: all affected `tests/` and the canonical CLI smoke path

**Interfaces:**
- The documented commands must reproduce a full license-safe example on a fresh environment, and optionally a real historical study when a legally usable snapshot is provided.

- [ ] **Step 1:** Freeze and record dataset provenance, experiment configs and code revision before final evaluation; audit any holdout contamination.
- [ ] **Step 2:** Run the full approved matrix on a properly sourced real historical snapshot, with explicit license and universe/split limitations. A synthetic fixture alone is insufficient for the **research-complete** label; if data access is blocked, publish a transparent framework demonstration but leave the R4 empirical gate open.
- [ ] **Step 3:** Run `uv sync --locked --group dev`, relevant `pytest`, `ruff`, `mypy` and CLI/reproducibility checks; record commands, return codes and deviations without editing failing tests to hide issues.
- [ ] **Step 4:** Verify that every result, chart, claim and public link corresponds to an artifact; scan published files for secrets, real broker identifiers, unsupported profitability statements and accidental deployment instructions.
- [ ] **Step 5:** Update public README and technical report to match actual evidence, commit the release and give a concise reproducibility handoff. Do not rename the repo, deploy or activate CI.

**R4 gate:** A reviewer can clone, run and inspect the license-safe example, trace a genuine historical-market study to a verified source, understand data-dependent empirical results and verify local systems evidence. If real historical market data are missing, R4 is incomplete. If adequate AI/news evidence is missing, the AI empirical claim remains explicitly inconclusive; do not fabricate an uplift result.

---

## Checkpoint contract for every Codex prompt

1. Show starting `main` SHA and `git status`; stop if unrelated user modifications make the intended files unsafe to edit.
2. Read `AGENTS.md`, the v0.7 specification, relevant research docs and this plan before changing implementation.
3. Make only the designated checkpoint changes; split into small tested commits as needed, but do not start the next checkpoint.
4. Write tests before implementation for each task; do not weaken safety or the scientific protocol to make tests pass.
5. Report exact passing/failing/skipped commands and any external dependencies that prevented verification.
6. Commit to `main` only after checks and verify local `HEAD`, `origin/main`, a clean tree and the remote hash if pushing is authorized.
7. Provide a compact handoff with changed files, interfaces, results, limitations, open decisions, and next checkpoint readiness.

## Planner self-review before execution

- [x] Every spec requirement maps to one of Tasks 1–12 or is explicitly marked optional/legacy.
- [x] Interface names and produced types are used consistently between dependent tasks.
- [x] All five Review Focus failure modes have tests assigned above.
- [x] Each task's tests can run without credentials or broker/cloud activity after development dependencies are installed.
- [x] R1–R4 gates are independently reviewable, with no mandatory profit target.
- [x] No documentation asserts that proposed commands, experiments, Temporal work or reports already exist.

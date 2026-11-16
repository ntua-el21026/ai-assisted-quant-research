# AI-Assisted Quantitative Trading Research v0.7 — Four Codex Checkpoint Prompts

- **Status:** Prepared for execution; no checkpoint has been implemented by these prompts.
- **Order:** R1 → review → R2 → review → R3 → review → R4 → release review.
- **Branch policy:** User-authorized changes to `main` only. Do not create a feature branch or PR.
- **Core authority:** [v0.7 specification](../app/AI_Assisted_Quant_Research_SPEC_v0.7.md), [research protocol](RESEARCH_PROTOCOL.md), [architecture](ARCHITECTURE.md), [task-level implementation plan](../superpowers/plans/2026-11-16-ai-assisted-quant-research.md) and root [AGENTS.md](../../AGENTS.md).

**Operating sequence:** Copy **one** prompt into Codex after the previous checkpoint has been independently reviewed. Each prompt is self-contained but depends on reading the governing documents. Never interpret an unexecuted target command or a planned test as completed evidence.

## Prompt 1 — R1: Offline research core

```text
Implement CHECKPOINT R1 ONLY for the AI-Assisted Quantitative Trading Research
Framework (v0.7), targeting ntua-el21026/ai-assisted-quant-research.
Work directly on main; do not create branches, PRs or tags. First inspect
git status, local HEAD, origin/main, remote URL and repository instructions.
If the tree is unexpectedly dirty or remote main has diverged, stop and
report rather than overwriting changes.

Before implementing R1, verify the GitHub repository has actually been
renamed to ntua-el21026/ai-assisted-quant-research. Verify the canonical
GitHub repository name, not merely an old URL that may redirect. If GitHub
still reports ai-trading-bot as its canonical slug, STOP and ask the owner
to complete the GitHub Settings rename. Update the documented clone URL
and local origin after the rename is confirmed.

Conduct an exhaustive, case-insensitive name/remnant audit using rg across
active docs, metadata, local scripts, configs, and references. Search for
Endeavour, ai-trading-bot, prior repository URLs, outdated deployment/product
claims, and broken paths created by the v0.7 naming migration. Fix active
references and keep Python/Node package metadata and lockfiles consistent.
Classify legitimate historical references separately: preserve versioned
v0.2–v0.6 specifications, old evidence, original filenames, deployment
records, and archived instructions unchanged. Do not perform the later
legacy-directory restructuring during R1.

Read AGENTS.md, docs/app/AI_Assisted_Quant_Research_SPEC_v0.7.md,
docs/research/RESEARCH_PROTOCOL.md, docs/research/ARCHITECTURE.md and
docs/superpowers/plans/2026-11-16-ai-assisted-quant-research.md in full.
Follow R1 Tasks 1–4, interfaces and test-first steps; keep all decisions
consistent with the governing scope.

Implement and verify:
1. Offline, provenance/sha256-verified market snapshot loading with explicit
   price basis, calendar/data-quality checks and a license-safe fixture.
2. Causal feature -> deterministic candidate/risk decision generation with
   timestamps, rejections and no future data access.
3. Next-eligible-session simulated fills, stop/gap behavior, coherent
   cash/position/equity accounting, fees and independent numerical fixtures;
   preserve or explicitly migrate the legacy run_backtest contract.
4. A working offline research CLI and deterministic, atomic result artifacts
   matching spec v0.7 §9, with two-run hash parity and no provider calls.

Keep the canonical CLI credential-free and offline. No broker requests/writes,
live or paper orders, hosted services, deployment, CI activation, history
rewrites, speculative experimental results or unrequested scope expansion.
Run targeted and affected tests, lint and type checks; do not weaken tests.
Include a Markdown-link check, package lock consistency checks and a final
remnant report that distinguishes active stale names from intentional history.
Use small meaningful commits, push to main only if git authorization works
and origin has not diverged (never force), and verify remote HEAD. Stop after
R1. Report commit SHA(s), changed interfaces, executed commands/outcomes,
fixture/artifact hashes, unresolved limitations and exact R1 gate status.
```

## Prompt 2 — R2: Experiments and bounded AI

```text
Implement the research framework v0.7 CHECKPOINT R2 ONLY on main, after verifying R1 has
actually passed its gate. Do not create a branch, PR or deployment.
Check git status, HEAD and origin/main first; stop on conflicting changes.
Read root AGENTS.md, v0.7 specification, research protocol, architecture,
and R2 Tasks 5–8 in docs/superpowers/plans/2026-11-16-ai-assisted-quant-research.md.

Write failing tests first, then implement:
1. Audited Sharpe/Sortino/drawdown/return/turnover definitions, initial-equity
   accounting, aligned SPY and exposure benchmarks and undefined-metric rules.
2. Temporal fold separation, walk-forward evaluation, declared cost stresses,
   ablations and fixed-seed bootstrap/Monte Carlo summaries, without fitting
   on any final holdout.
3. As-of-valid frozen news/AI replay using existing non-increasing risk
   contracts; neutral-control comparisons, post-cutoff exclusion, hashes,
   coverage diagnostics and fail-neutral malformed/missing evidence.
4. One integrated offline experiment matrix with deterministic provenance and
   machine-readable comparison artifacts. Check two-run reproducibility.

Use only frozen local input for canonical tests. Never call an AI/news provider
implicitly, fabricate historical AI evidence, place broker/paper orders,
deploy or enable CI. Preserve R1 behavior, run R1+R2 tests and relevant
lint/type checks, and commit in tested units to main (non-force push only
after safe remote verification). Stop at R2 and report exact hashes, command
results, evidence and remaining limitations for independent review.
```

## Prompt 3 — R3: Local systems correctness

```text
Implement the research framework v0.7 CHECKPOINT R3 ONLY, directly on main, after verifying
R1 and R2 evidence. Do not create a branch, PR or deployment. First inspect
git status, HEAD and origin/main and stop on conflicts. Read AGENTS.md,
the v0.7 spec, architecture, protocol and R3 Tasks 9–10 of the approved
implementation plan in docs/superpowers/plans/.

Use tests first to build the smallest functional local Temporal workflow:
typed request/result, actual offline research activity, deterministic replay,
retry and local test-server verification. Add idempotent SQLite-backed run
checkpoints and a reliable state-check/recovery path. Independently compare
uninterrupted versus duplicate/retried/interrupted runs, including partial
artifact corruption, and prove no duplicated committed side effects.

Never invoke legacy broker-order activities, cloud Temporal, managed databases
or outbound provider calls. Do not start a worker schedule or enable CI.
Run local Temporal integration tests, ledger and R1/R2 regression tests plus
relevant lint/type checks, then commit tested work to main (push only with
safe non-force remote checks). Stop after R3 and report exact state-parity,
retry/replay evidence, test results, commits and remaining limitations.
```

## Prompt 4 — R4: Research results and portfolio release

```text
Implement the research framework v0.7 CHECKPOINT R4 ONLY on main after verifying gates
R1–R3. First check git status, HEAD and origin/main; do not overwrite
unexpected changes. Read AGENTS.md, spec v0.7, research protocol,
architecture and R4 Tasks 11–12 of the implementation plan.

Build a derived technical report and (only if useful) a static LOCAL results
viewer sourced solely from versioned artifacts. Validate all numeric claims,
metric units, undefined values, provenance, escaping and secret safety.
Publish a license-safe fully reproducible synthetic reference example AND
conduct a genuine, licensed/provenance-verified historical-data study with
chronological evaluation, benchmarks, cost stresses, ablations and uncertainty.
Use only separately supplied/authorized read-only acquisition if needed.
Never download restricted data or publish third-party raw data without rights.
If suitable historical data are unavailable, STOP the empirical completion
gate and report exactly what input/authorization is needed; do not call the
research complete using only synthetic fixtures. Similarly label an absent
credible as-of historical news corpus as inconclusive AI empirical evidence.

After actual runs, update README, docs/research/RESULTS.md and
REPRODUCIBILITY.md as appropriate. Verify a clean offline reference run,
all relevant tests, Ruff/mypy, artifact hash parity, Markdown links,
licensing/secret review and no unsupported profitability/deployment claims.
Do not deploy, connect broker accounts, activate CI or write real/paper orders.
Commit tested work directly to main, non-force push only after remote checks,
and report SHA(s), test commands, provenance, authentic results, caveats and
the precise research-completion gate status. Do not create a release/tag or PR.
```

## Handoff requirements

After **each** checkpoint, the reviewer should independently inspect test outcomes and changed code before authorizing the next prompt. Save the verified checkpoint status, unresolved decisions, precise run commands and artifact hashes in the implementation handoff. The final project state must be supported by **executed evidence**, not just complete checklists or polished documentation.

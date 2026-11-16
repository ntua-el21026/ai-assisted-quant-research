# AGENTS.md — AI-Assisted Quantitative Trading Research Framework

## Project identity and authority

This repository is an **offline-first, reproducible AI-assisted trading research framework**. It showcases quantitative research, bounded AI news-risk analysis, software correctness and local systems reliability for MSc applications. It is **not** a deployable autonomous trading system.

The authoritative scope and acceptance criteria are:

1. [`docs/app/AI_Assisted_Quant_Research_SPEC_v0.7.md`](docs/app/AI_Assisted_Quant_Research_SPEC_v0.7.md) — current product specification.
2. [`docs/research/RESEARCH_PROTOCOL.md`](docs/research/RESEARCH_PROTOCOL.md) — data, experiment and reporting methodology.
3. [`docs/research/ARCHITECTURE.md`](docs/research/ARCHITECTURE.md) — architectural boundaries.
4. [`docs/superpowers/plans/2026-11-16-ai-assisted-quant-research.md`](docs/superpowers/plans/2026-11-16-ai-assisted-quant-research.md) — implementation tasks and gates.
5. Existing code and tests, followed by the current user-approved task.

The previous autonomous-trading specifications v0.2–v0.6, evidence, paper-broker milestones and operational runbooks are **historical**, not current acceptance criteria. The previous agent instructions are archived at [`docs/history/AGENTS_legacy_v0.6.md`](docs/history/AGENTS_legacy_v0.6.md). If documents conflict, use v0.7 and explicitly identify material ambiguity before implementing.

## Non-negotiable boundaries

1. **No deployment**: do not deploy to Vercel, a VPS, Temporal Cloud, managed databases or any hosted service; do not activate schedules or a continuously running worker.
2. **No broker writes**: do not place, cancel, replace or modify live or paper orders, flatten positions or perform cleanup on a real broker account. Historical smoke scripts that can write to Alpaca are out of scope and must not be run.
3. **No credentials by default**: the research CLI, tests, local Temporal demos and published fixture must work without external API keys, broker accounts or network access. Never inspect or print private credentials.
4. **No live authority**: keep live/autonomous execution flags disabled; no leverage, live shorting, AI broker authority or LLM-driven order placement. Do not loosen deterministic risk constraints.
5. **No false research claims**: do not invent prices, dataset provenance, AI outputs, test results, statistical significance, positive performance or deployment proof. Synthetic, historical and local-reliability evidence must be labeled separately.
6. **No silent scope changes**: changes to the research questions, execution timing, experiment splits, AI authority, risk policy or release gates require explicit review and a corresponding specification update.
7. **Preserve history**: do not rewrite published Git history, remove historical v0.6 specifications/evidence, or redact them in ways that misrepresent past outcomes.

## Research correctness requirements

- Research inputs are frozen, manifest-verified local snapshots; optional provider acquisition is a separate explicit read-only operation and never part of the canonical offline run.
- Features and decisions may use only data available by the declared decision timestamp. Completed EOD data for session `t` cannot cause a same-session already-observed close fill; use the next eligible session's execution convention.
- Distinguish raw tradable and adjusted research prices, market calendars, corporate actions, missing sessions and point-in-time universe limitations. Fail or warn explicitly according to the spec.
- The primary research baseline is unleveraged long-only. Paper-only short and long scale-in modules may be retained as optional simulations but are not release blockers.
- AI is limited to frozen shortlist news-risk evidence, negative-only influence and neutral fallback on missing or invalid output. It cannot add orders or increase size.
- Use time-aware splits, aligned benchmarks, versioned ablations, fixed seeds and reproducible statistics. Do not claim a holdout was untouched without checking historical design exposure.
- A zero-trade experiment, inconclusive comparison or negative return can still be a successful research result if the methodology is correct and limitations are accurately described.

## Working method for Codex

The user has requested work on **`main` only**. At the start of each checkpoint:

1. Check `git status`, `HEAD` and `origin/main`; preserve unrelated user modifications and stop if they conflict with the intended files.
2. Read the governing v0.7 documents and the exact checkpoint in the implementation plan; do not resume a legacy production milestone.
3. Identify affected modules and interfaces; use small cohesive tasks, failing tests first, and meaningful local verification.
4. Keep fake/local execution safe by default and reject network or broker operations from canonical research entry points.
5. Maintain compatibility where practical and document any intentional change to older tests or interfaces.
6. Run the affected tests, static checks and deterministic fixture smoke before committing; do not weaken, skip or delete tests to create green output.
7. Commit logically grouped changes to `main`, push only when authorized by the operating user/session, then verify the remote head and clean tree.
8. Report exact commit IDs, changed files, commands, outcomes, open limitations, and readiness for the **next** checkpoint. Stop after the assigned checkpoint.

Do not activate GitHub Actions/CI unless the user explicitly requests it. A locally executed test log is acceptable evidence; an unexecuted test is not.

## Preferred implementation boundaries

- Python **3.12+**, `uv.lock`, Pydantic, Pytest, Ruff and mypy; do not upgrade dependencies without a tested need.
- Reuse `packages/data`, `packages/strategy`, `packages/risk`, `packages/execution`, `packages/ai`, `packages/backtesting`, `packages/ledger` and `packages/reporting` when possible.
- Put canonical offline research orchestration, experiment validation and artifact generation in a small `packages/research` surface. Keep unrelated modules focused.
- Keep the core research CLI independent of Temporal. Use the Temporal SDK **local test environment** only for the bounded systems track, with simulated side effects and SQLite persistence.
- Keep generated artifacts under a documented result directory, with hashes, sorted records, config snapshot, warnings and explicit nondeterministic metadata. Do not commit large licensed data or raw private provider payloads.
- Local results visuals must consume generated artifacts; do not turn the static dashboard into a live control plane.
- The owner authorized one GitHub rename to `ntua-el21026/ai-assisted-quant-research`; confirm the canonical remote name before R1 begins. Do not make any further repository-name change or remove legacy deployment files without separate authorization.

## Four checkpoint gates

| Checkpoint | Completion proof |
| --- | --- |
| **R1** Data and simulation | Offline manifest-backed fixture produces correct causal strategy/simulation results and deterministic artifact hashes |
| **R2** Experiments and AI | Benchmarks, walk-forward, stress, ablations, uncertainty and frozen AI comparisons execute without future leakage |
| **R3** Local systems reliability | A real local Temporal workflow, retry/replay, idempotent ledger and fault-recovery tests preserve reference state |
| **R4** Portfolio research release | Verifiable experiments, report, optional static viewer, documented limitations, reproducibility instructions and full relevant checks |

The research framework must remain labeled **in development** until all mandatory v0.7 gates have evidence. Live readiness, paper-trading operational readiness and positive investment performance are never v0.7 completion criteria.

## Documentation integrity

Keep `README.md`, `docs/README.md`, the v0.7 specification, research protocol and architecture consistent with code **actually implemented**. Proposed commands and future experiments must be labeled as targets until verified. Preserve dates, original evidence and attribution. When preparing portfolio copy, favor concrete validated engineering contributions over promotional claims.

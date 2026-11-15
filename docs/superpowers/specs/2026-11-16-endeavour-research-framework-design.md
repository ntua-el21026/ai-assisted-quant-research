# Endeavour Research Framework v0.7 — Approved Design

- **Date:** 2026-11-16
- **Owner:** Michail Athanasios Peppas
- **Decision:** Option B — Balanced AI/ML + Systems Research Framework
- **Status:** Design approved in conversation; implementation pending

## Intent and audience

Endeavour should become an academically credible, independently reproducible portfolio project for MSc Computer Science, Data Science, AI/ML and quantitative-finance applications. Its value comes from rigorous quantitative experiments, bounded AI evaluation, explicit correctness properties and a focused local systems-reliability demonstration. It is not a trading product and will not be deployed.

## Goals

- A working offline dataset-to-signals-to-simulation-to-results pipeline, with correct temporal semantics and accounting.
- Transparent quantitative benchmarks, time-aware validation, ablations, sensitivity and uncertainty analysis.
- A frozen, timestamp-valid and non-increasing AI/news overlay comparison with honest null and failure cases.
- Local Temporal and ledger experiments that test replay, idempotence, retries and state reconciliation.
- A complete technical report, self-contained demo fixture, reproducibility commands, local plots and a truthful GitHub README.

## Non-goals and anti-goals

- No VPS, Vercel, managed deployment, background trading service, active broker account or live/paper orders.
- No real-time trading, profitability claim, unbounded AI trading or automatic tuning on a declared final holdout.
- No wholesale rewrite of functional legacy code just to match an idealized architecture.
- Avoid a broad but unfinished framework, synthetic results presented as empirical findings, or a polished README with no reproducible research.

## Approaches considered

| Approach | Benefit | Trade-off | Decision |
| --- | --- | --- | --- |
| A — Quantitative research first | Fastest path to historical experiments | Underuses existing reliability/Temporal modules | Not selected |
| **B — Balanced research + local systems** | Strong CS/DS combination and reuse of existing code | Requires bounded orchestration and additional tests | **Selected** |
| C — Full systems-heavy simulator | Deepest workflow complexity | Expensive and distracts from the research hypothesis | Not selected |

## Chosen architecture

The canonical Python CLI loads frozen historical snapshots, validates them, computes causal features and deterministic candidates, applies optional frozen AI evidence and risk controls, simulates trades and calculates benchmarks/experiments. It writes reproducible machine-readable artifacts and a locally viewable report. The main pipeline works without Temporal. Separately, a small local Temporal workflow exercises the same core through typed activities and SQLite-backed idempotency/recovery tests.

The [v0.7 specification](../../app/Endeavour_Research_Framework_SPEC_v0.7.md), [research protocol](../../research/RESEARCH_PROTOCOL.md), and [architecture](../../research/ARCHITECTURE.md) are normative for details. This design intentionally leaves no broker-write or deployment path in the canonical workflow.

## Important technical decisions

1. **Historical continuity:** Preserve v0.2–v0.6 specifications, prior paper-trading evidence, and legacy operational docs as history; do not retcon them as research validation.
2. **Primary strategy:** Start with unleveraged long-only EOD research, using prior deterministic config as a disclosed baseline. Paper-only short/scale-in experiments are optional extensions.
3. **Causality:** Completed EOD observations at `t` may not cause fills at the already-observed close of `t`; default simulation executes no earlier than next eligible session.
4. **Data:** Offline manifest-verified snapshots are mandatory. Real Tiingo or other licensed data are optional, separately acquired and never assumed redistributable. Small public synthetic fixtures must work without credentials.
5. **AI:** A frozen negative-only overlay is compared with neutral AI using identical decisions and market paths. Missing adequate historical AI data becomes a documented limitation, not made-up evidence.
6. **Research rigor:** Separate development, rolling OOS and final evaluation; audit potential holdout contamination due to prior work. Positive returns are not required to pass.
7. **Systems:** Complete selected local Temporal/replay/failure experiments, not all ten legacy production workflow skeletons.
8. **Release:** Require tests, deterministic artifacts, link/secret checks, methodology, measured results and limitations. GitHub Actions/deployment are out of scope.

## Proposed execution order

1. Documentation migration: v0.7 spec, protocol, architecture, AGENTS, README, technical index and implementation plan.
2. Codex checkpoint R1: data and simulation correctness.
3. Codex checkpoint R2: experiments, metrics, benchmarks and AI evaluation.
4. Codex checkpoint R3: local reliability and Temporal integration.
5. Codex checkpoint R4: actual results, local presentation and release verification.

Each checkpoint must preserve a clean repository, produce executable tests and a commit, and undergo independent source/evidence review before the next. The user requested direct edits to `main` for the documentation phase. Later Codex commits should also respect the user's branch preference unless the user changes it.

## Outstanding builder choices

These are implementation decisions inside the approved scope, not license to change requirements: exact historical provider snapshot format, whether to extend or wrap the legacy backtester while preserving tests, exact CLI argument names, optional visualization library, and extent of licensed historical input available for the final study. Implementers must document these choices and stop if a choice affects causal validity, AI authority, non-goals or user-controlled permissions.

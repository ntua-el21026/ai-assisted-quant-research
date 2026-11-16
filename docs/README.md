# Technical documentation index

**The AI-assisted quantitative trading research framework (v0.7) is under implementation.** No production deployment, paper-broker operation or live-trading readiness is a current goal. The v0.7 research specification supersedes the operating objectives of older documents, which remain available to explain historical implementation and tests.

## Authoritative research documentation

| Document | Purpose | Status |
| --- | --- | --- |
| [Research framework specification v0.7](app/AI_Assisted_Quant_Research_SPEC_v0.7.md) | Research questions, non-goals, safety, interfaces and completion criteria | **Governing specification** |
| [Research protocol](research/RESEARCH_PROTOCOL.md) | Dataset provenance, causal semantics, time-aware experiments, metrics, uncertainty and reporting | Method; R1 implementation available, studies pending |
| [Research architecture](research/ARCHITECTURE.md) | Actual component inventory, R1 pipeline/CLI, planned local Temporal boundary | Planned additions distinguished from existing code |
| [Design decision](superpowers/specs/2026-11-16-ai-assisted-quant-research-design.md) | Approved balanced AI/ML + systems direction and tradeoffs | Approved scope |
| [Four-checkpoint implementation plan](superpowers/plans/2026-11-16-ai-assisted-quant-research.md) | Test-first R1–R4 task definitions and verification gates | R1 implemented; R2–R4 pending |
| [Four Codex prompts](research/CODEX_CHECKPOINT_PROMPTS.md) | Copy-ready R1–R4 implementation assignments to use sequentially after review | R1 implementation completed; later prompts await review |
| [Root contributor/agent guide](../AGENTS.md) | Repository safety constraints, instructions and current authority | Current |
| [Main README](../README.md) | Portfolio-facing introduction and truthful implementation status | Current |

### The four implementation checkpoints

1. **R1 — Data and simulation:** audited offline snapshots, signal generation, correct causal fills and local artifact contract.
2. **R2 — Experiments and AI:** aligned benchmarks, walk-forward, cost/ablation/uncertainty analysis and frozen AI evaluation.
3. **R3 — Local reliability:** real local Temporal research workflow, SQLite idempotency and recovery evidence.
4. **R4 — Portfolio release:** verified results, research report, license-safe example, local presentation and reproducibility audit.

R1 has implemented tests and a synthetic artifact path; independent review is pending. R2–R4 remain unimplemented targets. See [R1 contracts and reproducibility](research/R1_IMPLEMENTATION.md) and the
[executed R1 verification handoff](research/R1_VERIFICATION.md). A synthetic example is not empirical performance evidence.

## Historical implementation references — not v0.7 goals

The documents in this section describe code, interfaces and operational ideas from the previous autonomous-bot project. They may still help when reusing components, but their references to the "current" v0.5/v0.6 spec, production services, paper schedules or Level 4 promotion are superseded.

- [Legacy v0.6 agent instructions](history/AGENTS_legacy_v0.6.md) and [historical README](history/readme-before-portfolio-preparation.md).
- [Legacy architecture](architecture.md), [Temporal workflows](temporal_workflows.md) and [validation plan](validation_plan.md).
- [Strategy/risk](risk_policy.md), [execution](execution_policy.md) and [broker integration](broker_integration.md) for existing deterministic and paper-only module contracts.
- [AI intelligence](ai_intelligence.md) for bounded shortlist news-analysis contracts and neutral fallbacks.
- [Database/audit ledger](database_audit_ledger.md) and [database runtime](database_runtime.md) for SQLite/managed-db implementation history.
- [Dashboard/control plane](dashboard_control_plane.md), [reporting](reporting.md) and [alerting](alerting.md) for historical presentation/read-model boundaries.
- [Fake/local dry-run orchestration](paper_dry_run_orchestration.md) is an existing *safe local demonstration*, but is not the canonical v0.7 research run.
- [Operational runbook](operations_runbook.md), [paper-trading runbook](paper_trading_runbook.md), [Level 4 readiness](level4_micro_live_readiness.md) and [legacy milestone prompts](prompts/README.md) are archival context, **not instructions for this research release**.
- Earlier [specifications v0.2–v0.6](app/) remain preserved unchanged for traceability.

## Historical evidence and interpretation

- [Frozen-validation start](frozen_paper_validation_m45.md), [Day-1 audit](frozen_validation_day1_audit_m46.md), [runner](frozen_validation_runner_m47.md) and [durable-runner record](durable_runner_m47b.md) capture dated paper-validation milestones.
- [Machine-readable evidence](evidence/) contains earlier observed results, failures and gates. It does **not** establish a complete 56-day validation, profitability, an active deployment or completion of the new research study.
- The [old readiness documents](frozen_validation_readiness_m44.md) and checklists are retained to preserve engineering history, not as current release requirements.

Default v0.7 tests and the R1 reference experiment need **no provider credentials, broker connection or deployment**. Do not run legacy scripts that can place paper orders. Preserve historical failure evidence and accurately qualify all new findings.

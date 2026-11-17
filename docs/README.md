# Technical documentation index

**Engineering implementation verified; historical empirical research pending.**
The v0.7 scientific completion gate remains open. Production deployment, paper-broker
operation and live-trading readiness are outside this deliverable. Earlier documents
remain dated engineering/research evidence; the current handoff separates their role
from the final portfolio status.

## Start with the engineering closure

- [Final project handoff](research/FINAL_PROJECT_HANDOFF.md): delivered scope, fresh
  checks, hashes, limitations, source decision and Git delivery evidence.
- [Public reproducibility guide](research/REPRODUCIBILITY.md): executed offline sequence,
  deterministic byte verification and independently calculated synthetic expectations.
- [Final data-feasibility decision](research/FINAL_DATA_FEASIBILITY.md): existing pilot
  plus three alternatives; empirical NO-GO without new acquisition or a changed study.

No additional R4-B investigation or historical strategy execution is active. The research
program remains in development; the engineering deliverable is ready for portfolio review.

## Authoritative research documentation

| Document | Purpose | Status |
| --- | --- | --- |
| [Research framework specification v0.7](app/AI_Assisted_Quant_Research_SPEC_v0.7.md) | Research questions, non-goals, safety, interfaces and completion criteria | **Governing specification** |
| [Research protocol](research/RESEARCH_PROTOCOL.md) | Dataset provenance, causal semantics, time-aware experiments, metrics, uncertainty and reporting | Engineering verified; empirical study pending |
| [Research architecture](research/ARCHITECTURE.md) | Actual offline research/matrix CLI, local Temporal/SQLite and qualification boundaries | Delivered interfaces and deferred scientific work distinguished |
| [Design decision](superpowers/specs/2026-11-16-ai-assisted-quant-research-design.md) | Approved balanced AI/ML + systems direction and tradeoffs | Approved scope |
| [Four-checkpoint implementation plan](superpowers/plans/2026-11-16-ai-assisted-quant-research.md) | Test-first R1–R4 task definitions and verification gates | R1–R3 reviewed baseline; R4 empirical gate pending |
| [Four Codex prompts](research/CODEX_CHECKPOINT_PROMPTS.md) | Original checkpoint assignments; later work follows explicit staged authorization | Historical assignments; use the final handoff for current status |
| [Root contributor/agent guide](../AGENTS.md) | Repository safety constraints, instructions and current authority | Current |
| [Main README](../README.md) | Portfolio-facing introduction and truthful implementation status | Current |

### Checkpoint structure and detailed evidence

1. **R1 — Data and simulation:** audited offline snapshots, signal generation, correct causal fills and local artifact contract.
2. **R2 — Experiments and AI:** aligned benchmarks, walk-forward, cost/ablation/uncertainty analysis and frozen AI evaluation.
3. **R3 — Local reliability:** real local Temporal research workflow, SQLite idempotency and recovery evidence.
4. **R4 — Portfolio release:** historical study and reporting, public example and reproducibility audit. Engineering closure is complete; the empirical gate remains open.

R1–R3 have tests and executed synthetic/local systems paths. The owner identifies
`60dd250` as their reviewed R1–R3 baseline. R4-A's synthetic-only historical-data
and corporate-action foundation was independently accepted at `0dd0875`.
R4-B engineering was independently accepted at `a6d3a09`. Subsequent corrective
reports preserve their dated implementation, qualification and review status.
The pilot has complete internal bar coverage but remains unqualified for historical
strategy research. The final handoff records the current engineering closure.
Test counts and artifact hashes in earlier reports describe their recorded revisions;
they are not replacements for the consolidated closure evidence.
See [R1 contracts](research/R1_IMPLEMENTATION.md), [R1 verification](research/R1_VERIFICATION.md),
[R2 verification](research/R2_VERIFICATION.md) and [R3 verification](research/R3_VERIFICATION.md).
A synthetic example is not empirical performance evidence.

- [R4-A implementation contracts](research/R4A_IMPLEMENTATION.md): explicit v2 snapshot,
  causal prices, isolated action accounting and analytical benchmarks.
- [R4-A acquisition boundary](research/R4A_ACQUISITION.md): mocked SIP transport,
  exact normalization/provenance bridge and unsupported provider conditions.
- [R4-A verification](research/R4A_VERIFICATION.md): executed checks, literal numerical
  evidence, baseline compatibility and deterministic hashes.
- [R4-A bounded implementation plan](superpowers/plans/2026-11-16-r4a-historical-infrastructure.md).
- [R4-B implementation](research/R4B_IMPLEMENTATION.md): opt-in finite IEX acquisition,
  immutable private candidate envelopes and offline qualification.
- [R4-B data qualification](research/R4B_DATA_QUALIFICATION.md): sanitized acquisition,
  corporate-action, rights and scientific restrictions.
- [R4-B verification](research/R4B_VERIFICATION.md): commands, hashes, compatibility and review handoff.
- [R4-B bounded plan](superpowers/plans/2026-11-17-r4b-historical-acquisition.md).
- [R4-B.1 implementation](research/R4B1_IMPLEMENTATION.md): explicit action applicability,
  aggregate budgets, immutable reuse and strict acquisition gates.
- [R4-B.1 data qualification](research/R4B1_DATA_QUALIFICATION.md): issuer contradictions,
  the acquired IEX pilot, precision/aggregation evidence and blocked admission.
- [R4-B.1 verification](research/R4B1_VERIFICATION.md): tests, hashes, numerical compatibility
  and independent-review handoff.
- [R4-B.1 bounded plan](superpowers/plans/2026-11-17-r4b1-requalification.md).
- [R4-B.2 implementation](research/R4B2_IMPLEMENTATION.md): optional exact-record currency
  resolution, preserved raw evidence and unchanged strict admission.
- [R4-B.2 data qualification](research/R4B2_DATA_QUALIFICATION.md): all 16 applicable events,
  period-specific primary evidence, three resolved currency fields and owner decision matrix.
- [R4-B.2 verification](research/R4B2_VERIFICATION.md): offline two-run hashes, regression
  checks and blocked R4-C handoff; independent acceptance pending.

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

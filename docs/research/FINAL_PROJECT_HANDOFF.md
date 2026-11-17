# Final project handoff — 2026-11-17

**Engineering implementation verified; historical empirical research pending.**

The implemented framework is a verified, reproducible engineering deliverable for
portfolio review. Historical strategy evaluation has not executed. The original
v0.7 scientific research-completion gate remains open. This is project engineering
closure, not acceptance of the blocked pilot, investment evidence or production readiness.

## Decision and scope

The final bounded review first assessed the existing authorized Alpaca IEX pilot,
then compared exactly three alternatives: Tiingo, EODHD and Massive. No sufficiently
qualified source with established acquisition authorization was available within
the permitted scope. [The source decision](FINAL_DATA_FEASIBILITY.md) records the
current official documentation, rights distinctions, finite review budget and NO-GO.
No new provider observation, authenticated request, account change or purchase occurred.

Consequently the conditional dataset/study/report phases were not executed. No
restricted-study contract or temporal amendment was invented without a data GO.
Strategy, positive relative strength, risk limits, thresholds, benchmark definitions
and proposed original splits remain unchanged. SPY alone would have zero relative
strength against itself and cannot replace the required distinct tradable instrument.
A future restricted study would need a qualified source, sufficient warm-up for the
200-session regime and other rolling/confirmation logic, predeclared boundaries and
an exposure/contamination audit. Earlier strategy work and inspected observations
do not establish an untouched 2024+ lockbox. No final historical segment was scored.

Historical AI/news evidence remains unqualified. An eventual empirical study must
keep AI neutral unless credible as-of evidence exists. Frozen synthetic AI examples
test bounded behavior; they do not support an empirical AI-uplift claim.

## Engineering-closure identity and file inventory

Initial clean main, origin/main and remote GitHub main all matched
`73febf57badc11dfe0a4984c7a5ac9c9ca242ddd`, with canonical SSH origin
`git@github.com:ntua-el21026/ai-assisted-quant-research.git`.
That is also the unchanged accepted implementation revision: closure changes only
Markdown documentation. The 147-file Python fingerprint remains
`0024fb53a8b6036c122a0b8eb3292c4205ddd837bbf58ea11b9933d90685cd1d`.

Closure commits:

1. `d4dc21485b6429810d1d8306331be20ff2394cbd` — `docs(research): close bounded data feasibility with empirical no-go`.
2. `cb30a032fff66966de6645545ee443dbe12366a6` — `docs: finalize engineering portfolio and reproducibility handoff`.

The engineering closure was delivered at `cb30a032fff66966de6645545ee443dbe12366a6`.
The subsequent documentation-only correction and presentation pass are described below.
Their final revision is the commit containing this updated handoff, resolved with
`git log -1 --format=%H -- docs/research/FINAL_PROJECT_HANDOFF.md`. The post-push receipt
and delivery message record its literal SHA without a self-referential commit hash.

| Changed file | Purpose |
| --- | --- |
| `README.md` | Concise portfolio overview, real capabilities, verified synthetic outcome and empirical status |
| `docs/README.md` | Entry points to closure, reproducibility and source decision; earlier reports retained |
| `docs/app/AI_Assisted_Quant_Research_SPEC_v0.7.md` | Clarify engineering closure versus the still-open scientific gate |
| `docs/research/RESEARCH_PROTOCOL.md` | Record final NO-GO without changing experimental parameters or split proposals |
| `docs/research/ARCHITECTURE.md` | Record actual delivered boundaries and closure status |
| `docs/research/FINAL_DATA_FEASIBILITY.md` | Finite primary-source comparison and empirical STOP |
| `docs/research/REPRODUCIBILITY.md` | Executed public command sequence, paired hash checks and expected outputs |
| `docs/research/FINAL_PROJECT_HANDOFF.md` | Consolidated evidence, limitations and delivery contract |

No Python, tests, fixtures, experiment configuration, dependency/lockfile, deployment,
Actions, historical report or private evidence file is changed. Runtime API/contract
versions and all accepted numerical behavior are preserved. No branch, tag, release,
PR, rebase, reset or history rewrite is part of this checkpoint.

## Delivered engineering and existing detailed evidence

| Track | Verified capability | Detailed report |
| --- | --- | --- |
| R1 | Manifest integrity, causal features/decisions, exact next-session execution and accounting | [Contracts](R1_IMPLEMENTATION.md), [numerical verification](R1_VERIFICATION.md) |
| R2 | Metrics, aligned benchmarks, chronological folds, fixed stresses/ablations, seeded uncertainty and frozen AI bounds | [R2 verification](R2_VERIFICATION.md) |
| R3 | Actual local workflow/activity, SQLite lifecycle, idempotence, fault recovery, reconciliation and history replay | [R3 verification](R3_VERIFICATION.md) |
| R4-A | Compatible v2 models, exact split/dividend state transitions and three analytical benchmark conventions | [Contracts](R4A_IMPLEMENTATION.md), [verification](R4A_VERIFICATION.md) |
| R4-B/B.1/B.2 | Explicit acquisition safety, cumulative durable budgets, economic action scope and evidence-bound field resolution | [R4-B](R4B_VERIFICATION.md), [R4-B.1](R4B1_VERIFICATION.md), [R4-B.2](R4B2_VERIFICATION.md) |

The v1 strategy simulator and isolated v2 corporate-action demonstration are separate
tested interfaces. A complete v2 historical strategy study has not been integrated or
claimed. Local exactly-once claims concern committed observable results, not computation
attempts. SQLite and filesystem publication are separate durability boundaries. These
are bounded cooperative single-host tests, not distributed/concurrency, hostile-writer,
power-loss, exchange-execution or hosted-production guarantees.

## Engineering-closure test, static and installation evidence

The following established results belong to the engineering-closure verification;
the later editorial pass does not represent them as a newly executed full suite.
Environment: Python 3.14.7, SQLite 3.53.1, Pydantic 2.13.3, Pytest 9.0.3, Ruff 0.15.12,
mypy 1.20.2 and Temporal SDK 1.27.0. No existing environment was deleted/recreated.
All settled verification commands exited **0**:

| Exact command | Observed outcome |
| --- | --- |
| `uv run --offline --no-sync pytest -q -rs` | **1,521 passed, 9 skipped, 0 failures/errors, 3 warnings**, 44.50 s |
| `uv run --offline --no-sync ruff check .` | Repository-wide PASS |
| Established mypy command below | PASS, 59 source files; no repository-wide typing claim |
| `uv run --offline --no-sync ruff format --check packages/data/action_reconciliation.py tests/unit/test_action_reconciliation.py` | PASS; established latest interface formatting scope; no unrelated reformatting |
| `uv lock --check --offline` | PASS, 27 entries |
| `uv sync --locked --group dev --offline --check` | PASS, 25 installed packages, would make no changes |
| `uv pip check --python .venv/bin/python --offline` | Installed metadata compatible |
| `uv pip list --python .venv/bin/python --format json --offline` | Version inventory retained; unchanged before/after |
| `uv run --offline --no-sync npm test` | Frontend-only safety-scaffold check passed; deployment gates remain refused |
| `uv run --offline --no-sync npm run build` | Local static build passed; generated files remain ignored |
| `python3 scripts/check_markdown_links.py` | PASS: 107 Markdown files, 229 local links, zero failures/unchecked fragments |
| `git diff --check` and protected-path/staged privacy checks | PASS; documentation-only inventory and unchanged accepted source |

```bash
uv run --offline --no-sync mypy packages/research packages/backtesting \
  packages/data/snapshots.py packages/data/quality.py packages/data/alpaca_historical.py \
  packages/data/corporate_actions.py packages/data/historical_models.py \
  packages/data/historical_normalization.py packages/data/historical_snapshots.py \
  packages/data/acquisition_budget.py packages/data/acquisition_plan.py \
  packages/data/acquisition_session.py packages/data/acquisition_cli.py \
  packages/data/action_reconciliation.py packages/data/candidate_publication.py \
  packages/data/historical_candidates.py packages/data/historical_qualification.py \
  packages/data/private_storage.py packages/data/research_calendar.py \
  packages/data/action_scope.py packages/data/checkpoint_budget.py \
  packages/data/requalification.py packages/data/requalification_cli.py \
  packages/risk packages/strategy/signals.py packages/ai/__init__.py \
  apps/workers/app/activities/research.py apps/workers/app/activities/__init__.py \
  apps/workers/app/workflows/research_experiment.py apps/workers/app/research_local.py \
  scripts/benchmark_research_pipeline.py
```

Nine pre-existing external-service tests remain gated: Alpaca account read/write (2),
managed database (2), news (1), OpenAI (3), Telegram (1). They were not represented as
executed tests, and no external broker-write request ran. The three warnings concern existing
legacy Temporal/Pydantic conversion. Actual local workflow/recovery/replay tests run
using the previously verified cached Temporal binary; no server download was needed.

An isolated clean install was additionally executed from cache:

```bash
UV_PROJECT_ENVIRONMENT=results/final-closure-clean-environment \
  uv sync --locked --group dev --offline
```

It installed the 25 locked packages with zero downloads. R1/R2 smokes in that clean
environment passed; 233 stable files, including all 99 numerical files, matched accepted
evidence. The existing `.venv`'s full 4,014-entry file/symlink/mode inventory was unchanged,
SHA `de820121b0a7d50b1b1a3cf0d7c9bf5253969cf2bd3fb8adf73b20e89e640bdc`.
Dependency inputs remained byte-identical. This qualifies the recorded Python 3.14.7
runtime, not an unexecuted multi-version or operating-system matrix.

## Public demonstration and deterministic verification

[The reproducibility guide](REPRODUCIBILITY.md) contains setup instructions, the executed
two R1 runs, exact inventory/hash/paired-byte inspection and optional R2, R4-A and R3 commands.
Initial dependency setup may use a network; experiment execution requires no credentials,
provider connection or managed service. Runtime metadata is explicitly separate.

The connected synthetic demonstration traverses dataset validation, features, strategy,
decisions, risk-constrained next-session simulation, accounting, metrics and artifacts.
Its 630 entry decisions plus one stop exit retain all rejections and two fills. There
is one closed trade and no terminal position. Independent Decimal arithmetic verifies
final cash/equity `9980.4831136` from initial cash `10000`, P&L `−19.5168864` and fees
`0.0328864`, using the existing `1e-8` USD binary64 comparison tolerance. These are
synthetic software expectations, not empirical performance findings.

All six fixture commands (R1/R2/R4-A, each twice) passed. All deterministic pair bytes
matched, and **238 generated artifact files** matched accepted R4-B/R4-B.2 baseline
bytes after excluding runtime metadata and revision-dependent manifests/reports. Numerical
projections remain:

| Fixture projection | Files | SHA-256 |
| --- | ---: | --- |
| R1 | 3 | `43c27422107eea69073743f8abdb810604ba60c36bb2da2d7a1efb32942411e2` |
| R2 | 96 | `c4eb58ad9932b90879c24cc03fed1b6b75234c215a20942d3face831a2d6b88d` |
| R4-A | 3 | `4b92e69392596f3bd11cecb98a173940e716e80d7fc5654254bed9acaa38506e` |

The exact public guide was executed verbatim for R1/inline verification/R2/R4-A.
The R3 executable placeholder was replaced by the verified existing local binary.
Both R3 invocations replayed distinct retained 11-event histories and returned the same
COMMITTED result: **one experiment, one execution attempt, one result and one completion
event**. Independent state verification checked all 294 indexed artifacts and the
durable ledger binding. Source/environment identity was not silently migrated.

Full run IDs/aggregate hashes include revision/environment provenance. Final-checkout
replays therefore use fresh output/state names and verify unchanged numerical bytes;
their own source-bound hashes are retained separately rather than copied from an older
commit. No historical strategy or real-data benchmark result was computed.

## Auditable local receipts and preservation

Generated receipts/logs remain ignored, rather than becoming another public result
collection. They contain exact argv, exit codes, versions, file inventories and log hashes.
The original verification index covers its capture-time files; the later preservation
operator/receipt are explicit supplements, covered separately by the final release audit:

| Relative local receipt | SHA-256 |
| --- | --- |
| `results/final-closure-verification-20261117/verification-receipt.json` | `960935067e02ff1e61629033b4117259ef2e9a0163e85bb9dccc9f10b30f73be` |
| `results/final-closure-clean-install-verification-20261117/clean-install-receipt.json` | `c5d1e1807c47687d00b9556309ef103ddd86fa65eeb2d4e90b39522380609e0f` |
| `results/final-closure-baseline-20261117/verification.json` | `14c4c556b9d14c0bd597e543aedb6a6f093bb67d93fce373d68ddfe6d0a2a89d` |
| `results/final-closure-baseline-20261117/synthetic-demo-audit.json` | `9551a4f18891760fc65663445381f5cdab5a764fa840a7fede07accbbbf1f1e3` |
| `results/final-closure-baseline-20261117/public-sequence/verification.json` | `1cc1b323af4d892fdcc43815fe7d0df73f1af4bdc407c5a6107363c0f6bb7428` |
| `results/final-closure-verification-20261117/preservation-receipt.json` | `2282f1d08abe03a891ad831407bcc62266b7eb79a63bb36930d613e25555b3a8` |

The preservation operator checked unchanged protected source/tests/config/locks/history
and independently recomputed the old negative qualification
`0a64c25cc9e9b179715da631ceb381e2beac01ef4f62b2f2e1fd9440f93b3621` and pilot strict
qualification `d98a64a0192dd342655fe1621a2f93fac2b7f5b7dfc0daf32cc50d71fbeece01`.
The pilot manifest remains
`44d4de820bbad745cc14b2cad11f6adf34b412b58d33f7b9aefa886a39df444f`.
All 11 indexed R4-B.2 partial-resolution files remain unchanged. No candidate is
admitted as v2; aggregate provider usage remains **5 attempts / 117,404 bytes**,
with no in-flight request. No private evidence is rewritten or reacquired.

## Historical research gates

These seven groups remain a concise future-work appendix, not a new acquisition plan.
None is silently waived by engineering closure or by a paid/free plan advertisement.

| Gate | Evidence still required before an empirical extension |
| --- | --- |
| G1 — Economic fields/classification | Resolve 13 currencies, one QQQ payment disagreement, eight exact-decimal interpretations and applicable classification with independent provenance |
| G2 — Complete action inventory | Establish complete cash/structural events, split consistency and treatment of the QQQ reorganization; pagination alone is insufficient |
| G3 — Identity/universe | Effective historical identities, mappings and explicit selection/survivorship restrictions; current tickers do not prove membership |
| G4 — Execution/aggregation | Qualified session/volume definitions and an explicit attainable-price or restricted proxy convention compatible with feature timing |
| G5 — Availability/revisions | Separate event, observation and correction times; credible cutoffs or owner-reviewed restricted assumptions without fictitious PIT/vintage claims |
| G6 — Rights | Authorized access, reproducible private retention and specific derived-publication rights; source code rights do not license provider observations |
| G7 — Scientific registration | Feasible multiyear SPY-plus-distinct-asset design, sufficient warm-up, predeclared evaluation, contamination audit and credible news or neutral-only scope |

The two-year IEX pilot does not cure these gaps. A narrower SPY-only study would also
conflict with the retained positive-relative-strength entry condition. No new scope,
split or threshold is chosen on the owner's behalf, and no empirical results are
fabricated to complete the portfolio narrative.

The [EODHD licensing correction](FINAL_DATA_FEASIBILITY.md#eodhd-licensing-correction--2026-11-17)
establishes conditional private storage and post-cancellation retention rights for
qualifying users. Project-specific public-derived licensing, owner entitlement and
dataset qualification remain unestablished. It does not qualify the existing IEX pilot
or change the empirical NO-GO.

## Security, publication and final repository state

The complete diff is restricted to the eight named Markdown files. Staged content is
reviewed for credentials, private observations/payloads, sensitive receipts and binaries;
private datasets, issuer workbooks, generated runs and the isolated test environment
remain ignored. Existing `.venv`, raw provider evidence and historical documents remain
intact. No credentials were loaded/forwarded, broker-write endpoint invoked, service
deployed, schedule enabled, CI activated, account changed or subscription purchased.

The original engineering-closure publication is recorded in
`results/final-closure-release-audit-20261117/release.json`, SHA-256
`62163b46669734ec65b0f129483576f9a12a6088c91de4598b1ba5076b8eeec9`.
That receipt and the earlier verification artifacts remain unchanged.

The final documentation pass uses a separate post-push receipt,
`results/final-presentation-20261117/release.json`. It records the literal presentation
revision, changed-file inventory, documentation checks and these observed conditions:

```text
local HEAD = origin/main = GitHub refs/heads/main
git status --porcelain is empty
protected source/config/test/dependency and historical paths are unchanged
no private/licensed input or generated empirical result is tracked
```

The presentation receipt and delivery message complete the Git observation after the
report's own commit. Publication uses a normal push only after confirming that the
remote has not advanced; synchronization is not inferred from a local commit succeeding.

## Final documentation and presentation pass

This final pass corrects the EODHD assessment using three separately authorized official
pages, improves the README's research objectives and evidence terminology, and clarifies
the implemented architecture, execution conventions and reproducibility conditions.
The [source report](FINAL_DATA_FEASIBILITY.md) preserves the original failed legal-URL
lookup and distinguishes that review from the corrective verification. The empirical
decision remains NO-GO; no data acquisition or historical research execution is authorized.

Implementation, tests, dependencies, parameters, fixtures and established numerical
artifacts are unchanged. Dated checkpoint verification reports retain their original
evidence and review status. Reproduction command blocks are checked against the
verified guide. The editorial checks passed 12 Markdown-link checker tests and validated
107 Markdown files with 232 local links. GitHub's Markdown API rendered all eight edited
pages. All three diagrams rendered with Mermaid's browser runtime and were visually
inspected; the README uses a top-down layout for legibility. The headless GitHub preview
did not load its rich diagram display, so that client preview is not claimed as a
successful rendering check. The separate browser-runtime results and privacy checks
are recorded in the presentation receipt. The repository is frozen for presentation
at the final documentation revision. No further development phase is proposed.

## Is further Codex work necessary?

**No further Codex engineering work is required for this defined portfolio closure.**
The existing verified framework, public synthetic reproduction, technical reports and
explicit data NO-GO constitute the delivered scope. The original scientific gate remains
pending. Any empirical extension would be a separate owner decision requiring qualified
rights/data and a reviewed registered design, not an automatic next R4-B or R4-C task.

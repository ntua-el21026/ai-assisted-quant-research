# R4-B implementation and verification — 2026-11-17

**Engineering verification: PASS for the bounded implemented path, including a verified
negative preflight. Dataset-to-R4-C: BLOCKED. Independent R4-B acceptance is pending.**
No pilot/larger historical dataset or historical strategy evaluation was executed.
The data failure is not reclassified as a successful dataset or empirical result.

## Repository and authority

Starting local `main`, `origin/main`, GitHub API `main` and `git ls-remote` main were
`0dd0875c9f4a1ff806a107badcd693922d9f7e29`. The tree was clean. Canonical GitHub metadata
identified `ntua-el21026/ai-assisted-quant-research`, default `main`; the SSH origin is
canonical. No redirect, reset, branch, PR, tag, history rewrite or unrelated edit is used.
The owner reports independent R4-A acceptance for synthetic engineering at that SHA.

Before implementation, the root instructions, complete governing specification/protocol/
architecture, R1–R4-A verification/implementation/acquisition documents and approved
implementation plans were inspected together with actual contracts, accounting,
benchmarks, artifacts, research runner and R3 SQLite/workflow tests. The current task
separately authorizes bounded personal IEX acquisition and local storage; it does not
authorize strategy studies, SIP inference, public vendor evidence or R4-C.

The exact implementation/file inventory and contract decisions are in
[R4B_IMPLEMENTATION.md](R4B_IMPLEMENTATION.md). The evidence/rights/readiness matrix is
in [R4B_DATA_QUALIFICATION.md](R4B_DATA_QUALIFICATION.md). R1/R2 numerical sources,
R3 ledger/workflows, fixtures, study parameters, dependencies and legacy evidence remain
unchanged. Only explicit IEX feed support, configurable action-quality filtering and an
optional bounded reader extend existing data interfaces; SIP/default behavior is retained.

## Environment and executed checks

Existing `.venv`: Python **3.14.7**, Pytest **9.0.3**, Ruff **0.15.12**, mypy **1.20.2**,
Pydantic **2.13.3**, Temporal SDK **1.27.0**, SQLite **3.53.1**. No dependency upgrade,
environment replacement or system installation occurred. The unchanged lock resolves
27 entries; environment check verifies 25 packages and would make no changes.

| Exact command | Observed result |
| --- | --- |
| `uv run --offline --no-sync pytest -q -rs` | **1,383 passed, 9 skipped, 0 failed/errors, 3 existing warnings**, 70.09 s, exit 0; log `results/r4b-verification-20261117/pytest-final.log` |
| Earlier same full-suite command | 1,382 passed, 9 skipped, 3 warnings, 64.38 s; final added synthetic special-preflight regression is included above |
| Focused command below | **317 passed**, 5.39 s, exit 0; initial settled run had 315 passing cases |
| `uv run --offline --no-sync pytest tests/unit/test_acquisition_session.py -q --tb=short` | **12 passed**, 3.47 s, exit 0, including the invented special-flag regression |
| `uv run --offline --no-sync ruff check .` | PASS, repository-wide, exit 0 |
| Expanded mypy command below | PASS, **55 source files**, exit 0 |
| `uv lock --check --offline` | PASS, exit 0 |
| `uv sync --locked --group dev --offline --check` | PASS, exit 0, would make no changes |
| `uv run --offline --no-sync npm test` | PASS, exit 0, frontend-only safety scaffold; no deployment or provider use |
| Python/Node root metadata assertions below | PASS, exit 0; names/versions/Python constraint/Node engines/dependency groups match locks |
| `python3 scripts/check_markdown_links.py` | PASS after staging new reports, **97 Markdown files/170 local links**, zero failures/unchecked fragments, exit 0; no remote link crawler or market API |
| `git diff --check` | PASS; repeated before staging |

The nine preserved skips are Alpaca account read/write smoke (2), managed database (2),
news (1), OpenAI (3) and Telegram (1). Their opt-in gates remain disabled. The suite
does **not** source Alpaca credentials. The three warnings are existing legacy
Temporal/Pydantic converter deprecations. Actual R3 workflow execution, retry/recovery,
SQLite reconciliation, interruption and replay tests run locally without skips.

Focused command:

```bash
uv run --offline --no-sync pytest \
  tests/unit/test_acquisition_budget.py tests/unit/test_acquisition_plan.py \
  tests/unit/test_acquisition_session.py tests/unit/test_candidate_publication.py \
  tests/unit/test_historical_candidates.py tests/unit/test_historical_qualification.py \
  tests/unit/test_research_calendar.py tests/unit/test_private_storage.py \
  tests/unit/test_action_reconciliation.py tests/unit/test_alpaca_historical.py \
  tests/unit/test_historical_normalization.py -q --tb=short
```

Scoped typing (repository-wide mypy is not represented as qualified):

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
  packages/risk packages/strategy/signals.py packages/ai/__init__.py \
  apps/workers/app/activities/research.py apps/workers/app/activities/__init__.py \
  apps/workers/app/workflows/research_experiment.py apps/workers/app/research_local.py \
  scripts/benchmark_research_pipeline.py
```

Lock metadata assertions independently parse `pyproject.toml`/`uv.lock` and check the
root package name/version and `requires-python`; `package.json` is compared with
`package-lock.json` root name/version/engines/dependencies/devDependencies. Both original
lockfiles and package metadata remain byte-unchanged from the accepted baseline.

Test-first evidence includes 21 missing-plan failures and 6 missing-session/CLI failures
before implementation, 14 missing-publisher failures and the agents' original budget,
candidate, calendar/storage and reconciliation RED cases. Review regressions reproduced
the pilot-action gate, lexical private-output escape, missing non-200 evidence,
duplicate cross-event action identity and partial-acquisition success-exit defects
before correction. Tests cover explicit no-cost feed/entitlement rejection, retries,
body/page/time/request budgets, redirects/proxies, malformed responses, exact pagination,
DST/closures, missing rows, provenance/revisions/identity, immutable snapshots and
private publication. The final special-flag regression uses **invented** event values,
never actual vendor observations. No existing test/tolerance was weakened or removed.

One intermediate integration run had 1,182 passing/30 failing/12 skipped cases while
calendar implementation and the absent local Temporal binary were unresolved. Another
intermediate broad run was interrupted (exit 130), not counted as passing. Final settled
results above supersede these implementation-stage outcomes without erasing them.

## Restored local Temporal tool

The accepted cached binary was absent after the previous checkpoint. Official download
resolution now points to a newer binary; that mismatch was recorded rather than
silently changing the accepted tool. The exact historical executable was recovered
from [official SDK Java v1.40.0](https://github.com/temporalio/sdk-java/releases/tag/v1.40.0),
verified and restored only to the previously absent
`/tmp/temporal-test-server-sdk-python-1.27.0`:

- Size **84,478,216 bytes**.
- SHA-256 `19defb9f7318c7cf249518b3642a735efb79876c2b6918afe312336476b796a5`.
- Actual targeted workflow/replay command:
  `uv run --offline --no-sync pytest tests/temporal/test_research_workflow_local.py::test_research_workflow_executes_actual_pipeline_and_replays_without_effects[run] -q --tb=short`
  — **1 passed**, exit 0, 1.57 s.

Ignored `results/r4b-tools/recovery-summary.json` records 15 direct public HTTP attempts
including redirects and **55,483,755 observed response-body bytes**, archive hashes and
unsuccessful candidate probes. Connector/document lookups are separate source research.
These are **test-tool** requests, not authenticated market-data requests. No package or
provider account was changed. The full suite subsequently used the byte-identical local tool.

## Actual authenticated acquisition and negative evidence

`credentials_available: true`. Credentials were loaded only programmatically by the
explicit acquisition command in [the implementation report](R4B_IMPLEMENTATION.md).
No values, headers, complete responses or credential-file contents were printed,
committed, logged or sent to another service; contents/permissions were unchanged.

| Query | Exact scope | Outcome |
| --- | --- | --- |
| GET `data.alpaca.markets/v2/stocks/bars` | SPY/QQQ, explicit IEX/raw/1Day, 2025-01-06–2025-01-10, limit 100, `asof=-` | HTTP 200, terminal page; 8/8 expected rows valid |
| GET `data.alpaca.markets/v1/corporate-actions` | SPY/QQQ, inclusive process dates 2024-01-01–2024-03-31, all types, `data_quality=all`, US, limit 1000 | HTTP 200, terminal page; 2 cash-dividend rows, one special flag; normalization fails |

Total: **2 authenticated requests, 1,457 successful/received body bytes, zero retries**.
Actual acquisition interval was 2026-11-17 **10:29:02.384488–10:29:03.914362 UTC**;
freeze was **10:29:03.914796 UTC**. These are observation times, not historical publication.
No SIP, account, broker, pilot, candidate or split/adjustment diagnostic request occurred.
The bounded runner stopped with `unsupported_corporate_action`; the result is preserved
privately. The initial acquired-evidence CLI returned exit 0 despite its explicit stopped
code; review added a failing fake-transport regression and corrected future stopped
acquisitions to exit 1. No real request was repeated to test that exit-code fix.

Private evidence root: `datasets/private/r4b/session-20261117/` (gitignored, files 0600).
Frozen manifest: `frozen/evidence/manifest.json`, **8 inventoried files**. Candidate
publication uses the accepted atomic writer; exact inventory and hashes load successfully.
There is **no admitted market-snapshot/v2** and no ledger experiment for these observations.

| Deterministic reference | SHA-256 |
| --- | --- |
| Registered request plan | `6eb3b0b4e425884aeda36ef284dd237047650b9caa55d34e5ef14c245bba0c49` |
| Official-schedule calendar input | `181922ef62e8e73c6edb9641abc776c4b7f67c680e00288ce27159947e2b400f` |
| Private candidate manifest | `8f9ed18dd45602979ca7ff1b35b6de332908ff75f26b325130ddffe0fba1335e` |
| Frozen envelope `hashes.json` | `a6fd227e8628fbe44335fc75c3cb3907e8fb13505c6c1e8f7d780c1ab859f609` |
| Offline `qualification.json` | `0a64c25cc9e9b179715da631ceb381e2beac01ef4f62b2f2e1fd9440f93b3621` |
| Offline `input-inventory.json` | `f046f08f61ae3e251609dc83a4b268743c1f9a86595ca8007a2d20f330639105` |
| Offline qualification `hashes.json` | `0063b5485b7a6dcb1a9ab4e1745fa61e3595cea156ceb53936199f8f31116fcf` |

Two separate offline CLI processes used `qualification-first` and `qualification-second`
under the same private workspace. Hash indexes and every indexed byte were compared
exactly: **identical**. Both diagnose FAIL/technical FAIL/BLOCKED. Runtime files are
excluded. Retained workspace contents after these checks were **745,318 bytes**, far
below 1 GiB; later qualification receipts legitimately add private bytes. The frozen
candidate and its inventory remain unchanged. Final-checkout replay uses fresh output
directories and the same pinned hashes; it does not reacquire observations.

## R1/R2/R4-A compatibility and deterministic outputs

Before edits, six original synthetic CLI invocations produced paired baseline evidence
under `results/r4b-baseline-0dd0875-20261117-qualification/`. Baseline receipt SHA:
`22206da1c974837a09f35f0d139e39960973b98edde90fd04f9c6887febd99dc`.
After Python implementation froze, all six invocations were repeated under
`results/r4b-final-0dd0875-frozen-20261117-qualification/`:

```bash
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --output <new-r1-output>
uv run --offline --no-sync python -m packages.research.cli evaluate \
  --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --output <new-r2-output>
uv run --offline --no-sync python -m packages.research.historical_demo \
  --dataset tests/fixtures/historical_snapshot/manifest.json \
  --security-id synthetic:001 --initial-cash 1000 --output <new-actions-output>
```

Each command was run twice to a fresh `*-a`/`*-b` directory. The ignored receipt contains
the exact expanded commands and return codes; all six exit 0. Every indexed artifact
and `hashes.json` within each pair is byte-identical. Source was stable across runs:
`dc51ba4fbe0b56702d1708bcd835b816e92e4839844b6e22275d4e5996e024e6`
over 143 Python source files. Receipt SHA:
`c7656337081f6537a596429d46db3d8af8037e5c9cde8d554bd1f92cdcb37679`.

| Synthetic path | Paired indexed files | Full deterministic aggregate | Invariant baseline-byte projection |
| --- | --- | --- | --- |
| R1 | 7 | `ff271dff7d11a112a18a023291780db04900d1d8a1504894631339cf1f4041e0` | 5 files; `228e4474603104d0d320ce12236edaa3296f29f4d25aaff4cadf728b66d24611` |
| R2 | 294 | `ea6c87593e1594ad305cfcccfb3b83c245211ef1ba08b89336c0c3670eea0d61` | 228 files; `28502e770b408d4b2af4bb9967d8ec30bd57046349e7c569605db7c9514d8b4a` |
| R4-A action demo | 7 | `738876edd46ec424837454d041c513649416e4bb815ec6db13813e607da84711` | 5 files; exact baseline bytes |

**238 stable files** match the accepted baseline byte-for-byte. Numerical-only
projections independently match R1 `43c27422107eea69073743f8abdb810604ba60c36bb2da2d7a1efb32942411e2`
(3 files), R2 `c4eb58ad9932b90879c24cc03fed1b6b75234c215a20942d3face831a2d6b88d`
(96), and R4-A `4b92e69392596f3bd11cecb98a173940e716e80d7fc5654254bed9acaa38506e`
(3). Source-dependent manifests/reports change legitimately. Revision/dirty-tree metadata
also change after commits; these aggregate hashes identify the recorded frozen-source
verification checkout, not a promise that future source commits have the same run ID.
The final checkout preserves invariant numerical bytes and frozen-candidate diagnostics.

R3 tests verify fresh identities against unchanged ordinary runners, durable ledger,
publication reconciliation and actual local replay. Existing identities are not migrated
to candidate/v2 data or new source contracts. The synthetic public v1/v2 fixtures remain
unaltered, credential-free and license-safe; no provider data replaced them.

## Independent issuer evidence

Three official workbook downloads used **4 unauthenticated GETs including one same-host
redirect**, **1,321,356 response bytes**, during 2026-11-17 **10:33:17–10:33:22 UTC**.
Issuer hosts were allowlisted and ambient proxies disabled; each source was bounded at
16 MiB and the total at 48 MiB. No Alpaca authentication was used or forwarded. These
independent issuer requests are separate from the two authenticated Alpaca requests;
the concrete Alpaca transport continues to reject every redirect.

Private root: `datasets/private/r4b/issuer-evidence-20261117/`. It contains 27 files,
**1,723,549 retained content bytes**, including source/download receipts, hashed
extraction operators, schema/date-style validation, extracted records and diagnostic
comparison. Workbooks/rows/operators remain private and were not staged.

| Reference | Bytes | SHA-256 |
| --- | --- | --- |
| SPDR historical distributions workbook | 584,557 | `4add18439e505ba6c114bea5d352ac68b1ea5420bc99abdf2e21500dd6f1faa2` |
| Invesco 2024 workbook | 365,290 | `79f40d466b77539c4579d90bb1d0f15521cb01f26f6450f0dd3b88185ac4dd0f` |
| Invesco 2025 workbook | 371,509 | `2a27df1879bac86a81363a01d731b446ea2cf1d581afc14198af951b04038798` |
| `independent-actions.json` | Private normalized records | `867e50207cd5f1a3630299d284793697db4485831a21cdc9882acafcc820227f` |
| `provider-issuer-preflight-field-comparison-v2.json` | Private diagnostic comparison | `355200b3fb764d767f6752b37fdc805e2f8025d04f9c1dff276f0ae7b7ab6b48` |
| `evidence-index.json` | Complete private file index | `f4bdcf82b5bd1c6ef0277748ad600c91d3aea0b45230074cc2bc90390388b719` |

There are 16 extracted pilot-window event records (SPY 8, QQQ 8) with explicit ex-date,
payable date and amount. ISO currency, historical declaration availability and full
inventory completeness remain unverified. The SPDR source has 136 SPY rows; QQQ has four
event rows in each annual Primary ICI sheet. Annual percentages/other sheets were not
duplicated as events. Counts alone are not a completeness guarantee.

Both provider events have 2023 effective dates outside the 2024–2025 normalized issuer
pilot. Broader SPDR history verifies one exact ex/pay/rate match. The special-flagged
record is outside the Invesco books' coverage, so neither its economic classification
nor currency is independently established. No source flag was changed and the rejected
event was never coerced into an ordinary modeled dividend. This is a field comparison,
not a complete action-inventory PASS.

Private operator hashes: `parse-workbooks.py`
`2d2184dbad4f5c3009775ae1eed2059d8e839bf0fa454ac751f626dff3096640`,
`normalize-and-compare.py`
`1cc6dbaf8877649a931e3390e90077fb4490b3e0080882258e9aa3ba8c5a1166`,
`preflight-coverage-comparison.py`
`f168a049307f68a299b1ef0245e4e71dcfe467a1adb212636918a9f62d995f09`.
Receipts preserve interim comparisons and corrections instead of overwriting them.

## Remaining limitations and review handoff

Independent issuer workbooks and their diagnostic comparison are private supplementary
evidence, not newly admitted action histories. Their observed source hashes, coverage,
missing-currency/availability limitations and comparison outcome are recorded with the
private evidence receipts; nothing is promoted by treating issuer records as ordinary
provider distributions. The dataset remains blocked even if economic fields agree.

No measured strategy return, empirical chart or AI-uplift claim is produced. Full-history
pagination, 2016–2019 completeness, actual DST/early-close aggregation, consolidated
execution semantics, permanent historical identity, provider revision history and causal
first-publication evidence remain unqualified. Retention and public derived-result rights
remain unresolved; SIP was not requested. No new study split/holdout status is registered.
The existing special-distribution rejection is preserved. Engineering PASS concerns
tested bounded transport/storage/diagnostics and honest negative-state behavior, not
successful completion of the planned pilot or a qualified dataset.

Implementation commits on main:

1. `5dc301810624ae527f79297d449e3dfa5487cf7b` — explicit IEX/shared finite budgets.
2. `b491bbf99f6d09f6fbf25a8c23936a5c78222f98` — private candidate/qualification pipeline,
   synthetic tests and registered calendar/request plan.

The subsequent documentation commit and post-push equality are recorded in the release handoff.
This report cannot embed its own future Git object hash. Final delivery must verify
`git rev-parse HEAD`, `git rev-parse origin/main`, `git ls-remote origin refs/heads/main`
and a clean tree after a non-force push. Private evidence and ignored local test tools
remain local; no deployment/CI/account mutation is authorized.

**Stop after R4-B. R4-B awaits independent acceptance; R4-C requires separate authorization
after data-blocker resolution and requalification.**

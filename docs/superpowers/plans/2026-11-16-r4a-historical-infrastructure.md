# R4-A historical infrastructure implementation plan

The owner's detailed R4-A request authorizes implementation on `main`, synthetic-only
verification and publication after checks. Starting clean HEAD/origin/GitHub main is
`60dd250c52254ab1f08f7042971967467f05b11f`. This bounded extension does not authorize
R4-B, acquisition, revised research dates or empirical experiments.

## Design and alternatives

Preserve the accepted v1 loader, strategy, simulator, benchmarks, CLI and R3 workflow.
Add an explicit v2 loader and isolated action accounting/benchmarks. Reinterpreting v1
would invalidate established provenance; adding action branches throughout the old
simulator now would expand into unapproved historical strategy execution. A separate
synthetic qualification command exercises the new foundation without either change.
These implementation choices follow the authorized compatibility and bounded-scope
requirements; they are submitted for independent acceptance with the implementation.

Provider transport is injected and has no environment/credential discovery. Its optional
concrete HTTP adapter accepts caller-supplied authentication, permits only the official
read-only data paths, disables redirects and is tested through mocked HTTP. No acquisition
command is exposed. Normalization is pure and explicit about calendar, price basis,
information availability, acquisition and missing data. Historical storage/retention
rights must be confirmed before a real v2 input is accepted.

V2 stores immutable raw execution observations and explicit security mappings, sessions,
acquisition receipts, action inventory and licensing/revision provenance. Feature views
use only observations and effective splits available at the cutoff. Fully adjusted
provider bars are not silently admitted as causal raw execution or features.

Actions use Decimal arithmetic, pre-open holdings, split-before-dividend ordering and
cash entitlements recognized on ex-date, paid once on/after payment date. Fractions are
either exact or rejected explicitly; cash-in-lieu is unsupported without a valuation
policy. Benchmarks distinguish price return, cash total return and payment-open dividend
reinvestment, include unpaid receivables in equity, and disclose frictionless fractional
units and payment-time assumptions. No historical strategy rules or thresholds change.

## Tasks and interfaces

### 1. Typed acquisition and HTTP boundary

- New `packages/data/alpaca_historical.py` and `tests/unit/test_alpaca_historical.py`.
- `HistoricalBarsRequest`, `CorporateActionsRequest`, injected `HttpTransport`, bounded
  retry policy, explicit optional urllib transport, acquisition receipts and pure
  normalization. Explicit SIP, adjustment, timeframe, symbols, dates, mapping and USD.
- RED: mocked pagination, rate-limit, malformed/error, timestamp and sanitization cases.
- GREEN: run the new test module, Ruff and scoped mypy. No actual Alpaca calls.

### 2. Action domain and accounting

- New `packages/data/corporate_actions.py`,
  `packages/backtesting/corporate_actions.py`, and new unit tests.
- `SplitAction`, `CashDividendAction`, `validate_actions`, immutable
  `PortfolioActionState`, `AccountingPosition`, `PendingOrder`, and
  `apply_session_actions(state, actions, *, session, as_of, fractional_policy)`.
- RED: literal 4:1/10:1 quantity/basis/stop/order expectations, separate dividend dates,
  zero eligibility, fractions, repeats, missed/late actions and contradictory records.
- GREEN: verify independent Decimal expectations and no legacy changes.

### 3. V2 local snapshot and causal feature view

- New `packages/data/historical_snapshots.py`,
  `tests/unit/test_historical_snapshots.py`, and clearly synthetic JSON fixture.
- `HistoricalSnapshotManifest`, `HistoricalBar`, `HistoricalSnapshot`,
  `load_historical_snapshot(Path)` and `snapshot.feature_view(cutoff, basis=...)`.
- RED: integrity, complete inventory, raw-only prices, license gates, missing sessions,
  mappings, DST, revision immutability, acquisition/availability ordering, and future
  action exclusion. Existing `load_dataset_snapshot` must still reject v2 explicitly.
- GREEN: new module plus accepted v1 snapshot/decision tests.

### 4. Action-aware benchmark accounting

- New `packages/research/historical_benchmarks.py` and its new unit tests.
- Explicit price-return/cash-total-return/reinvested-total-return conventions, daily
  cash/receivable/units/basis/equity, comparison compatibility validation.
- RED: independently calculated split/dividend paths, payment-open reinvestment,
  action-free parity, missing prices and incompatible comparisons.
- GREEN: new and existing benchmark suites with old results unchanged.

### 5. Synthetic qualification artifacts and documentation

- New `packages/research/historical_demo.py` and
  `tests/integration/test_historical_infrastructure.py`.
- Offline synthetic-only command accepting explicit v2 manifest/output, using the
  existing deterministic serializer/atomic publisher; separate runtime metadata.
- RED: numerical results, immutable outputs, no network/provider imports, byte/hash
  repeatability, corrupted input rejection, and historical-kind refusal.
- GREEN: repeat the actual command; retain hash-indexed results under ignored storage.
- Document usage, v2 contract, accounting/reinvestment assumptions, unsupported actions,
  current rights/quality/scientific blockers and independent-review handoff.

## Review focus

Each boundary has named tests: future split cannot restate an earlier feature view;
an ex-date purchase earns no prior-holder dividend; a later split cannot multiply an
existing cash entitlement; retries/page order cannot duplicate bars; unknown identity,
missing declared action, changed snapshot bytes or unconfirmed storage rights fail closed.
Payment-open reinvestment is an explicit synthetic convention, not an empirical guarantee.

## Final verification and delivery

1. Run full `uv run --offline --no-sync pytest -q -rs`, including actual cached local
   Temporal/replay and legacy tests; report external-service skips individually.
2. Run repository-wide Ruff, expanded existing mypy scope, Markdown links, lock and
   installed-environment consistency, frontend checks and `git diff --check`.
3. Compare final R1/R2 numerical and all non-manifest/report artifacts with independently
   captured clean-baseline outputs. Source/revision manifests intentionally change.
4. Commit coherent tested source groups on main, then perform two independent final-HEAD
   runs for R1/R2 and the new synthetic command. Verify full inventories and every hash.
5. Record evidence in `docs/research/R4A_VERIFICATION.md`; preserve old handoffs/evidence.
6. Confirm remote has not moved, push without force, verify clean HEAD/origin/GitHub equality.
   A final documentation commit changes HEAD-bound run identities; report qualification
   source SHA and final publication SHA separately and rerun final-HEAD parity.

No dependencies, credentials, provider observations, trading authority, schedules,
infrastructure or registered historical periods are changed. Stop after R4-A.

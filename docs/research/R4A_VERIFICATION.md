# R4-A implementation and verification — 2026-11-16

**Acceptance update, 2026-11-17: R4-A independently accepted at
`0dd0875c9f4a1ff806a107badcd693922d9f7e29` for synthetic engineering scope.**
The evidence below records R4-A, when historical acquisition and empirical execution
had not begun. Subsequent acquisition is reported separately in [R4-B](R4B_VERIFICATION.md).
All R4-A market/action observations and
acquisition receipts are original synthetic fixtures or mocked HTTP responses.
No empirical performance, AI benefit or overall research-completion claim is made.

## Repository, scope and source

Starting main, cached origin/main, remote main and GitHub main matched the reviewed
baseline `60dd250c52254ab1f08f7042971967467f05b11f`, with a clean tree and canonical
`ntua-el21026/ai-assisted-quant-research` identity. Origin remains
`git@github.com:ntua-el21026/ai-assisted-quant-research.git`. Work used main only.

| Commit | Change |
| --- | --- |
| `0d67f6695ead3bc81688fc395729b2bb7d17fc5b` | Isolated action domain/accounting, literal regression fixtures and bounded plan |
| `44679b302f47fd302c3a914293b84c55052cf5b3` | Explicit SIP acquisition, exact normalization bridge, v2 snapshot contracts/fixture |
| `9a566868ea83962fb8822605687c4f1e30311031` | Action-aware analytical benchmarks, synthetic artifacts and active documentation |

The executed source qualification below identifies **`9a56686`**, clean before this
report was written. A documentation commit follows. Existing run identity binds actual
HEAD, so that commit changes run IDs/manifests without changing numerical results.
Final-HEAD two-run verification and actual HEAD/origin/GitHub synchronization are
recorded after publication in the user-facing handoff and ignored
`results/r4a-final-handoff.json`; this report does not invent its own future commit SHA.
Resolve the report's publication commit with `git log -1 --format=%H -- docs/research/R4A_VERIFICATION.md`.

No Alpaca credentials were inspected, loaded, modified or printed. No authenticated
Alpaca request, dataset download, broker operation, account change, subscription,
deployment, schedule or Actions activation occurred. Existing `.venv`, dependencies,
locks, registered study dates, thresholds, old reports and historical evidence remain
unchanged. No branch, PR, tag or history rewrite was created.

## Implemented files and interfaces

[Detailed contracts](R4A_IMPLEMENTATION.md) and [acquisition reference](R4A_ACQUISITION.md)
document usage, exact semantics, boundaries and unsupported conditions.

| New source | Interfaces/responsibility |
| --- | --- |
| `packages/data/alpaca_historical.py` | Typed explicit SIP requests, injected HTTP, restricted optional urllib transport, bounded retries/pages/bytes, exact normalization |
| `packages/data/historical_normalization.py` | Exact normalized observations and full query/page receipts → v2 domain, without writing snapshots |
| `packages/data/historical_models.py` | Frozen `market-snapshot/v2` schema, raw execution, calendar, identity, availability, revision and rights |
| `packages/data/historical_snapshots.py` | Local loader, pinned integrity, complete declared inventory, raw/split-as-of feature views |
| `packages/data/corporate_actions.py` | Split/cash-domain records, duplicate/contradiction validation, compact semantic fingerprints |
| `packages/backtesting/corporate_actions.py` | Immutable pre-open action state; quantities, cost basis, stops/orders, entitlement and payment |
| `packages/research/historical_benchmarks.py` | PR/cash-TR/reinvested-TR, exact rational arithmetic and explicit compatibility checks |
| `packages/research/historical_demo.py` | Synthetic-only qualification CLI and `historical-infrastructure-artifacts/v1` publication |

New tests are five focused unit modules and
`tests/integration/test_historical_infrastructure.py`; the v2 JSON fixture has an explicit
synthetic README. Active README/specification/architecture/protocol/index and dataset
documentation describe the implemented subphase. Earlier checkpoint reports remain intact.

There are **no changes to any existing Python source, existing test or accepted fixture**.
Ordinary research CLIs, v1 artifacts, risk, strategy, legacy backtesting and R3 workflow/
ledger remain unchanged. V2 is not silently passed into v1. No action-aware strategy
backtest or new R3 mode was introduced; that integration needs separate authorization.

## Independent numerical and causal evidence

All expectations below are literal arithmetic checks rather than expectations produced
by the implementation under test.

| Case | Independent expectation |
| --- | --- |
| 4:1 split | Quantity ×4; per-share cost/stop/order price ÷4; total cost basis invariant |
| Subsequent 10:1 split | Quantity ×10 and per-share levels ÷10; earlier fixed dividend entitlement unchanged |
| 1000 at raw opening price 400 | 2.5 analytical units; after both splits, 100 units with cost basis 1000 |
| Dividend 1, ex March 12/pay March 14 | Ten eligible pre-open units create receivable 10; no cash before pay; one cash credit 10 |
| Final mark 11, no dividend inclusion | Price-return equity 1100 |
| Same path, cash dividends | Cash 10 + market value 1100 = equity 1110 |
| Reinvest payment cash at open 10 | Buy one additional unit; 101 × final 11 = equity 1111 |
| Inert one-unit pending order at 400/stop 360 | After both splits: quantity 40, limit 10, stop 9; held-position stop also 9 |
| Ex-date opening purchase/zero position | Zero dividend entitlement; later sales do not remove previously earned cash |
| Reverse split creating 2.5 units | Explicit fractional rejection or exact finite-Decimal mode; no invented cash-in-lieu |

The six-session action-ledger equities are **1000, 1000, 1000, 1000, 1010, 1110**.
Every point matches the separately implemented exact-rational cash-TR comparator.
The command is an analytical initial allocation with inert stop/order conversion probes,
not a new strategy, order simulator or relaxation of accepted risk constraints.

Tests also cover consecutive/same-day actions, entitlement survival after sale/later
split, weekend payments, repeated transitions, changed/missing inventory, restored-state
contradictions, incompatible comparisons, recurring fractional benchmark units and
ambient Decimal-context independence. Finite-Decimal accounting traps inexact operations;
analytical benchmarks retain exact rational provenance and explicitly rounded reporting.

Causality tests verify that future effective splits do not restate earlier views;
unavailable bars and identity mappings cannot enter features; unavailable effective
actions fail closed; and a corrected snapshot cannot supply pre-correction feature
views. A separate synthetic mutation changed a first price from 400 to 420/500:
the original fixture remained unchanged and the corrected pre-observation run failed.
Observed availability cannot predate its linked request; synthetic evidence cannot
be relabeled as historical. Unknown/uncertain identities require rejection or an
explicit warned restriction. DST, early closes, rename intervals, missing/duplicate
sessions, broken hashes and incomplete query/action provenance are covered.

## Executed tests and static checks

Retained environment: CPython **3.14.7**, SQLite **3.53.1**, Pytest **9.0.3**, Ruff
**0.15.12**, mypy **1.20.2**, Pydantic **2.13.3**, Temporal SDK **1.27.0**.
No installation, upgrade or environment recreation was needed.

| Exact command | Observed result |
| --- | --- |
| `uv run --offline --no-sync pytest tests/unit/test_corporate_action_accounting.py -q` | **61 passed** |
| `uv run --offline --no-sync pytest tests/unit/test_alpaca_historical.py tests/unit/test_historical_normalization.py -q` | **85 passed**, all HTTP mocked |
| `uv run --offline --no-sync pytest tests/unit/test_historical_snapshots.py -q` | **49 passed** |
| `uv run --offline --no-sync pytest tests/unit/test_historical_benchmarks.py -q` | **27 passed**, including actual v2 loader fixture |
| `uv run --offline --no-sync pytest tests/integration/test_historical_infrastructure.py -q` | **10 passed**, actual command, no-network and immutable publication |
| `uv run --offline --no-sync pytest -q -rs` | **1151 passed, 9 skipped, 0 failed/errors**, 37.06 s, 3 existing warnings |
| `uv run --offline --no-sync ruff check .` | PASS, repository-wide after line-wrapping corrections |
| Expanded mypy command below | PASS, **45 source files** |
| `uv lock --check --offline` | PASS, 27 lock entries |
| `uv sync --locked --group dev --offline --check` | PASS, 25 installed packages; would make no changes |
| `uv run --offline --no-sync npm test` | PASS, frontend-only historical-preview safety checks; no deployment |
| `python3 scripts/check_markdown_links.py` | PASS, **92 Markdown files/143 local links**, zero failures/unchecked fragments |
| `git diff --check` | PASS |

```bash
uv run --offline --no-sync mypy packages/research packages/backtesting \
  packages/data/snapshots.py packages/data/quality.py packages/data/alpaca_historical.py \
  packages/data/corporate_actions.py packages/data/historical_models.py \
  packages/data/historical_normalization.py packages/data/historical_snapshots.py \
  packages/risk packages/strategy/signals.py packages/ai/__init__.py \
  apps/workers/app/activities/research.py apps/workers/app/activities/__init__.py \
  apps/workers/app/workflows/research_experiment.py apps/workers/app/research_local.py \
  scripts/benchmark_research_pipeline.py
```

The 232 new cases execute without skips. The nine existing skips are Alpaca write/read-only
(2), managed database (2), news (1), OpenAI (3) and Telegram (1); none were enabled.
The three warnings are unchanged legacy Temporal/Pydantic conversion deprecations.
The full suite executes the actual cached local SDK workflow/replay/recovery cases,
not mocked workflow registration. Cached server SHA remains
`19defb9f7318c7cf249518b3642a735efb79876c2b6918afe312336476b796a5`.

TDD evidence: acquisition began with 39 missing-module failures; accounting with 36;
snapshot with 38; benchmarks with 21; bridge/exact-byte-budget wave with 14; synthetic
integration with 10. Expanded regressions reproduced confidentiality/stream-close,
split-direction/currency/share-basis, JSON duplicates/page times, Decimal context,
snapshot identity/observed-time/correction and compact fingerprint defects before fixes.
One parallel unit run saw only the then-missing snapshot implementation fail (38),
with 973 passing/1 existing skip; settled full runs passed. No existing test was weakened,
removed or disabled. Intermediate type/style failures were corrected, not excluded.

Python/Node root metadata were independently parsed and compared with their locks;
name/version/Python requirement and Node engines/dependency groups matched. Git no-diff
checks also confirm lock/configuration, legacy workers/ledger, prior handoffs, historical
evidence/deployment and accepted fixture preservation. The Markdown checker verifies
local targets/fragments offline; it does not claim external website availability.

## Reproducibility and unchanged baseline

Before edits, ordinary CLI run/evaluate were each executed twice at clean baseline.
After source commit `9a56686`, these exact commands each ran with suffixes `a` and `b`:

```bash
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --output results/r4a-qualified-9a56686-r1-a
uv run --offline --no-sync python -m packages.research.cli evaluate \
  --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --output results/r4a-qualified-9a56686-r2-a
uv run --offline --no-sync python -m packages.research.historical_demo \
  --dataset tests/fixtures/historical_snapshot/manifest.json \
  --security-id synthetic:001 --initial-cash 1000 \
  --output results/r4a-qualified-9a56686-actions-a
```

An independent standard-library verifier checked exact recursive inventory, safe regular
paths, every indexed SHA, manifest/index agreement and byte parity including the index.
Runtime metadata is intentionally excluded from cross-run identity.

| Pair at `9a56686` | Indexed files, excluding index/runtime | Aggregate SHA-256 |
| --- | ---: | --- |
| R1 compatibility | 7 | `9dac8f4cdd09714b8bad18cfc93396073faac361dd2b91aa5edc5cd14126d7e8` |
| R2 development, 32 cases/16 pairs | 294 | `d3215e8ccc223b66a89d0d9bcaecdc123e4c15ad016f98b0c710d7e709a94f50` |
| New synthetic action qualification | 7 | `fe980d7a6afb0dae4472a7f82664019ac6720bb01260130f4139c4ec1c5ac258` |

New synthetic run ID:
`99617258d563aedc4433a42f77cad457a17ebf349b19c06faf8f6b5a0741be4d`;
hash-index SHA `ad82dab55a8885a60726efbc7ea7da9cb458727d6afc884c774bde5c7afefd4a`.
The qualification receipt is ignored `results/r4a-qualification-9a56686.json`, SHA
`63fc618257497dbf5bfadc5c3c6bb5290def747a79e7224703746e5a07e35212`.

Input hashes:

| Original synthetic v2 input | Bytes | SHA-256 |
| --- | ---: | --- |
| Manifest | 6337 | `6b8d166a98c9e5f12126ce0a649eec8deba85a9a0fa3ff6263ecb6f522a59b5e` |
| Raw bars | 1863 | `03d92a2492d86661e4d41e42f1dcc28814f9c35fbfdfea3cf0fe44ad91d1ba69` |
| Actions | 887 | `d665c0b91ddcbb7041a6216eafd74599571606a1b106c87deaf0d49faccccccd` |

All R1/R2 indexed files **except manifest/report basenames** match the clean baseline
byte-for-byte, including all benchmark, AI, uncertainty, fold/configuration, comparison
and matrix artifacts. Source/revision-dependent provenance changes intentionally.

| Unchanged projection | Files | Canonical filename→SHA mapping digest |
| --- | ---: | --- |
| R1 accounting/trades/equity | 3 | `43c27422107eea69073743f8abdb810604ba60c36bb2da2d7a1efb32942411e2` |
| R2 accounting/trades/equity | 96 | `c4eb58ad9932b90879c24cc03fed1b6b75234c215a20942d3face831a2d6b88d` |
| R1 excluding manifests/reports | 5 | `228e4474603104d0d320ce12236edaa3296f29f4d25aaff4cadf728b66d24611` |
| R2 excluding manifests/reports | 228 | `28502e770b408d4b2af4bb9967d8ec30bd57046349e7c569605db7c9514d8b4a` |

R1 still closes one QQQ share: P&L **−19.5168864 USD**, fees **0.0328864 USD**,
terminal cash/equity **9980.4831136 USD** within its unchanged binary64 tolerance.
R3 continues binding complete source identity: a new checkout requires new experiment
identity/state or the original qualified source to resume old evidence. No old ledger
was migrated, rewritten or adopted under changed provenance.

## Review and remaining limits

Task-level adversarial reviews reproduced defects and verified their test-first fixes.
The fresh immutable-patch review covers `60dd250..9a56686` and found **no actionable
defects or blocking findings**. It independently executed 108 accounting/benchmark/
normalization cases and a delegated 49-case snapshot/model review. Existing executable
sources were confirmed unchanged. This is internal engineering review, not the
independent acceptance reserved for the owner/external reviewer.

Supported conditions and scientific/legal blockers are detailed in
[the contract](R4A_IMPLEMENTATION.md#deferred-decisions-and-blockers). In particular:

- No full historical acquisition/publication is authorized while written rights are pending.
- Snapshot completeness, calendar accuracy, identity truth and action inventory are external
  evidence obligations. Hashes establish bytes, not vendor truth or historical availability.
- USD ordinary cash dividends/splits only; unsupported actions and ambiguous same-date
  provider split/dividend rates fail closed. No cash-in-lieu/withholding/FX/interest.
- Payment-open cash availability is an analytical assumption; no actual settlement evidence.
- Corrected-vintage stitching and v2 strategy/R3 integration are not implemented.
- HTTP socket timeouts, page/body/wait limits are bounded; there is no global wall-clock
  deadline or claim that the raw-body cap bounds decoded-object peak memory.
- Real SIP continuity, early dividends, adjustment-factor reconciliation, symbol mappings,
  session/volume conventions, earnings/PIT/delistings/news and design contamination remain
  qualification work. Study dates/thresholds were not changed and no study was run.
- Other Python versions/platforms, hostile coordinated edits, abrupt host/power failure
  or production durability are not newly qualified by this checkpoint.

Stop after R4-A. R4-B and later phases require independent review and explicit authorization.

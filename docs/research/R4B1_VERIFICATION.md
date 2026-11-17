# R4-B.1 verification — 2026-11-17

**Engineering: PASS. Dataset-to-R4-C: BLOCKED. Independent R4-B.1 acceptance pending.**
The pilot was acquired and its 1,004 raw bars passed internal quality checks. Relevant
action/currency, payment, identity, availability, aggregation and admission gates remain
unresolved. The 2020–2025 candidate and R4-C were not executed.

## Baseline, authority and implementation

Initial local main, origin/main and remote main matched
`a6d3a0960e5924ab2f2969d02a1620e87b007101`, with a clean working tree and canonical
SSH origin `git@github.com:ntua-el21026/ai-assisted-quant-research.git`. The owner
independently accepted R4-B engineering; dataset acceptance remained blocked. Governing
instructions/specification/protocol/architecture/plans, R4-A/R4-B contracts and evidence,
actual source/tests and the hash-pinned private inputs were inspected before changes.

The [implementation report](R4B1_IMPLEMENTATION.md) inventories interfaces and rules.
The [qualification report](R4B1_DATA_QUALIFICATION.md) records primary-source facts,
uncertainties and scientific implications. The [plan](../superpowers/plans/2026-11-17-r4b1-requalification.md)
and new request/policy files precede the new provider observations.

New modules/tests: `action_scope.py`/`test_action_scope.py`,
`checkpoint_budget.py`/`test_checkpoint_budget.py`,
`requalification.py`/`test_requalification.py`,
`requalification_cli.py`/`test_requalification_cli.py` under `packages/data` and
`tests/unit` respectively. Existing acquisition budget/session/CLI, private storage
and candidate failure-code interfaces receive backward-compatible extensions and
explicit authority-safety restrictions. Two new JSON plans preserve old registration.
Extended existing tests are `test_acquisition_budget.py` and `test_acquisition_session.py`.
R1/R2 numerical, R3 workflow/ledger, fixture, lock and historical evidence files are
unchanged. No deployment, schedules, branches, PRs, tags or broker operations were used.

Implementation commits:

1. `e39b786838c22cfed0852049ab7c60e5483ffc10` — economic scope and aggregate budgets.
2. `93a939c19e9ad9515f0ace7a6b2c73f354b78bd5` — scoped pilot pipeline, guarded CLI,
   immutable evidence and versioned request/policy.
3. `e169d0d56b822800d92a91b83c813832ae6010d3` — explicit applicable-currency finding.

Acquisition genuinely ran at the original revision with the implemented working-tree
source fingerprints. **Every recorded acquisition source hash matches commit
`93a939c` exactly**, verified before that commit. The later two-line finding and its
test are a separate reporting refinement, not a data correction. No evidence was
rewritten to claim that a later commit existed at acquisition time. Final qualifier
source hashes identify that later diagnostic version explicitly.

## Environment and verification commands

The existing environment was retained: Python 3.14.7, Pydantic 2.13.3, Pytest 9.0.3,
Ruff 0.15.12, mypy 1.20.2, Temporal SDK 1.27.0 and SQLite 3.53.1. No new dependency,
environment replacement or system installation was needed.

| Exact command | Outcome |
| --- | --- |
| `uv run --offline --no-sync pytest -q -rs` | **1,495 passed, 9 skipped, 0 failed/errors, 3 warnings**, 43.58 s, exit 0; `results/r4b1-verification-20261117/pytest-final-source.log` |
| Earlier full-suite command | 1,494 passed/9 skipped/3 warnings, 43.64 s; before the explicit currency-finding regression |
| Focused command below | Pre-acquisition **323 passed**, 9.55 s, exit 0; later additional diagnostic test included in full suite |
| `uv run --offline --no-sync pytest tests/unit/test_action_scope.py tests/unit/test_requalification.py tests/unit/test_requalification_cli.py -q --tb=short` | **74 passed**, 5.30 s, exit 0 |
| `uv run --offline --no-sync ruff check .` | PASS, repository-wide, exit 0 |
| Established expanded mypy command below | PASS, **59 source files**, exit 0 |
| `uv lock --check --offline` | PASS, exit 0, 27 entries |
| `uv sync --locked --group dev --offline --check` | PASS, exit 0, 25 packages; would make no changes |
| `uv run --offline --no-sync npm test` | PASS, exit 0, frontend-only safety preview; no deployment/provider activity |
| `git diff --exit-code -- pyproject.toml uv.lock package.json package-lock.json packages/backtesting packages/research packages/risk packages/strategy apps/workers tests/fixtures` | PASS, protected numerical/fixture/workflow/dependency paths unchanged |
| Python/Node lock metadata assertions | PASS; root names/versions/Python constraint/Node engines/dependency groups unchanged and consistent |
| `python3 scripts/check_markdown_links.py` | PASS after staging: **101 Markdown files/196 local links**, zero failures/unchecked fragments, exit 0 |
| `git diff --check` and staged-file privacy scans | PASS before commits; only source, synthetic tests, metadata plans and sanitized documentation staged |

Focused command:

```bash
uv run --offline --no-sync pytest tests/unit/test_requalification.py \
  tests/unit/test_requalification_cli.py tests/unit/test_action_scope.py \
  tests/unit/test_checkpoint_budget.py tests/unit/test_acquisition_budget.py \
  tests/unit/test_acquisition_session.py tests/unit/test_private_storage.py \
  tests/unit/test_historical_candidates.py tests/unit/test_historical_qualification.py \
  tests/unit/test_alpaca_historical.py tests/unit/test_historical_normalization.py -q --tb=short
```

Scoped typing (not a claim of repository-wide mypy qualification):

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

The **112 added cases** execute without skips. Nine existing external-service cases
remain gated: Alpaca account read/write smoke (2), managed database (2), news (1),
OpenAI (3), Telegram (1). Credentials were not exported into the suite. The three
warnings are unchanged legacy Temporal/Pydantic conversion deprecations.

R3 actual workflow, recovery, interruption, SQLite reconciliation and replay tests run
in the full suite using the accepted local executable, SHA
`19defb9f7318c7cf249518b3642a735efb79876c2b6918afe312336476b796a5`.
No new test-server download or external service was required in R4-B.1.

TDD evidence: 45 initial missing-scope failures; 24 initial budget/authority failures;
10 initial missing-requalification failures; three missing-CLI failures; three missing
runner-hook failures. Expanded regressions reproduced authority reset/nested lock,
malformed/NaN row loss, inherited receivables, source-report binding, unsafe default
writers, callback failure, pilot stop, mutation of returned original diagnostics and
error-page provenance defects before fixes. Six malformed retry-page variants failed
while the valid variant passed, then all passed after full-chain validation. The final
missing-currency finding reproduced a KeyError before correction. One intermediate
integration run had 170 passing/one failing immutability case during its RED cycle;
the settled full suite passed. Existing assertions/tolerances were not weakened. The
legacy partial-CLI test gained only temporary-repository injection to isolate it from
the real aggregate authority marker.

## Actual acquisition, budget and protected evidence

Offline plan command:

```bash
uv run --offline --no-sync python -m packages.data.requalification_cli plan \
  --policy experiments/configs/r4b1_requalification.json
```

Outcome: exit 0, network false, IEX, two reused preflight requests; pinned policy/plan
load verifies 59 referenced files and 16 independent issuer records without credentials.

Executed acquisition:

```bash
uv run --offline --no-sync python -m packages.data.requalification_cli acquire \
  --allow-network --policy experiments/configs/r4b1_requalification.json \
  --workspace /home/peppasmich/projects/ai-assisted-quant-research/datasets/private/r4b/session-r4b1-20261117-v1 \
  --credentials-file /home/peppasmich/.config/ai-quant-research/alpaca.env
```

`credentials_available: true`. Values/content/headers were never displayed, logged,
mutated or committed. The command exited **1**, retained a new failed candidate and
reported terminal `invalid_corporate_action`; this is not a successful dataset admission.
Two GETs fetched the raw daily IEX SPY/QQQ 2024–2025 bars; one fetched all-type actions
over the registered inclusive 2024-01-01–2026-11-16 process window with `data_quality=all`.
All three returned HTTP 200. No retries or larger requests followed.

New usage **3 requests / 115,947 bytes**; prior charged usage **2 / 1,457**; aggregate
**5 / 117,404**, all successful-body bytes, no in-flight reservation. The closed authority
has sequence 63 and head
`d192472a8a73d6c60263891d3f9ddb0c51d67204053a9df75f4d987fd65e9bb4`.
Seed journal SHA:
`19efd26e6ccb5f995e49b08db1682600ad1066f88eacbdcce6d384bedbced925`.
Aggregate private contents after first paired qualifications were **6,834,029 bytes**,
well below 1 GiB. Later replay receipts add private bytes without new network usage.

The [qualification matrix](R4B1_DATA_QUALIFICATION.md) records 1,004/1,004 valid bars,
24 cash rows, 16 applicable and eight outside, missing currency, independent date/rate
checks, numeric precision evidence and actual failed scientific gates. No source field,
payable date, amount, special flag or old qualification was edited to pass.

Other authorized native retrievals were one official 2023 workbook GET (345,473 bytes)
and three currency-document download invocations (2,123,995 body bytes). Redirect hops
for the latter were not separately instrumented; no exact on-wire count is claimed.
Official documentation/search connector operations have no observable internal byte
counter and are separate from authenticated market-data accounting. All materials
remain private. No support message, order/account mutation, SIP query, payment,
subscription change, deployment or schedule occurred.

## Deterministic replay and integrity

New pilot manifest SHA:
`44d4de820bbad745cc14b2cad11f6adf34b412b58d33f7b9aefa886a39df444f`.
Original manifest/qualification hashes remain exactly those stated in the data report.
The unchanged pure R4-B qualifier was executed again on the old candidate and reproduced
the original `0a64c25c…` bytes/hash, independently of retaining the original file.
Both frozen candidates were each qualified in **two separate offline CLI processes**:

```bash
uv run --offline --no-sync python -m packages.data.requalification_cli qualify \
  --policy experiments/configs/r4b1_requalification.json \
  --candidate <pinned-private-manifest> --output <new-private-output>
```

Actual old-output directories are `datasets/private/r4b/r4b1-original-qualification-one`
and `...-two`; new outputs are `datasets/private/r4b/session-r4b1-20261117-v1/qualification-one`
and `.../qualification-two`. Each contains a `report/` publication. All four commands
exit 0 as diagnostic computations; all diagnose dataset BLOCKED. Hash indexes and every
indexed file were compared byte-for-byte; runtime timestamps were excluded.

| Indexed artifact | Original candidate report | New pilot report |
| --- | --- | --- |
| `requalification.json` | `5f8b3c654db26655a953ca4893292ecf21394f2176b18aba7ff79d0cc4f392ef` | `d98a64a0192dd342655fe1621a2f93fac2b7f5b7dfc0daf32cc50d71fbeece01` |
| `input-binding.json` | `15fec7a683702349e94249cf60ddf057eeba6c5f065786de30f7514a7dcfca35` | `42bf9ea67b5b7593fa5d1516b89f6dda9ff0622a7b132b35dffa95a77496e615` |
| `qualifier-source.json` | `8d9f1b79dcf7780c65a3630da5c2675d5c9675923cbdf812b0f2fa617d02c9af` | Same |
| `hashes.json` | `cc9feedf1ec448063fc03c2f617dbdbebed2bda0300b9a92d1e12446feef7b97` | `305ddd7cb01a977d9efa9d3da20723c69c641ac7b3e5784b13cf4384500b3a46` |

Ignored replay receipt: `results/r4b1-verification-20261117/offline-replay-verification.json`,
SHA `fd4256fb95c4f138442533b2c994b499737d311e7f842f730d0d1528ce3f1e64`.
It verifies both manifests, old qualification, indexed bytes, unchanged network counters
and the global retained-byte ceiling. Publication refuses existing outputs. No frozen
input or original failed evidence is overwritten. Final checkout uses new output paths
for the same deterministic replay rather than reacquisition.

## Accepted numerical and systems compatibility

Six synthetic CLI commands (R1 `run`, R2 `evaluate`, R4-A `historical_demo`, each twice)
were executed against unchanged fixtures/configurations. Exact expanded commands,
return codes, file inventories, runtime/source hashes and baseline comparisons are in
`results/r4b1-workingtree-20261117-qualification/verification.json`, SHA
`2cb81d50449275185c1405e1931669b45d455c7f4de7e9bb280801d16396fdfc`.

```bash
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --output <new-r1-output>
uv run --offline --no-sync python -m packages.research.cli evaluate \
  --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --output <new-r2-output>
uv run --offline --no-sync python -m packages.research.historical_demo \
  --dataset tests/fixtures/historical_snapshot/manifest.json \
  --security-id synthetic:001 --initial-cash 1000 --output <new-r4a-output>
```

All six exit 0. All three indexed pairs including `hashes.json` are byte-identical.
**238 invariant files** match accepted R4-B delivery byte-for-byte. Numerical
projections remain R1 (3 files)
`43c27422107eea69073743f8abdb810604ba60c36bb2da2d7a1efb32942411e2`,
R2 (96) `c4eb58ad9932b90879c24cc03fed1b6b75234c215a20942d3face831a2d6b88d`,
R4-A (3) `4b92e69392596f3bd11cecb98a173940e716e80d7fc5654254bed9acaa38506e`.

The stable 147-file Python fingerprint was
`64e2016a75bec45373c07af35e747a8ab2668f8b587d3c187b8dd6ca2c4ae8ba`.
Recorded full aggregates: R1 (7 indexed files)
`f2262ca798350b8bae73ddf5830f9ef20d7b1aa2410c8800f2728ff2fd7d4a53`,
R2 (294) `71fb332807312d7d0a037e6372c433631aa0ccb2c2e64b5c7f7030bec0e9e79f`,
R4-A (7) `0b972a814cd7b4dd387f1c38f56d997430f9957d25fbef3f0ac006cff4320196`.
Only source-dependent manifests/reports differ from accepted delivery (2/66/2 files).
Git revision/dirty state change after commits; these aggregates identify the recorded
working-tree verification. Final-checkout receipts record its new provenance while
verifying identical invariant numerical bytes. R3 fresh identities/recovery/replay pass
without silently migrating any existing experiment identity.

## Handoff and limitations

Source/transport/scope/publication behavior passes the tested engineering invariants,
including the expected negative qualification. This is not independent acceptance,
successful action admission, true point-in-time research or an empirical performance result.
Unresolved payment/currency/classification, authoritative decimal intent, action
completeness, permanent identity, daily aggregation/execution semantics, historical
availability/corrections, retention and publication rights remain explicit. The data
report identifies the smallest justified next evidence/admission step. No R4-C work begins.

Before release, staged files are scanned for private paths, binaries and key material;
only synthetic source/tests, plan metadata and sanitized documentation are published.
Remote main must still be an ancestor before a non-force push. Final local/origin/remote
SHA equality and the documentation commit's own SHA are recorded after publication in
the release handoff; a report cannot embed its own future Git object hash. Stop after R4-B.1.

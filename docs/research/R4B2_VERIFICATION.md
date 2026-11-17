# R4-B.2 verification — 2026-11-17

**Engineering: PASS; independent acceptance pending. Pilot data: BLOCKED.
R4-C readiness: BLOCKED.** Partial field evidence is not accepted historical data.
No authenticated provider request, historical strategy experiment, larger acquisition,
scope change, broker operation or deployment occurred.

## Git, scope and environment

Starting clean canonical main, origin/main and `git ls-remote origin refs/heads/main`
all matched `5064f7eaae19c0ce97b5f39e17fa84a4a09b7334`. SSH origin is
`git@github.com:ntua-el21026/ai-assisted-quant-research.git`. The owner required main
only; no branch, worktree, PR, tag, reset, rebase or force-push was used.

Implementation commit `2c94b1ed4a6568f420c113f2219991ab10a35b7e` changes only
`packages/data/action_reconciliation.py` and `tests/unit/test_action_reconciliation.py`.
The subsequent evidence/documentation commit adds the three R4B2 reports and updates
README, docs index, specification status, protocol status and architecture inventory.
Its own future object ID cannot be embedded in that commit; the final handoff records
the release SHA and local/origin/remote equality after publication.

There is one optional versioned currency-only helper, no new module or CLI. R1/R2
strategy/accounting/results, R3 workflows/ledger, strict normalization/v2 contracts,
fixtures, acquisition registration, lockfiles and historical reports are unchanged.
The [implementation](R4B2_IMPLEMENTATION.md) describes the interface and caller/source
interpretation boundary. [Qualification](R4B2_DATA_QUALIFICATION.md) explains every
applicable event, unresolved field and proposed owner option.

The existing environment was retained: Python 3.14.7, SQLite 3.53.1, Pydantic 2.13.3,
Pytest 9.0.3, Ruff 0.15.12, mypy 1.20.2, Temporal SDK 1.27.0. No dependency installation,
environment replacement, provider credentials or account changes were required.

## Executed checks

All settled commands below exited **0**. Logs are ignored under
`results/r4b2-verification-20261117/`.

| Command | Observed outcome |
| --- | --- |
| `uv run --offline --no-sync pytest tests/unit/test_action_reconciliation.py -q --tb=short` | **58 passed**, 0.09 s; 26 new synthetic cases |
| `uv run --offline --no-sync pytest -q -rs` | **1,521 passed, 9 skipped, 0 failed/errors, 3 warnings**, 44.51 s; `pytest.log` |
| Focused command below | **318 passed, 0 skipped, 3 warnings**, 15.29 s; includes actual local Temporal/replay/recovery; `focused.log` |
| `uv run --offline --no-sync ruff check .` | PASS repository-wide; `ruff.log` |
| `uv run --offline --no-sync ruff format --check packages/data/action_reconciliation.py tests/unit/test_action_reconciliation.py` | PASS for the two changed Python files |
| Established mypy command below | PASS, 59 source files; `mypy.log`; not repository-wide typing qualification |
| `uv lock --check --offline` | PASS, 27 lock entries |
| `uv sync --locked --group dev --offline --check` | PASS, 25 installed packages, would make no changes |
| `python3 scripts/check_markdown_links.py` | PASS after staging: 104 Markdown files, 214 local links, zero failures/unchecked fragments |
| `git diff --check` / staged privacy and file allowlist checks | PASS before commits; no private evidence, credentials or binaries staged |
| Protected-path diff against starting SHA | PASS; R1/R2/R3, strict normalizer/v2 models, fixtures, dependency and frontend paths unchanged |

Focused command:

```bash
uv run --offline --no-sync pytest tests/unit/test_action_reconciliation.py \
  tests/unit/test_action_scope.py tests/unit/test_requalification.py \
  tests/unit/test_requalification_cli.py tests/unit/test_historical_normalization.py \
  tests/unit/test_corporate_action_accounting.py tests/unit/test_historical_snapshots.py \
  tests/temporal tests/integration/test_research_reliability.py -q --tb=short
```

Established typing scope:

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

Nine pre-existing external-service gates remain skipped: Alpaca account read/write (2),
managed database (2), news (1), OpenAI (3), Telegram (1). Credentials were not loaded.
Three warnings are the existing legacy Temporal/Pydantic converter deprecations.
Temporal uses the previously verified cached SDK test-server executable, not a new
download or cloud service. Frontend code/locks were untouched; frontend checks were
not rerun in this checkpoint.

TDD first produced **26 failures/32 passes**, exit 1, for absent new interfaces, then
58 passes. Initial Ruff found four added overlong lines; formatting fixed them and
repository-wide lint passed. The first private operator attempt correctly refused the
fourth proposed SPY resolution because payment exceeded policy coverage; no candidate
was changed or partial resolution published. It was restricted to three events without
weakening the helper. A diagnostic hash verifier initially misread the existing index
envelope; its corrected verifier checks `sha256`, every byte and exact inventories.
QQQ evidence serialization retained its interrupted v1; v2 recovered from already
captured bytes with zero additional GETs. No test or acceptance tolerance was weakened.

## Network, privacy and primary-source evidence

**New authenticated provider calls: 0; received provider bytes: 0.** No credential file
was inspected, sourced, printed or changed. Existing aggregate authority stays at
5 attempts / 117,404 received bytes, sequence 63, no in-flight request; head
`d192472a8a73d6c60263891d3f9ddb0c51d67204053a9df75f4d987fd65e9bb4`.
No IEX/SIP reacquisition, account/broker endpoint, paid service or support message ran.

New native public-source retrievals: **11 HTTPS GETs**, all HTTP 200, **6,632,413 native
body bytes**: seven official Alpaca documentation files (3,756,961), three QQQ SEC
filings (1,838,394), one SPY 2025 SEC prospectus (1,037,058). Search/rendered-document
connector operations are separate; their internal requests/bytes are not observable.
Native HTTP bytes, transformed extracted text and cached rendered documents are labeled
separately. No transformed text is described as a native HTML hash. All downloaded
materials and field-level audits remain private with guarded storage and hash indexes.

| Private source/package | SHA-256 |
| --- | --- |
| `r4b2-api-semantics-20261117-v1/evidence-index.json` | `a2822f110aab08fe3c34e8fb4dc885b7a1f006e7a79a4cb7c7c9d444b8def90d` |
| Native official OpenAPI, 184,493 bytes | `9c2a7a50aa0585ede66cb963ed8bdc73d9d1dd69ff1e1fd06a6ee027651a96a3` |
| `r4b2-spy-audit-20261117-v1/evidence-index.json` | `3c5bf3cf4eaddcb04d29470ae2a8ddfff82b8740b64263557129d1a1e67a84ae` |
| Reused SPY January 2024 policy, 1,154,039 bytes | `e6b7acb1c3805621e83689f83e236c954f940a47a1279cc280567d971700122f` |
| `r4b2-spy-2025-policy-20261117-v1/evidence-index.json` | `83c00e854f95a6d6f0abf04b6b50c405313f04bb5b30d4e62f53cfcbeece5dbc` |
| Native SPY January 2025 prospectus, 1,037,058 bytes | `ffe2e2129e207193305705e7ec4bf4df2976354edf4d26652b8b4c710494403b` |
| `qqq-period-audit-r4b2-20261117-v2/evidence-index.json` | `6de0f0cc66d50fea0dff21585374714205ef0624d49d63892ec55750bdb4b7e5` |
| Native QQQ January 2024 filing, 895,506 bytes | `55f9e2ee7a1afecd8288eacb9923c62dafe9c2efa748c547cdcb4c46f39dba36` |
| Native QQQ May 2024 supplement, 19,996 bytes | `5037e5df2d2a750a97dec8be3c3ef037783da0f4eaec732821f8522f98cd8136` |
| Native QQQ January 2025 filing, 922,892 bytes | `abf8ee4dd7307da7848f466d5578596328a3102164ca702c6595a792f80b9ace` |

All package paths are below `datasets/private/r4b/`; their receipts record exact
retrieval UTC, source URLs, native hashes/sizes and interpretation limits. Existing
SPDR/Invesco workbook hashes remain in [R4-B.1](R4B1_DATA_QUALIFICATION.md).
Nothing in these captures confirms missing provider currency or historical availability.

## Independent offline qualification and immutability

Both separate strict CLI processes exited 0 as **diagnostic computations**, reporting
technical action normalization FAIL and dataset BLOCKED:

```bash
uv run --offline --no-sync python -m packages.data.requalification_cli qualify \
  --policy experiments/configs/r4b1_requalification.json \
  --candidate datasets/private/r4b/session-r4b1-20261117-v1/frozen/evidence/manifest.json \
  --output datasets/private/r4b/r4b2-strict-pilot-one
```

The second command substitutes only `r4b2-strict-pilot-two`. All three indexed files,
hash index bytes and exact inventories match. Runtime metadata is excluded.

The ignored, retained finite operator uses the tested helper and frozen context:

```bash
PYTHONPATH=. uv run --offline --no-sync python \
  results/r4b2-verification-20261117/freeze_resolution.py \
  --context datasets/private/r4b/r4b2-partial-resolution-20261117-v1/report/context.json \
  --output datasets/private/r4b/r4b2-partial-replay-one
PYTHONPATH=. uv run --offline --no-sync python \
  results/r4b2-verification-20261117/verify_offline_replay.py
```

The other independent replay substitutes `r4b2-partial-replay-two`. All 11 indexed
files and index bytes match. Original provider fields are unchanged; the derived view
contains three resolved/13 unresolved currencies and every applicable independent row.

| Deterministic artifact | SHA-256, identical in both processes |
| --- | --- |
| Frozen pilot manifest | `44d4de820bbad745cc14b2cad11f6adf34b412b58d33f7b9aefa886a39df444f` |
| Strict `requalification.json` | `d98a64a0192dd342655fe1621a2f93fac2b7f5b7dfc0daf32cc50d71fbeece01` |
| Strict `input-binding.json` | `42bf9ea67b5b7593fa5d1516b89f6dda9ff0622a7b132b35dffa95a77496e615` |
| `qualifier-source.json` | `26bcfba400975d108d9d6bdd9742f95d584221ca3e92519b65614f61108755c8` |
| Strict `hashes.json` | `38ea1233441e4e2e90af56b204f6ec84a681b8fc290e9450964b7397d9b69a10` |
| Partial audit `summary.json` | `8238ac22d8ac5ebeec1e47ae65e32500e6a32137a10083c804eb8ddd44293231` |
| Partial audit `hashes.json` | `62cbf78090b770a7a9f26e0ba912d623a3bc14ad3bb1b5c8f9ac6c35dfca8b9f` |

The original R4-B pure qualifier was independently executed again and reproduced
`0a64c25cc9e9b179715da631ceb381e2beac01ef4f62b2f2e1fd9440f93b3621`.
Both old/pilot manifests and old issuer evidence load under their original pins.
The offline verification receipt is
`results/r4b2-verification-20261117/offline-replay-verification.json`, SHA
`08f621dd572a452f19186ec09a46fa68122fdf47f33894528e640fc5526950dd`.
Its storage measurement was 13,236,231 bytes before the later SPY 2025 capture; storage
remains guarded by the aggregate 1 GiB limit. No frozen input was overwritten.

## Numerical and systems compatibility

Six independent synthetic CLI commands executed: R1 `run`, R2 `evaluate` and R4-A
`historical_demo`, each twice, exit 0. Actual complete argument vectors, output paths,
return codes, log/source hashes and exact file comparisons are retained in
`results/r4b2-workingtree-20261117-qualification/commands.json` and `verification.json`.
Verification receipt SHA:
`fbcb3f7b7b2259f3072cdd71c9fcc1607ced81da51a7ae2b0cdd85243e90af6f`.

```bash
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --output results/r4b2-workingtree-20261117-qualification/r1-a
uv run --offline --no-sync python -m packages.research.cli evaluate \
  --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --output results/r4b2-workingtree-20261117-qualification/r2-a
uv run --offline --no-sync python -m packages.research.historical_demo \
  --dataset tests/fixtures/historical_snapshot/manifest.json \
  --security-id synthetic:001 --initial-cash 1000 \
  --output results/r4b2-workingtree-20261117-qualification/actions-a
```

Each second command substitutes `-b` for `-a`. All pair bytes including hash indexes
match. **238 invariant files** match both R4-B and R4-B.1 accepted reference receipts.
Numerical projections remain exactly R1 (3 files)
`43c27422107eea69073743f8abdb810604ba60c36bb2da2d7a1efb32942411e2`,
R2 (96) `c4eb58ad9932b90879c24cc03fed1b6b75234c215a20942d3face831a2d6b88d`,
R4-A (3) `4b92e69392596f3bd11cecb98a173940e716e80d7fc5654254bed9acaa38506e`.
Source-dependent manifests/reports are not falsely required to retain an older revision.
The 147-file Python fingerprint is
`0024fb53a8b6036c122a0b8eb3292c4205ddd837bbf58ea11b9933d90685cd1d`.
Final-checkout replays use fresh output paths and retain a separate release receipt.

Full/focused tests execute actual R3 local workflows, durable ledger, retries,
publication reconciliation, interruption/recovery and history replay. No existing
experiment identity is migrated. Public synthetic examples remain credential-free.

## Independent-review handoff

Review the three currency policy interpretations and their exact private receipts,
all 16 event comparisons, current schema/changelog findings, unchanged strict failures,
and [seven admission gate groups/owner options](R4B2_DATA_QUALIFICATION.md#admission-gates-and-owner-decision-matrix).
Integrity verification cannot establish policy interpretation, action completeness,
historical first availability, executable prices, unchanged vintages or publication rights.
No dataset acceptance or research-complete claim follows from engineering PASS.

Before release, only the named source/test and sanitized documentation are staged;
private inputs/receipts/workbooks/diagnostics remain ignored. The remote must remain at
the verified starting main before a normal push; the final handoff records observed
Git synchronization and a clean tree. R4-C remains blocked and requires separate
authorization after evidence and any proposed restricted study convention are reviewed.

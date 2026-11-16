# R3 local systems verification — 2026-11-16

R3 Tasks 9–10 are implemented and verified within the bounded local scope below.
**R3 awaits independent acceptance.** The owner reports that R2 passed independent
external engineering review at `9b3678bd5debed41f8238805d34fba7f606a18a3`.
No R4 work, historical-market conclusion or overall research-completion claim is made.
All market/news inputs in these demonstrations are the existing synthetic R1/R2 fixtures.

## Repository and source provenance

The starting checkout was clean `main`, equal to cached and fetched `origin/main` at
the accepted R2 SHA above. GitHub API metadata confirmed repository ID `1228937377`,
canonical name `ntua-el21026/ai-assisted-quant-research`, default branch `main` and
the canonical SSH origin `git@github.com:ntua-el21026/ai-assisted-quant-research.git`.
The existing repository visibility was unchanged. Only `main` was used; there are no
new branches, PRs, tags, deployments, schedules or Actions changes.

Before implementation, the root instructions, README, pyproject/lock context, complete
v0.7 specification, architecture, protocol, R2 handoff and approved R3 plan/Prompt 3
were inspected, together with affected runners, artifacts, SQLite and Temporal code/tests.

| Commit | Change |
| --- | --- |
| `27982eda801821391a5964b920f418b0b801f246` | Research-only SQLite experiment checkpoints and transaction/integrity tests |
| `9d0a64af685e0e9f186549f3275556554431a781` | Content-pinned requests, artifact verification, reconciliation and failure tests |
| `44715e7fb7c2f778c4b9a131170068b5697390b9` | Typed actual research activity/workflow, finite local CLI, SDK execution/replay/recovery tests |
| `af99d7311d6e4656f608b3a68f6f660ea2de27fd` | Regression-led review corrections: immutable runtime evidence and serialized first-use setup |

The numerical hashes and local scenarios in this report identify source **`af99d73`**.
The documentation commit follows it. Actual Git HEAD is part of existing R1/R2 identity,
so a later documentation commit changes run IDs/manifests even with identical numerical
files. The final handoff gives the final documentation SHA and synchronization outcome.
`results/r3-final-handoff.json` is the ignored post-commit publication receipt, containing
actual HEAD/origin/GitHub equality, clean status and final-HEAD reproducibility evidence.

## Architecture and interfaces

R3 adds an optional wrapper; ordinary `packages.research.cli run` and `evaluate` remain
independent of Temporal, SQLite orchestration and server availability. Existing research
runner, simulation, feature, metrics, AI and artifact implementations have no source diff
from accepted R2. New source files naturally change their provenance fingerprints.

| Interface/source | Responsibility |
| --- | --- |
| `reliability_models.ResearchWorkflowRequest/Result` | Frozen plain dataclasses, string paths and typed mode/result; suitable for SDK serialization without legacy Pydantic conversion |
| `reliability.prepare_workflow_request` | Validate/pin local configuration, dataset, resolved AI evidence, source, orchestration code, environment, mode and final flag before submission |
| `reliability.execute_research_experiment` | Acquire local ownership, execute the actual R1/R2 runner or reconcile a prior verified checkpoint; return only a verified COMMITTED result |
| `reliability.verify_research_run_state` | Read-only full artifact/ledger verification by canonical runner ID; never edits or reconstructs artifacts |
| `research_ledger.ResearchLedger` | Typed checkpoint/query protocol |
| `research_ledger.SQLiteResearchLedger` | Separate local SQLite schema, immutable bindings, short transactions, checked lifecycle/event/result consistency |
| `ResearchActivities.run` | Synchronous SDK activity named `run_research_experiment`; deterministic validation/conflict/corruption errors are nonretryable, operational failures retain bounded retries |
| `ResearchExperimentWorkflow.run` | Deterministic typed orchestration of that real activity; no filesystem, SQLite or provider I/O in workflow code |
| `apps.workers.app.research_local` | One finite local SDK server/worker execution, retained history and verified replay; explicit existing binary required |

Source additions are three research modules and the dedicated activity, workflow and local
entry point. Tests add the ledger suite, core failure suite, CLI suite, two SDK suites and
a small local test helper. The only changed existing executable module is the activity
package initializer: its five legacy registry exports load lazily with the same names and
objects, isolating research imports from broker/provider registries. Legacy worker queues,
activities, database schema/repositories, historical evidence and R1/R2 tests are preserved.
Active README, specification status, architecture, protocol and documentation index reflect
implemented R3 and pending independent acceptance; historical handoffs remain unchanged.

## Identity, lifecycle and transaction boundaries

The caller supplies an experiment key. A canonical request fingerprint binds exact raw
configuration/registration/base hashes, effective configuration, verified market manifest,
actual resolved AI file presence, all research source and worker-source fingerprints,
Git revision, installed dependency/Python versions, mode and explicit final-evaluation flag.
Physical state/input locations are not scientific identity. Resolved missing AI remains a
distinct input, as required by R2. Source/environment/input changes on retry fail explicitly.

The experiment key, request fingerprint, actual runner ID and final destination have
uniqueness constraints. A conflicting request cannot replace an earlier binding, and an
alias key for the same request is rejected. Idempotence is scoped to one local state
directory/database; independent state directories are separate comparison namespaces.

The ledger uses `research_experiments`, `research_events` and `research_results` tables,
schema version 1, foreign keys, `synchronous=FULL`, explicit `BEGIN IMMEDIATE` mutations
and short read transactions. Each operation opens/closes its own connection. No SQL
transaction spans research computation or a filesystem rename. Default SQLite rollback
journaling is retained; no managed database is imported or contacted.

Lifecycle: **REGISTERED → RUNNING → PREPARED → PUBLISHED → COMMITTED**. RUNNING can start
another retained attempt. Permanent precommit errors enter FAILED. Each transition and
its progress event commit together. COMMITTED, the single result row and its unique
completion event commit in one SQL transaction. Injected completion-event failure proves
that all three effects roll back together. Audit sequences/hash chains are replay-checked
against the row and result; schema, SQLite integrity and foreign keys are checked.
These hashes detect accidental inconsistency, not coordinated hostile rewriting.

COMMITTED records immutable evidence of a past commit. Every result return also verifies
current artifacts. Later corruption raises the original corruption error without rewriting
that history or silently recreating a missing result. Thus a state column alone is not a
current-integrity certificate; callers use the verifier or execute/reconcile API.

Two POSIX kernel advisory locks have distinct scopes. A sibling initialization lock
covers marker writing and first database creation; active contention is retryable. An
experiment lock serializes computation/publication for that key. Persistent lock filenames
are not ownership evidence; the kernel releases ownership on close or process exit.
An already initialized workspace with a lost database, or an empty replacement database
contradicting retained attempts, fails closed. A bootstrap crash leaving a marker without
a database also fails closed; initialization evidence is not erased to guess a repair.

## Filesystem publication and deterministic reconciliation

The existing runner first publishes its unchanged artifact format into
`attempts/<key-sha256>/<attempt-number>/artifacts`. PREPARED then stores the actual run ID,
complete deterministic filename→SHA map, deterministic aggregate, safe stage/final paths
and a **separate SHA of the original `runtime.json` bytes**. Runtime remains excluded from
cross-run reproducible research hashes; it is immutable within its own attempt.

Only after PREPARED commits does R3 rename that directory to `runs/<run_id>`, fsync the
affected directories, verify it, and record PUBLISHED/COMMITTED in separate SQL commits.
**SQLite and the filesystem are not one atomic transaction.**

| Observed state | Action |
| --- | --- |
| REGISTERED/RUNNING without a durable PREPARED anchor | Retain old attempt evidence; compute in a new numbered attempt |
| PREPARED, only exact matching private artifacts | Verify, rename, verify final and advance SQL |
| PREPARED, only exact matching final artifacts | Reconcile an interrupted rename-to-SQL boundary without recomputation |
| PUBLISHED, exact matching final artifacts | Commit the one result/completion transaction |
| COMMITTED, exact matching final artifacts | Return the same verified typed result; no new attempt/checkpoint/completion |
| Stage and final both present, missing anchored bytes, bad hashes/runtime, extra/unsafe entries, lost/reset ledger or contradictory SQL/event state | Fail closed; preserve artifacts and original evidence |

Verification checks canonical JSON, full recursive file/directory inventory, regular safe
paths, every deterministic SHA, manifest/index agreement, aggregate, runtime-byte digest,
request binding and ledger/event/result consistency. A matching directory name or index
alone is insufficient. Private unanchored computation can repeat; one committed result,
publication checkpoint and completion event are the exactly-once observable effects.
Attempt counts can legitimately increase. Ordinary R1/R2 writer exceptions retain their
existing temporary-stage cleanup behavior; R3 retains the attempt directory/progress.
Abruptly interrupted private stages remain evidence and are not blindly adopted/deleted.

## Executed failure matrix

`test_research_reliability.py` executes actual offline research, compared with a separate
ordinary runner invocation. It does not replace the pipeline with successful mocks.

| Fault/invariant | Observed outcome |
| --- | --- |
| `before_register`, `after_register`, `before_execution` | Retry reaches the same verified result, one binding/completion |
| `after_execution`, `before_prepare` | Complete but unanchored private attempt retained; retry uses a new attempt |
| `after_prepare`, `before_publish` | Matching anchored stage publishes once |
| `after_publish_rename`, `before_published` | Matching final output is recognized; SQL catches up without new computation |
| `after_published`, `before_commit` | Verified published output commits once |
| `after_commit` / lost activity completion | Retry returns the prior committed result without repeating effects |
| OSError during the actual artifact writer's equity-file write | Private retry succeeds; attempts 2, committed results 1 |
| Real child `os._exit(73)` immediately after final rename | Persisted PREPARED and final artifacts; process ownership releases; resume reaches COMMITTED |
| Changed/missing/extra/symlinked/index-corrupt committed artifacts | Corruption error; changed evidence and historical committed ledger retained |
| Changed/missing prepared stage or simultaneous stage/final | FAILED, no recomputation/commit and retained evidence |
| Deleted or valid-empty replacement database | Explicit state-corruption error without recreating history |
| Altered SQLite schema, row, event, result or replaced file | Integrity/event/result validation fails closed |
| Runtime field loss or otherwise valid elapsed-time mutation after PREPARED/COMMITTED | Runtime digest mismatch; no new publication/success, no rewritten committed history |
| Concurrent first use, same and distinct experiments | Retryable initialization contention, then correct completion; no false corruption |
| Overlapping same-key attempt after initialization | Retryable ownership contention; one actual computation/result/completion |
| Same key/different request or duplicate input alias | Explicit nonretryable conflict; original binding preserved |

The SDK tests execute real local workflows for both `run` and `evaluate`, typed results,
duplicate workflow-ID refusal and distinct workflow invocations reusing the same experiment.
They cover transient retry, exhausted three-attempt retry without success, corruption,
lost completion after COMMIT, and worker replacement. Replay schedules no activity side
effects and leaves the ledger and artifact bytes unchanged.

For worker replacement, Worker A reaches a controlled `before_execution` barrier, observes
SDK shutdown and raises a retryable error. A distinct Worker B completes the same workflow
history. Tests require A/B callbacks exactly once each, the recorded ActivityTaskStarted
identity `research-worker-b`, retry attempt ≥2, exact independent-reference hashes and
successful no-effect replay. This is **cooperative worker shutdown with pending retry**.
It does not prove abrupt Temporal worker-process death while an activity is running.

The qualified workers/local CLI set `max_cached_workflows=0`, forcing normal-queue history
replay. Earlier default sticky-cache handoff tests timed out: inspection showed B had
committed successfully, while workflow completion polling/replay stalled. Initial STARTED
activity-state inference was insufficient and was corrected using the ledger evidence.
No timeout/assertion was weakened and no test was skipped. Default cached handoff remains
unqualified. Eight development logs retain this negative evidence under
`results/r3-temporal-development-evidence`; index SHA:
`5671bdaf5c856190d48d80cf943340fe34b6981b3f5d42baa786f6295f994563`.

## Reference, recovered and corruption demonstrations

At source `af99d73`, the existing 32-case R2 registration was executed twice independently,
through uninterrupted R3, after a real post-rename child exit, and through the local SDK
CLI twice. All successful paths matched **294 indexed files plus `hashes.json`** byte for
byte, excluding `runtime.json` from cross-run parity. Every indexed SHA and recursive
inventory was independently checked.

| Quantity | Observed value |
| --- | --- |
| Canonical R2 run ID | `b91591eecbe2328ea32147cfaac793865373c04ff0c369aff21c8347f0e9c45b` |
| R3 request SHA | `a26bafe83b25910fea362efe8e2c46eccb894fef2fe5620de3fbc31131e34d30` |
| R2 deterministic aggregate | `4e65f3deca50a319c8d96152e98517bffb91b8a0bf6804f98207e1f3b8b506f6` |
| `hashes.json` SHA | `c6e4c2d75d2fddf4f027f28ebb8092de743a8b42445a8ac1706044cb65831445` |
| R1 compatibility run ID | `069e850a9cb000c61719cd6d83d4cdb848b607290d32831fb3e7514dde4ffeb5` |
| R1 deterministic aggregate, two runs | `75a729bc3b3ddc3ebad275e668880aad8496e87dbd74a7d01451ca1efb339271` |
| Final recovered state | COMMITTED; child exit 73, interrupted state PREPARED |
| Semantic counts, clean/recovered/repeated SDK | experiments 1, attempts 1, prepared 1, published 1, committed results 1, completion events 1 |

Clean/recovered canonical request/result bindings, lifecycle progression and effect counts
match. Independent attempts have different runtime bytes and checkpoint runtime digests:
uninterrupted `7363179974a545fcf1e5b6c041d91c9968d3ae21f51cdad98351eda42ad96624`;
recovered `b8b7f8b2c14da4cd8f87666c0ab6b772dad2e40daa3dcada568bb1f75a95555b`.
Their prepared-event/chain hashes therefore need not match across independent attempts.
The recovered attempt's own runtime bytes/digest remain unchanged across restart/reuse.

A third completed run had a case equity file deliberately changed. Re-execution raised
`artifact_hash_mismatch:cases/092989462e9df97ce5999062d240f7c10a500ddb0eb077521f95dcc494507bcc/equity.csv`.
The corrupted bytes remained untouched, SHA
`d906bd1526e48b1953230e4a39413a74bd4a5ec563636107a2b59c55107d8ffd`;
the immutable historical ledger remained COMMITTED and current verification failed.
No replacement or new completion was created.

All **96 R2 case metrics/trades/equity files** and **three R1 accounting/trades/equity files**
were byte-identical to the retained accepted-baseline evidence. R1 still has one closed QQQ
share, net P&L **-19.5168864 USD**, fees **.0328864 USD**, final equity **9980.4831136 USD**.
R1/R2 source, configuration, fixtures, numerical behavior and artifact schemas are preserved.

Two actual retained SDK histories, 8,186 bytes each, replayed successfully with one ledger
completion and one result across both CLI invocations. Their SHA-256 values are
`87e3ccea15665940a2f1a0baca7ad0d5704ac7674d3e072e7edc9350822df76b` and
`7a34641372d41d9b449f4693e569bdc1644b88bad80ba9153b4f252149279a26`.
Histories include nondeterministic SDK IDs/timestamps and are evidence, not reproducible
research artifacts. Logical evidence paths are `results/r3-qualified/verification.json`,
`sdk-verification.json` and `results/r3-qualified-sdk/histories/`.
The verification JSON SHA is
`e0cd3c917a1109ead4b795bce94cb01e516216f65b4b57db12a8168ea0e0590a`;
the executed local orchestration helper SHA is
`806c42b2902acb49b0347794cd69c248051e9d59a40c81873382fa30e99a4575`.
Earlier pre-correction candidate runs remain separate evidence under `results/r3-evidence`.

## Exact commands and outcomes

Environment: retained `.venv`, CPython 3.14.7, uv 0.12.9, Pytest 9.0.3, Temporal SDK
1.27.0, SQLite 3.53.1, Ruff 0.15.12, mypy 1.20.2. SQLite's actual version is recorded
again in the final receipt. No package installation/upgrade or system environment change
was performed. Lock checks resolve 27 entries and verify 25 installed packages.

The already cached local test-server executable was passed explicitly, without download:
84,478,216 bytes, SHA
`19defb9f7318c7cf249518b3642a735efb79876c2b6918afe312336476b796a5`.
The new SDK tests fail qualification if no existing executable is available; they do not
silently download or skip. Local loopback SDK transport is required; no provider, broker,
cloud namespace or external database is used.

| Exact command | Observed outcome |
| --- | --- |
| `uv run --offline --no-sync pytest tests/unit/test_research_ledger.py -q` | Initial RED 29 missing-interface failures; expanded to final 33 passing cases |
| `uv run --offline --no-sync pytest tests/integration/test_research_reliability.py -q` | Initial RED 20; intermediate dependency-spelling/error-masking failures corrected; final 33 passing cases |
| `uv run --offline --no-sync pytest tests/integration/test_research_local_cli.py -q` | RED 3 missing-entrypoint failures → GREEN 3 |
| `uv run --offline --no-sync pytest tests/temporal/test_research_workflow_local.py tests/temporal/test_research_recovery.py -q` | Initial RED 6 missing-workflow failures; expanded to 9 passing new SDK cases |
| `uv run --offline --no-sync pytest tests/temporal -q` | 21 passed, including 12 preserved legacy cases; 3 existing warnings |
| `uv run --offline --no-sync pytest tests/integration/test_research_local_cli.py tests/temporal -q` | 24 passed, 3 existing warnings, 6.01 s after local cache alignment |
| `uv run --offline --no-sync pytest tests/unit/test_research_*.py tests/integration/test_research_cli.py tests/integration/test_research_experiments.py tests/integration/test_research_reliability.py tests/integration/test_research_local_cli.py -q` | Pre-review 235 passed, including the complete 174-case R1/R2 research regression set |
| `uv run --offline --no-sync pytest tests/integration/test_research_reliability.py -k 'runtime_bytes or first_use_contention' -q` | Review RED 6 failures, then GREEN 6 |
| `uv run --offline --no-sync pytest tests/integration/test_research_reliability.py tests/unit/test_research_ledger.py -q` | Final correction wave **66 passed**, 5.20 s |
| `uv run --offline --no-sync pytest -q -rs` | **919 passed, 9 skipped, 0 failed/errors**, 32.43 s; 3 existing warnings |
| `uv run --offline --no-sync ruff check .` | PASS, whole repository |
| `uv run --offline --no-sync mypy packages/research packages/backtesting packages/data/snapshots.py packages/data/quality.py packages/risk packages/strategy/signals.py packages/ai/__init__.py apps/workers/app/activities/research.py apps/workers/app/activities/__init__.py apps/workers/app/workflows/research_experiment.py apps/workers/app/research_local.py scripts/benchmark_research_pipeline.py` | PASS, 37 source files |
| `uv lock --check --offline` | PASS, unchanged lock |
| `uv sync --locked --group dev --offline --check` | PASS, would make no changes |
| `uv run --offline --no-sync npm test` | PASS, frontend-only legacy-preview checks; no deployment |
| `python3 scripts/check_markdown_links.py` | PASS, 88 Markdown files/120 local links, no failures/unchecked fragments |
| `git diff --check` | PASS |

The nine skips remain existing explicit gates: Alpaca write/read-only (2), managed DB (2),
news (1), OpenAI (3) and Telegram (1). They were not enabled. The three warnings are
existing Temporal/Pydantic legacy converter deprecations. All 78 new R3 tests execute.
SQLite legacy affected tests passed 43 cases with one existing managed-DB skip before
the additional R3 review cases. No established test was weakened, removed or disabled.
Failed intermediate probes, intentional RED tests and cached SDK timeouts remain recorded;
they are not represented as passing checks.

The standalone actual SDK command was executed twice with the same state directory:

```bash
uv run --offline --no-sync python -m apps.workers.app.research_local \
  --experiment-id synthetic-r3-sdk --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --state results/r3-qualified-sdk \
  --test-server-binary /tmp/temporal-test-server-sdk-python-1.27.0
```

On another machine, supply an independently available executable; the CLI has no
downloader. Use new output/state locations when changing code/environment. Repeat an
unchanged request/state to verify reuse. The direct reference/crash/corruption evidence
ran via `uv run --offline --no-sync python -m results.r3-qualified.verify`; its ignored
helper is supplementary local evidence. The committed 33-case integration suite and
nine SDK cases reproduce the critical invariants without requiring that ignored helper.
Reference calls are `evaluate_research(config, dataset, new_output)` twice and
`run_research(baseline, dataset, new_output)` twice, using the unchanged fixture paths.

Additional standard-library assertions verified Python/Node metadata against their lock
root entries. Final diff checks protect historical specifications/evidence/deployment,
legacy SQLite/Temporal tests, R1/R2 numerical sources, data/configuration and lockfiles.
Generated SQLite files, histories, outputs and raw logs remain ignored. No binary,
credential, active deployment instruction or enabled workflow was introduced.

## Internal review, rulings and limitations

One fresh internal review examined immutable `9b3678b..44715e7`, executed 59 focused
ledger/core cases and reproduced two Important findings. Both were fixed in one TDD wave:
runtime mutations after PREPARED/COMMITTED first failed four regressions; initial same/
distinct-experiment contention first failed two. A separate runtime-digest contract case
was added to ledger validation. The final full suite passes. No internal-review minors
are deferred, no second review was used, and this is not independent external acceptance.

Implementation rulings and their practical costs:

- The approved plan and detailed R3 request supply implementation authority; routine
  architecture choices are documented for external review instead of requiring renewed
  approval. Their suitability remains an external checkpoint decision.
- A separate research SQLite backend preserves the broker schema and transaction-owning
  legacy repository contracts; the cost is a small additional local persistence surface.
- Kernel locks, short SQL commits and verified PREPARED reconciliation provide once-only
  committed effects, with potentially repeated private computation. They do not provide
  a distributed lease or an atomic SQL/filesystem transaction.
- Input/source/environment pinning rejects silent upgrades and changed evidence;
  resumption requires the original qualified versions or a new experiment identity.
- Lazy activity exports preserve legacy API names while isolating the research path;
  legacy operational registries remain separately qualified historical functionality.
- COMMITTED history is immutable; consumers must verify current artifacts rather than
  treating a past successful state column as perpetual integrity assurance.
- Runtime is nondeterministic across independent attempts but immutable within one
  checkpoint. Its separate integrity digest does not alter R1/R2 reproducibility hashes.
- Initial setup is serialized; an interrupted bootstrap or genuinely lost ledger fails
  closed rather than guessing reconstruction. Such evidence needs explicit inspection.
- Cache-zero local SDK worker replacement is qualified; default sticky-cache handoff
  remains negative evidence. Cooperative worker replacement and real post-rename process
  death are distinct demonstrated scenarios, not proof of every in-flight worker crash.
- R3 external acceptance, R4 empirical/release conclusions and profitability remain
  unclaimed. Cloud/providers/brokers/managed DBs/deployment/schedules remain outside scope.
- Existing environment qualification uses executed tests/locked checks; fresh installation,
  dependency upgrades, other Python/platforms and independent post-fix review were not run.

Further unverified properties include abrupt Temporal worker death mid-activity, Temporal
server restart, host crash, power loss, distributed/network filesystems, distributed fencing
and coordinated malicious edits. File fsync/rename and SQLite guarantees do not establish
those properties from the tests here. Locks are cooperative POSIX single-host mechanisms.
Staging/final paths must share a filesystem; cross-mount rename errors fail without
a copy-and-replace fallback.
Contention may exhaust bounded retries; resubmitting the unchanged request is safe.
Large-scale throughput/retention policy and managed services were not added. Synthetic
evidence does not establish real historical validity or AI benefit. R1/R2 trading/data/
statistical assumptions and limitations remain unchanged.

The independent-review handoff should assess the lifecycle/identity boundary, runtime and
deterministic artifact anchoring, initial contention, non-atomic reconciliation, effect
cardinalities, SDK cache qualification and the exact scope of crash evidence. Stop after
R3; begin R4 only under a separate authorization.

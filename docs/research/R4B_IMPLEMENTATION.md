# R4-B historical acquisition and qualification

**Acceptance update:** the owner independently accepted R4-B engineering at
`a6d3a0960e5924ab2f2969d02a1620e87b007101`. Its dataset remained blocked. The following
records that checkpoint; [R4-B.1](R4B1_IMPLEMENTATION.md) adds separately authorized
corrective scope/budget handling and pilot evidence without changing this history.

R4-B adds an optional, finite read-only acquisition boundary and deterministic offline
candidate qualification. It does not execute a strategy, register new study periods,
or enable R4-C. The accepted starting point is
`0dd0875c9f4a1ff806a107badcd693922d9f7e29`; R4-A acceptance is for synthetic engineering.
The [predeclared plan](../superpowers/plans/2026-11-17-r4b-historical-acquisition.md)
and [JSON request plan](../../experiments/configs/r4b_acquisition.json) precede observations.

## Interfaces and file inventory

| Module | Interface and responsibility |
| --- | --- |
| `packages/data/acquisition_plan.py` | `load_acquisition_plan`, frozen plan/stage/budget types; pinned calendar; bounded nonexecuting credential-file parser |
| `packages/data/acquisition_budget.py` | `HistoricalSessionBudget`, `BudgetedHistoricalTransport`; one durable sequential attempt/body/time allowance |
| `packages/data/alpaca_historical.py` | Backward-compatible explicit IEX/SIP selection and action `data_quality`; bounded concrete reader; unchanged exact bar/action normalizers |
| `packages/data/historical_models.py` | Permit explicit IEX in existing v2 receipt feed validation; original SIP/v1 meanings preserved |
| `packages/data/historical_normalization.py` | Bind actual selected feed and full query/hash chain into compatible v2 receipts |
| `packages/data/research_calendar.py` | Hashed official-schedule calendar with explicit closure/early-close tables and New York DST |
| `packages/data/private_storage.py` | Fresh ignored private workspace, exclusive writes, fsync, retained-byte cap and private atomic publisher |
| `packages/data/historical_candidates.py` | Frozen `historical-candidate/v1` envelope, complete/partial query truth, exact inventory/hash loader |
| `packages/data/candidate_publication.py` | Validate candidate/file agreement and publish a strict nested evidence subtree |
| `packages/data/historical_qualification.py` | Pure coverage/action/provenance/rights/availability diagnostics; `historical-candidate-quality/v1` |
| `packages/data/action_reconciliation.py` | Exact independent event matching, sanitized findings/fingerprints, explicit unknown fields |
| `packages/data/acquisition_session.py` | Preflight → pilot → conditional candidate; private capture/normalization/freeze; offline qualification |
| `packages/data/acquisition_cli.py` | `plan`, opt-in `acquire`, offline `qualify`; sanitized output and POSIX deadline |

New tests are the corresponding nine `tests/unit/test_*.py` modules for budget, plan,
session, reconciliation, publication, candidates, qualification, private storage and
calendar. Existing acquisition/normalization tests are extended; no test or tolerance is
removed. Public configuration consists of the request plan and
`experiments/configs/r4b_calendar_2020_2025.json`. Active README/index/specification/protocol/
architecture and dataset instructions describe the actual boundary. R4-A reports receive
dated acceptance annotations; their original results remain evidence.

## Explicit execution and resource control

Offline plan check (no credential discovery):

```bash
uv run --offline --no-sync python -m packages.data.acquisition_cli plan \
  --plan experiments/configs/r4b_acquisition.json
```

The actual authorized acquisition command was:

```bash
uv run --offline --no-sync python -m packages.data.acquisition_cli acquire \
  --allow-network --plan experiments/configs/r4b_acquisition.json \
  --workspace /home/peppasmich/projects/ai-assisted-quant-research/datasets/private/r4b/session-20261117 \
  --credentials-file /home/peppasmich/.config/ai-quant-research/alpaca.env
```

This is an evidence command, not an instruction to acquire again. Existing workspaces
are refused. Interrupted attempts are not resumed or given a fresh allowance
automatically. Additional attempts require a manual checkpoint-wide remaining-budget
review. Limits are enforced per sequential session, not through a concurrent global
lease or cross-process quota service.

The registered plan permits Basic/paper-only **IEX only**, up to 100 authenticated
attempts including retries, 250 MiB received HTTP bodies across **all** statuses,
1 GiB retained private file contents, 900 seconds and 20-second socket timeouts.
Pacing is at least 0.35 seconds between starts. Each response is separately capped at
16 MiB. Retry count/backoff, page counts and wait budgets are finite. Reservation and
byte events are fsynced before continuation; journal failures permanently close the
session. Unknown-length bodies filling their allowance are conservatively rejected
without an extra probe byte. HTTP headers/TLS/OS buffers and filesystem metadata are
outside these content-byte counters. A POSIX process alarm covers otherwise blocking
DNS/transport work; it is not a power-loss or hostile-process guarantee.

The concrete transport allows GET only at the exact HTTPS Alpaca stock-bars and
corporate-actions endpoints. Ambient proxies and redirects are disabled. No broker,
order or account endpoint is imported or called. Credentials are read programmatically
only after explicit opt-in, through a bounded literal parser for two APCA assignments;
there is no shell execution or environment dump. File content and permissions are
unchanged. Errors expose closed codes; response bodies and opaque pagination tokens
remain private. Returned non-200 bodies are retained privately, not echoed. A stream
interrupted before return has durable byte/failure accounting, not a fabricated page.

## Query design and observed stop

SPY/QQQ are a deliberately small ETF universe for coverage/benchmark feasibility, not
a historical stock screen. The first daily-bar query covers completed sessions
2025-01-06 through 2025-01-10, including the January 9 exchange closure. The action
preflight uses inclusive **process dates** 2024-01-01 through 2024-03-31, all types and
`data_quality=all`. The documentation warns that already-processed incomplete events can
also occur with the default `complete` filter; neither filter proves completeness.

Only after preflight and both pilot components qualify may the full candidate run.
The pilot is 2024–2025; the conditional raw candidate is 2020–2025. Four narrow early-year
bar probes and split/adjustment/action diagnostics are registered, but none executed
after the real preflight stopped. These windows do not replace the research protocol.
The [qualification report](R4B_DATA_QUALIFICATION.md) records the negative outcome.

## Versioning, publication and reproducibility

`market-snapshot/v1` and `market-snapshot/v2` retain their accepted semantics. V2
admission still requires essential provenance, complete action inventory, honest
rights and valid time/identity/calendar evidence. R4-B cannot satisfy these by assertion.
The new **candidate envelope** explicitly permits partial queries and unverified or
contradictory evidence. It cannot be passed to either ordinary research runner or R3
as though it were an admitted snapshot. No existing experiment identity is migrated.

Successful raw observations pass through exact Decimal normalization and the v2
bar/receipt bridge. Adjusted observations remain diagnostic source pages, never
execution inputs. Acquired/received timestamps are actual UTC observations. Historical
availability is `observed`, not backdated to the event or historical close. Current
query tickers get explicitly uncertain logical `research:<ticker>` identities; they
are not invented permanent identifiers or point-in-time universe membership.

The envelope retains request parameters, feed/basis/timeframe, page hashes/status,
query times, calendar/source/dependency fingerprints, exclusions/failures and licensing
evidence classifications. The JSON loader verifies size/SHA, safe paths and exact
recursive file inventory. Raw JSON decimals survive conversion; no forward fill occurs.
The outer atomic publication has `hashes.json`/`runtime.json`; its nested `evidence/`
subtree contains only the exact candidate inventory and manifest. Publication uses the
existing staged/fsynced rename implementation. This is single-host filesystem evidence,
not a SQLite/filesystem joint transaction or an expansion of R3 guarantees.

Corrections require new evidence, manifest/hash and candidate identity. Existing
publications are never overwritten. Same-user manual file mutation is not prevented by
an immutable filesystem; subsequent hash verification fails closed. Private files use
0600 and directories 0700. Gitignore is verified before creation. No vendor observation,
issuer workbook or sensitive receipt is staged or committed.

Offline qualification example (new output path each time):

```bash
uv run --offline --no-sync python -m packages.data.acquisition_cli qualify \
  --candidate datasets/private/r4b/session-20261117/frozen/evidence/manifest.json \
  --output datasets/private/r4b/session-20261117/qualification-new
```

Historical outputs must remain in the same ignored private workspace. The pure report
contains coverage keys/counts, classifications and hashes, not economic observations,
dividend rates or opaque provider identifiers. This checkpoint nevertheless retains
even these actual qualification artifacts privately. Runtime timestamps/host metadata
remain outside the deterministic output index. Replaying a **frozen** candidate is
reproducible; reacquiring a provider query may observe later corrections and is not
promised to yield the same bytes or historical information set.

## Corporate actions and scientific restrictions

`reconcile_actions` compares hashed independent records by stable identity, kind and
ex-date. Split ratios use exact rational equivalence; dividends compare exact Decimal
amount, payable date and currency only where known. Duplicate provider identity,
same-date component ambiguity, contradictions, unsupported distributions and missing
fields produce explicit restrictions/failures. An incomplete independent inventory
never proves provider completeness. The report contains counts/codes/fingerprints;
historical announcement availability is always unestablished without separate evidence.

Accepted split/dividend accounting is unchanged: special distributions, unknown cash
in lieu, ambiguous share basis and unsupported reorganizations are not modeled by
inventing ordinary dividends. The actual special flag remains a failure. Category
counts alone do not indicate economic support: `cash_dividends` can contain an
unsupported special record even when unknown-category count is zero.

Venue-limited IEX data cannot establish consolidated next-open/high/low/volume execution
semantics. The calendar is an official regular-session schedule, not independent proof
of a provider's daily aggregation window. Historical provider corrections, permanent
identity, survivorship-free membership, complete 2016–2019 actions, raw execution,
total-return benchmark consistency and causal feature availability require further
evidence. Support #397685 is owner-reported scope authorization, not a public
redistribution grant or proof of SIP entitlement. See [qualification](R4B_DATA_QUALIFICATION.md)
for each blocker. No R4-C implementation, optimization or holdout performance inspection
is included.

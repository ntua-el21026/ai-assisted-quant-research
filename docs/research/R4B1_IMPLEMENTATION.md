# R4-B.1 corporate-action resolution and requalification

This corrective checkpoint follows independently accepted R4-B engineering at
`a6d3a0960e5924ab2f2969d02a1620e87b007101`. The failed R4-B dataset remains evidence;
its manifest and deterministic qualification are never overwritten. This work adds
explicit economic scope and aggregate acquisition limits. It does not execute R4-C,
change study periods/thresholds, or make historical performance claims.

## Root cause and action treatment

The R4-B action query filtered **process dates**, not effective/ex-dates. Its two cash
records have 2023 ex-dates, while the proposed pilot starts in 2024. The original
normalizer correctly rejected a provider special flag, but acquisition had no way to
establish whether that event was economically applicable to a fresh pilot portfolio.
The new path supplies that missing distinction without changing the strict normalizer.

Official 2023 Invesco evidence matches the flagged QQQ security, ex-date, record date
and exact amount. Its tax characterization is income/ordinary dividends, with zero
capital-gain/return-of-capital components. **Payable dates disagree** with the provider;
both fall after the start boundary. Tax character does not establish what Alpaca's
special flag means. Historical declaration availability and historical QQQ payout
currency remain unverified. The private source/field comparison and hashes are recorded
in [data qualification](R4B1_DATA_QUALIFICATION.md).

No special distribution is converted into an ordinary modeled dividend. No new special
cash accounting class is justified while payment/classification evidence conflicts.
Relevant special or ambiguous events remain rejected. Accepted exact Decimal dividend,
split, receivable, payment and benchmark accounting is unchanged.

A position held across a supported ex-date would earn quantity times the exact
per-share distribution as a receivable, followed by available cash at the established
payment boundary. The disputed payable date would change available cash for a held
position, so it cannot be chosen for convenience. A fresh zero-entitlement pilot earns
zero under either date. Dividend-adjusted prices are never added to cash credits;
simulation/analytical benchmarks continue to require their declared compatible bases.

## Economic scope contract

`ActionScopeContext` explicitly declares evaluation dates, feature-history start,
raw execution/feature basis, opening state and empty positions/orders/receivables with
independently specified starting cash. Defaults are unknown/unsafe. A valid cash event
before feature history is outside only under the complete fresh-flat/raw contract.
Its payment may occur afterward: there is zero eligibility because no prior portfolio
or inherited entitlement exists. Zero current shares alone is insufficient.

This exclusion does not apply to inherited receivables, carry-in positions/balances,
earlier warm-up, provider-adjusted inputs, old splits, symbol changes, mergers or
structural dependencies. In-period cash events remain applicable because later positions
could be eligible. Missing/contradictory dates, IDs, source pagination or records fail
closed. Future cash exclusions also require absence of retrospective adjustment
dependencies. These are data-qualification conditions, not new strategy parameters or
changes to the registered evaluation periods.

Every readable source row retains its category, source ID, page/record hashes, location,
event/process/payment dates, special/foreign/currency fields, scope, support and closed
reason. Malformed rows and nonfinite constants remain inventoried as failures rather
than disappearing with page parsing. Private serialization includes the full audit;
sanitized serialization contains only counts, codes and hashes.

`normalize_applicable_actions` binds the report to the exact original acquisition and
recomputes it before use. It builds an internal derived selection and invokes the
unchanged normalizer. Original provider pages/queries/timestamps and receipts remain
original evidence; derived selection is never issued as a provider receipt. A rejected
action normalization writes no fictional empty normalized action inventory.

## Interfaces and compatibility

| File/interface | Responsibility |
| --- | --- |
| `packages/data/action_scope.py` | `classify_action_scope`, `normalize_applicable_actions`, private/public scope reports |
| `packages/data/checkpoint_budget.py` | `CheckpointBudgetAuthority`, `BudgetReceiptReference`, aggregate storage checks and durable continuation |
| `packages/data/requalification.py` | Hash-pinned `RequalificationPolicy`/inputs, typed evaluator/gate and deterministic aggregate report |
| `packages/data/requalification_cli.py` | Offline `plan`/`qualify`, explicit finite `acquire`, private publication |
| `packages/data/acquisition_budget.py` | Optional initial counters; default-zero session behavior retained |
| `packages/data/acquisition_session.py` | Optional reused preflights, supplemental evidence, guarded budget/storage, scoped evaluation and strict pilot-stop hooks |
| `packages/data/private_storage.py` | Optional external quota check before every write/append/publication; authority-aware refusal of unguarded writes |
| `packages/data/acquisition_cli.py` | Reject legacy acquisition before credential loading after aggregate authority initialization; optional repository injection isolates tests |
| `packages/data/historical_candidates.py` | Additional closed callback-failure codes; existing candidate/v1 meaning retained |

The old default path is preserved when no aggregate authority exists. Once initialized,
legacy acquisition cannot reset the checkpoint allowance, and historical publication
requires its global storage guard. This deliberate local safety restriction is tested;
ordinary offline research, synthetic examples and pure quality computation remain
credential-free. The original partial-acquisition CLI test uses an explicit temporary
repository, retaining its assertions while avoiding dependence on local private state.

R1/R2 strategy, risk, simulator, metrics and fixture files are unchanged. R3 ledger,
activity/workflow/recovery and identity contracts are unchanged. `market-snapshot/v1`
and strict `market-snapshot/v2` admission are not weakened. A candidate envelope plus
requalification report is not a v2 snapshot or a new R3 experiment mode.

## Registered requests and aggregate resource control

The old plan is preserved. New [request plan](../../experiments/configs/r4b1_acquisition.json)
retains its six primary request groups and exact windows, with no unrelated diagnostics.
The [policy](../../experiments/configs/r4b1_requalification.json) binds it to the old
manifest/quality, prior budget, independent evidence and distinct pilot/candidate scope.
The original preflight pages are reused, not downloaded again. Their times and query
identity remain unchanged. New source/acquisition times are actual observations.

The checkpoint authority seeds **2 requests / 1,457 received bytes** from the pinned
closed old journal. Reservations and chunks append to a locked, hash-chained journal
with immutable anchors. An immutable base pointer prevents selecting a fresh authority
directory to reset usage. Missing/truncated/changed evidence or an unfinished attempt
blocks continuation for manual review; no unknown bytes are automatically refunded.
Limits remain 100 requests, 250 MiB across all response statuses and 1 GiB across **all**
private checkpoint file contents, including old/new evidence, logs, copies and staging.

One budget is permitted per authority context. Rate pacing, socket timeout, retry/page
limits and a 900-second POSIX process watchdog remain finite. Deadlines are per finite
authorized session; request/body/storage ceilings are aggregate across sessions. The
new CLI includes an initial pacing delay. Headers, TLS/kernel buffering, filesystem
metadata and hostile-writer guarantees are outside these content counters. Journal,
pointer and anchor publication are separate fsynced steps; interrupted boundaries fail
closed rather than being described as one atomic transaction.

Only explicit `acquire --allow-network --credentials-file ...` loads credentials, through
the accepted bounded literal parser. No values are printed or mutated. The fixed HTTPS
GET endpoints, redirect/proxy rejection, IEX selection, no broker endpoints and private
permissions remain enforced. Neither a successful HTTP response nor a manually asserted
complete action inventory grants readiness.

## Commands and output

Offline registration/evidence check:

```bash
uv run --offline --no-sync python -m packages.data.requalification_cli plan \
  --policy experiments/configs/r4b1_requalification.json
```

Acquisition is a separate explicit command. The executed command, resource use and
outcome are recorded in [verification](R4B1_VERIFICATION.md), not an instruction to
reacquire. New immutable workspaces are required; no automatic acquisition resume exists.

Offline replay:

```bash
uv run --offline --no-sync python -m packages.data.requalification_cli qualify \
  --policy experiments/configs/r4b1_requalification.json \
  --candidate <private-frozen-candidate-manifest> --output <new-private-output>
```

The report preserves original/full-query diagnostics alongside scoped results,
independent reconciliation status, source/policy/candidate hashes and actual failed
gates. Scope-blocked normalization defers reconciliation rather than pretending the
provider has no records. Runtime metadata is separate. Two independent qualifications
must match every indexed byte. This path does not create or admit v2 data; scientific
readiness remains blocked until the actual contract can be satisfied honestly.

All provider pages, issuer materials, extracted fields, sensitive receipts and generated
empirical diagnostics remain in ignored private storage. Public tests use invented
synthetic records. Existing public v1/v2 examples and offline tests remain available.

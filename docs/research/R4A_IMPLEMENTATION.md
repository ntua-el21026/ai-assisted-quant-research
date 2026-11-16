# R4-A historical infrastructure contract

R4-A is a **synthetic-only engineering foundation**. The owner accepted the R4-0
preflight and identified `60dd250c52254ab1f08f7042971967467f05b11f` as the reviewed
R1–R3 baseline. R4-A independent acceptance, historical acquisition, data-rights
clearance and empirical research remain pending. This phase changes no registered
research periods, strategy thresholds or accepted v1 numerical behavior.

## Interfaces and execution boundary

| Interface | Purpose |
| --- | --- |
| `data.alpaca_historical` | Explicit SIP daily-bar/action requests, injected GET transport, bounded pagination/retries and pure normalization |
| `data.historical_normalization.to_snapshot_bar` | Preserve exact source Decimal values in a v2 domain observation; reject adjusted execution |
| `to_acquisition_provenance` | Bind actual queries, page/query hashes and timestamps without inventing endpoint parameters |
| `data.historical_models.HistoricalSnapshotManifest` | Frozen `market-snapshot/v2` contract |
| `data.historical_snapshots.load_historical_snapshot` | Local integrity/quality/provenance validation, optional root-manifest pin |
| `HistoricalSnapshot.feature_view(cutoff, basis=...)` | Raw or split-as-of price history with causal observation/action/identity gates |
| `data.corporate_actions.validate_actions` | Supported split/USD-cash domain validation and deterministic action ordering |
| `backtesting.corporate_actions.apply_session_actions` | Pure, immutable pre-open quantity/basis/stop/order/dividend state transition |
| `research.historical_benchmarks.evaluate_historical_benchmark` | Explicit price-return, cash-total-return or reinvested-total-return comparator |
| `require_compatible_benchmark_conventions` | Reject silently incompatible return/payment conventions |
| `research.historical_demo.run_historical_synthetic` | Synthetic-only qualification artifacts, not historical strategy execution |

[Acquisition reference](R4A_ACQUISITION.md) gives exact transport/normalization usage,
safe errors, resource bounds and a fully mocked example. There is **no acquisition CLI**,
environment/credential discovery, automatic provider request or scheduled worker.
The optional concrete transport accepts caller-supplied authentication; every test
mocks HTTP. No Alpaca credentials or authenticated endpoints were accessed in R4-A.

V1 loader, `run_backtest`, `run_causal_backtest`, ordinary research `run`/`evaluate`,
metrics and R3 workflow/ledger remain unchanged. They do not silently dispatch v2.
V2 is an explicit library boundary plus a synthetic qualification command; adapting
causal strategy/risk execution to v2 requires a separately authorized phase and tests.
The new artifact schema is not silently added as a new R3 workflow mode.
Existing R3 experiment requests pin source/environment identity. A changed checkout
therefore requires a new experiment identity/state, or the original qualified source
to resume old evidence; no ledger migration or silent provenance replacement occurs.

## Snapshot v2

The [original synthetic fixture](../../tests/fixtures/historical_snapshot/manifest.json)
contains six sessions across the New York March DST change, one fictional security,
two splits and one dividend. It contains no recorded vendor observations.

V2 requires two hash/size-verified JSON files: `raw_bars` and `corporate_actions`.
Decimal prices are encoded as exact strings; raw volume is integral. File paths are
relative regular files without symlink traversal. JSON duplicate keys, repeated
observations, malformed OHLC and unknown securities/sessions fail validation. Input
row order is normalized by security ID/date; different source bytes retain distinct
provenance identities. No prices are forward-filled.

The manifest additionally requires:

- Explicit regular-session opens/closes, timezone, early-close flags, calendar
  authority/version and separate price/volume session scope. Supported closes are
  16:00 or declared 13:00 New York. Calendar completeness is a source attestation;
  the loader does not independently discover exchange holidays.
- Stable security IDs and nonoverlapping symbol intervals with source, availability
  and point-in-time status. Every covered security/session needs one mapping.
  Uncertain identities fail unless `allow_uncertain` is explicitly selected and
  retained in warnings. This does not establish survivorship-free membership.
- Actual acquisition/query provenance, SIP/raw/daily request basis, complete
  pagination receipts, page SHA-256, first query parameters and per-page query
  hashes. Action queries preserve their process-date semantics and absent feed,
  currency/as-of parameters. Bar `asof="-"` is preserved, not relabeled as a date.
- A declared complete action inventory and expected action IDs. Missing declared
  records fail. Exhausting API pages or querying all action types does **not**
  prove ex-date completeness, correct source records or absence of unknown actions.
- Revision ID, optional parent manifest hash and correction observation time.
  The loader never writes inputs. A revised snapshot has a new root hash; callers
  should pin `expected_sha256`. Parent existence/authenticity is not independently
  established by recording its declared digest.
- Explicit entitlement, storage, retention, raw-redistribution and derived-publication
  classifications and restrictions. Historical inputs require the first three
  confirmed. These declarations require external supporting evidence; the loader
  does not grant rights. Current Alpaca clearance remains unresolved.

An explicitly excluded missing row must exactly match a declared exclusion/reason.
Benchmarks and the qualification command reject missing prices needed by their path.
This restricted mode never substitutes prices or silently removes a benchmark member.

## Time and feature prices

Event/effective session, information availability, acquisition and correction observation
are distinct. `historical_availability` binds record bases to synthetic, observed or
explicitly reconstructed evidence. Observed bar/action availability cannot predate the
linked acquisition request or follow its completion. Reconstruction is tagged `assumed`,
with a statement and evidence reference; it is not provider-observed historical latency.
Historical inputs cannot retain synthetic observation/action/identity evidence.

`feature_view(..., basis="raw")` exposes only completed, available bars whose security
mapping is available by the cutoff. `split_asof` restates earlier prices/volumes using
only splits effective and known by that cutoff, including the action's identity mapping.
A due but unavailable split/mapping fails closed. A future split cannot restate an
earlier view. Prices divide and volumes multiply by the split ratio.

Corrected snapshots cannot produce feature views predating their correction observation.
Automatic stitching of original/corrected vintages and retrospectively corrected-history
replay are unsupported. Provider-adjusted-to-freeze bars are never automatically admitted
as causal features or raw execution. Dividend-adjusted feature views are unsupported;
raw dividend discontinuities remain explicit. Acquiring today does not reconstruct the
market data actually available at a historical decision.

## Corporate-action accounting

Call `apply_session_actions` with prior-close holdings **before opening fills**, the
complete retained action inventory and the exact calendar opening cutoff. The function
has no network, filesystem or broker side effects. It returns a new state.

Splits multiply position and pending-order quantities and divide protective stops and
pending limit/stop levels by the same ratio. Total position cost basis remains unchanged;
cost per share consequently divides. `fractional_policy="reject"` rejects fractional
resulting quantities. `"exact"` permits exactly representable Decimal fractions. A fixed
50-digit context traps inexact arithmetic independently of ambient precision/rounding.
Nonterminating Decimal transformations and cash-in-lieu fail explicitly. No fraction
is silently rounded away and no cash-in-lieu price is invented.

Same-session splits precede dividend entitlements; domain cash rates explicitly use
post-split shares. The Alpaca normalizer rejects coincident provider split/dividend
records until independent evidence establishes that share basis. It also rejects
unsupported action classes, foreign/special distributions and ambiguous required fields.

Dividends accrue from pre-open holdings on ex-date. Ex-date opening purchases receive
no entitlement; later sales retain the earned entitlement. Receivables contribute to
equity but cannot finance orders before payment. Payment credits cash once on the first
processed session on/after payment date, including non-session payment dates. A later
split does not multiply an existing dollar entitlement. No dividend price adjustment
is combined with cash credits, preventing double counting.

Repeated transitions preserve effects through action-content fingerprints. Duplicate,
changed, missed/unavailable actions, backwards sessions and inconsistent restored
entitlements fail. This is domain validation, not authenticated protection against
coordinated rewriting of a complete portfolio history. Prior eligible share ownership
requires the caller's real holding ledger. R3's durable publication mechanism is unchanged.

## Benchmarks and numerical qualification

The new analytical comparator requires an explicit convention:

| Convention | Splits | Dividends |
| --- | --- | --- |
| `price_return` | Preserve economic units | Ignore cash distributions explicitly |
| `total_return_cash` | Preserve economic units | Ex-date receivable, payment cash, no reinvestment |
| `total_return_reinvest` | Preserve economic units | Same entitlement; reinvest payable cash at payment-eligible open |

All use raw marks, fractional units, zero cash yield/fees/slippage/taxes and no fabricated
terminal sale. Reinvestment assumes payment cash is available at that open; this is an
explicit analytical convention, not observed intraday settlement. Exact Fraction arithmetic
handles recurring unit quantities. Reports use 50 significant Decimal digits with
ROUND_HALF_EVEN and retain exact rational units/equity/return strings. Reported equity
sums reported cash, receivables and market value under the same fixed context.

The synthetic fixture starts with 1000 at 400 (2.5 units). A 4:1 split produces 10 units
at 100. A dividend of 1 creates a 10 receivable on the next ex-date. A later 10:1 split
produces 100 units without changing that receivable. Payment at an open of 10 credits
10 cash; reinvestment buys one extra unit. A final mark of 11 yields price equity 1100,
cash total-return equity 1110, and reinvested equity 1111. These are independently
calculated artificial accounting checks, not observed market returns.

The synthetic command additionally exercises the finite-Decimal ledger and split-as-of
views, comparing every cash-total-return equity point with the rational comparator:

```bash
uv run --offline --no-sync python -m packages.research.historical_demo \
  --dataset tests/fixtures/historical_snapshot/manifest.json \
  --security-id synthetic:001 --initial-cash 1000 --output results/r4a-example
```

Only synthetic-kind manifests are accepted, before reading their observation files.
The initial allocation is analytical; its pending order/stop are inert conversion
probes, not risk-approved orders or a replacement simulator. Outputs include config,
accounting, benchmarks, features, comparisons, report, source/data manifest and hash
index through the existing atomic publisher. Runtime host/time metadata remains separate.
Existing output directories are immutable. [Verification](R4A_VERIFICATION.md) records
executed commands, numerical evidence and reproducibility hashes.

## Deferred decisions and blockers

No acquisition, historical study, optimization or AI-uplift evaluation was executed.
Written Alpaca clarification of historical SIP use, snapshot storage/retention and derived
publication is pending. Continuous SIP coverage, early SPY dividend completeness,
adjustment-factor reconciliation, entity mapping and regular-session/volume conventions
still need qualification. Earnings availability, point-in-time universe/delistings,
historical news evidence and holdout contamination remain scientific limitations.
The proposed 2016–2018 design alternative is **not registered or implemented**.

R4-B or later work needs explicit authorization and independent R4-A acceptance.

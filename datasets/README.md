# Offline market snapshots

R1 loads local manifests with `packages.data.snapshots.load_dataset_snapshot(Path(...))`.
No loader operation requests providers or downloads missing inputs. Private or licensed
inputs and generated results are ignored; the original synthetic reference lives at
[`tests/fixtures/market_snapshot/manifest.json`](../tests/fixtures/market_snapshot/manifest.json).

The version `market-snapshot/v1` manifest declares source, license, freeze timestamp,
coverage, sorted symbols, timezone, explicit session dates/open/close timestamps,
normalization version, universe selection and survivorship limitations. Each ordered
CSV file declares its relative path, size and SHA-256. Paths cannot escape the manifest
directory. Rows are globally ordered by `(symbol, date)` across the listed files;
duplicates and unsorted input fail instead of being silently normalized.

CSV columns are exactly `symbol,date,open,high,low,close,volume,available_at`.
Session dates use ISO dates; timestamps require UTC offsets. OHLC is finite and positive,
open/close lie inside low/high, and volume is a nonnegative integer. Availability must
follow the explicit session close and precede the freeze. The decision cutoff is one
minute after the declared close; later observations cannot enter that decision's features.
The explicit calendar is authoritative: missing rows produce sorted per-symbol/session
warnings or a failure under `missing_session_policy: reject`. No tradable prices are
forward-filled. Supply a verified exchange calendar for real studies, including closures
and early closes; the loader checks declared calendar consistency, not external accuracy.

R1 supports **raw prices for both features and execution**, with
`corporate_action_policy: none_in_coverage` and `dividend_policy: none_in_coverage`.
Adjusted/mixed series and other action policies are rejected. This intentionally limits
R1 to action-free coverage; it cannot simulate splits, cash dividends or adjusted-to-raw
stop conversion. Separate feature/execution mappings keep this boundary explicit.

The synthetic fixture has 210 weekday sessions and three symbols (630 rows). It contains
original arithmetic values, volume changes and a gap, not recorded market observations.
Its weekday calendar includes dates that may be exchange holidays and is explicitly
not an exchange calendar. Symbols are illustrative and fixed, not historical membership.
The fixture is dedicated under CC0-1.0; no provider data or third-party payload is included.

## Explicit historical contract v2

R4-A adds `packages.data.historical_snapshots.load_historical_snapshot` for
`market-snapshot/v2`, with raw execution, cutoff-specific split feature views,
corporate actions, security mappings, explicit query/calendar/revision/rights provenance
and exact JSON Decimal values. V1 above remains unchanged; ordinary R1/R2 commands
do not silently consume v2. [R4-A contracts](../docs/research/R4A_IMPLEMENTATION.md) and
the [original synthetic v2 fixture](../tests/fixtures/historical_snapshot/manifest.json)
document the separate R4-A boundary. Historical acquisition and empirical execution remained
blocked pending rights/data qualification and separate authorization.

## Private R4-B candidates

R4-B separately authorizes finite Basic/IEX acquisition for personal noncommercial
qualification. Real captures, source receipts, normalized rows and independent issuer
workbooks belong only under gitignored `datasets/private/r4b/<new-workspace>/`.
No provider observations are public fixtures. `historical-candidate/v1` preserves failed
or incomplete evidence; it is not an admitted v2 snapshot. Offline qualification never
changes the frozen input. The observed preflight candidate is blocked by an unsupported
action flag and unresolved evidence. See [R4-B contracts](../docs/research/R4B_IMPLEMENTATION.md)
and [qualification](../docs/research/R4B_DATA_QUALIFICATION.md).

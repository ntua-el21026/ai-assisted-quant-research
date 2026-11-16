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

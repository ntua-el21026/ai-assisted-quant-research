# R4-A historical acquisition and normalization contract

R4-A qualifies these interfaces with original synthetic responses and mocked HTTP.
It does not acquire a historical dataset or establish empirical research results.
**2026-11-17 status:** independently accepted at `0dd0875` for that synthetic scope.
The separately authorized [R4-B extension](R4B_IMPLEMENTATION.md) adds explicit IEX
selection and private acquisition, with remaining rights and qualification restrictions.
The following describes R4-A's original boundary; its SIP examples remain compatible.
Provider entitlement, storage, retention and publication rights remain unresolved for
any proposed real dataset. The canonical research CLI remains offline; R4-A exposes
no download command or automatic provider fallback.

The implementation is in [alpaca_historical.py](../../packages/data/alpaca_historical.py)
and [historical_normalization.py](../../packages/data/historical_normalization.py).
The separate [v2 models](../../packages/data/historical_models.py) and
[v2 loader](../../packages/data/historical_snapshots.py) preserve the existing v1
snapshot and research interfaces. Provider parameter semantics are documented in
Alpaca's [historical bars reference](https://docs.alpaca.markets/us/reference/stockbars)
and [corporate actions reference](https://docs.alpaca.markets/us/reference/corporateactions-1).
The [official SDK action models](https://github.com/alpacahq/alpaca-py/blob/master/alpaca/data/models/corporate_actions.py)
identify the supported wire fields; they do not supply a historical availability or
revision history.

## Interfaces and boundaries

| Interface | Contract |
| --- | --- |
| `HistoricalBarsRequest` | Required `provider="alpaca"`, `feed="sip"`, `adjustment`, `timeframe="1Day"`, `symbols`, `start`, `end`; optional `asof`, `limit`, `max_pages` |
| `CorporateActionsRequest` | Required `provider="alpaca"`, `symbols`, inclusive process-date `start`/`end`, and `types`; optional `limit`, `max_pages` |
| `decode_historical_page(body)` | Exact JSON numeric decoding with duplicate-key rejection |
| `historical_query(request)` | Pure construction of `(endpoint, dict[str, str])` for the first page |
| `HttpTransport.get(endpoint, params, timeout_seconds)` | Injected boundary returning `HttpResponse(status_code, headers, body: bytes)` |
| `UrllibHistoricalTransport` | Optional concrete read-only transport, configured directly by its caller; no credential discovery |
| `AlpacaHistoricalAcquirer` | Requires a transport; accepts `retry`, `clock`, `sleep`, `timeout_seconds`, `max_total_body_bytes` |
| `fetch_bars(request)` / `fetch_actions(request)` | Return `HistoricalAcquisition` after exhausting pagination; no file publication |
| `normalize_historical_bars(acquisition, *, sessions, missing_policy, availability=None)` | Pure calendar/price validation, ordered bars and missing-session diagnostics |
| `normalize_corporate_actions(acquisition, *, security_ids)` | Pure bounded conversion to shared `SplitAction` and `CashDividendAction` records |
| `to_snapshot_bar(observation, *, security_id, acquisition_id, mocked)` | Convert exact raw values to a v2 bar with caller-owned identity and evidence labels |
| `to_acquisition_provenance(acquisition, *, acquisition_id, mocked)` | Validate the query/pagination chain and construct a v2 receipt |

Request models reject additional fields and invalid supported values. Symbols must
be nonempty, unique uppercase ticker identifiers matching
`[A-Z][A-Z0-9.-]{0,19}`; accepted symbols are sorted. `start <= end` is required.
Adjustment is explicitly one of `raw`, `split`, `dividend`, `all`. The adapter
supports daily SIP requests and never substitutes IEX after a failure. A provider
`all` adjustment can incorporate spin-offs as well as splits and dividends; these
values are not admitted as causal raw execution observations.

`HistoricalBarsRequest.asof` is an identity-selection date or the literal `"-"`,
which is the default and disables provider symbol mapping. It is not a data
revision cutoff. The bridge preserves `"-"` exactly. Corporate-action queries have
no `asof`, feed or currency parameter; their receipt fields are `None`, rather
than invented bar-query values.

## Synthetic transport example

This complete example uses an invented response and a fixed synthetic acquisition
clock. It performs no network request and writes no files. Its mock labels describe
synthetic evidence even though the request describes the Alpaca wire contract.

```python
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from packages.data.alpaca_historical import (
    BARS_ENDPOINT,
    AlpacaHistoricalAcquirer,
    HistoricalBarsRequest,
    HttpResponse,
    normalize_historical_bars,
)
from packages.data.historical_normalization import (
    to_acquisition_provenance,
    to_snapshot_bar,
)
from packages.data.snapshots import MarketSession


class OriginalSyntheticTransport:
    def get(
        self,
        endpoint: str,
        params: Mapping[str, str],
        timeout_seconds: float,
    ) -> HttpResponse:
        assert endpoint == BARS_ENDPOINT
        assert params["feed"] == "sip"
        return HttpResponse(
            200,
            {},
            b'{"bars":{"SYN":[{"t":"2025-03-10T04:00:00Z",'
            b'"o":100.25,"h":101,"l":99,"c":100.5,"v":1200}]},'
            b'"next_page_token":null}',
        )


request = HistoricalBarsRequest(
    provider="alpaca",
    feed="sip",
    adjustment="raw",
    timeframe="1Day",
    symbols=("SYN",),
    start="2025-03-10",
    end="2025-03-10",
)
acquisition = AlpacaHistoricalAcquirer(
    transport=OriginalSyntheticTransport(),
    clock=lambda: datetime(2025, 4, 1, 12, tzinfo=UTC),
).fetch_bars(request)
observations = normalize_historical_bars(
    acquisition,
    sessions=(MarketSession(
        date="2025-03-10",
        open_at="2025-03-10T13:30:00Z",
        close_at="2025-03-10T20:00:00Z",
    ),),
    missing_policy="error",
)
receipt = to_acquisition_provenance(
    acquisition, acquisition_id="original-synthetic-bars", mocked=True,
)
bar = to_snapshot_bar(
    observations.bars[0],
    security_id="synthetic:001",
    acquisition_id=receipt.acquisition_id,
    mocked=True,
)
assert receipt.provider == "synthetic" and receipt.mocked
assert receipt.asof == "-"
assert bar.open == Decimal("100.25")
assert bar.availability_basis == "synthetic"
```

The production transport is optional and absent from this example. Its caller owns
explicit authentication configuration; the module does not inspect environment
variables, configuration files or account state. It allows `GET` only to the exact
HTTPS data paths `/v2/stocks/bars` and `/v1/corporate-actions` on
`data.alpaca.markets`, disables ambient proxies and rejects redirects. Tests replace
its opener, including success/error-body reads and close failures. No actual
provider request forms part of R4-A verification.

## Resource limits, pagination and retries

| Control | Default | Supported bound |
| --- | --- | --- |
| Bars `limit` | 10,000 rows/page | 1–10,000 total rows across symbols |
| Actions `limit` | 1,000 records/page | 1–1,000 total records |
| Request `max_pages` | 1,000 | 1–10,000 |
| HTTP `timeout_seconds` | 20 seconds | Finite, greater than zero, at most 120 |
| Concrete transport `max_body_bytes` | 16 MiB/response | 1 byte–64 MiB |
| Acquirer `max_total_body_bytes` | 128 MiB | 1 byte–1 GiB of retained successful page bodies |
| Retry `max_attempts` | 3/page, including first attempt | 1–10 |
| Retry `initial_delay_seconds` | 1 | Greater than zero, at most 60 |
| Retry `max_delay_seconds` | 60 | Greater than zero, at most 300 |
| Retry `max_total_wait_seconds` | 300/acquisition | 0–3,600 |

Pagination uses the global `next_page_token`, including when a page contains no
bars or only one requested symbol. A non-null token must be followed. Cycles,
empty/oversized/non-string tokens, missing pagination fields and page-limit
exhaustion fail explicitly. Duplicate JSON object keys at any depth are rejected;
an ambiguous duplicate terminal token cannot certify completion. Accepted tokens have at most 4,096 characters.
Successful pages are retained only within the aggregate body budget. Injected
transports own their individual response-read bound; the aggregate acquirer check
also applies to injected responses.

Retries apply to transport failures and HTTP 429, 500, 502, 503 and 504. The base
wait is `min(max_delay_seconds, initial_delay_seconds * 2**attempt)`, with the first
retry using `attempt=0`. `Retry-After` seconds or HTTP dates take precedence over
`X-RateLimit-Reset` epoch seconds. A declared provider delay can increase the base
wait. If that delay exceeds the individual or aggregate wait budget, acquisition
fails without retrying early. A successful page with another page outstanding and
`X-RateLimit-Remaining: 0` also observes the rate-delay policy. Header names are
case-insensitive. This is rate-header-aware retry behavior, not an independent
fixed-quota scheduler.

The urllib timeout concerns blocking socket operations. It is not a global
wall-clock deadline for the complete acquisition. The aggregate byte limit counts
raw successful response bodies; decoded objects, normalized records and transient
retry responses have additional memory costs. Failures do not return a completed
partial acquisition or publish files.

## Acquisition and timestamp evidence

`HistoricalAcquisition` holds the typed request, UTC `request_started_at`, UTC
`acquired_at`, and ordered `AcquiredPage` records. Each page retains its endpoint,
full query including any pagination token, raw response bytes, `received_at`, and
computed SHA-256. The final successful page's received time is the acquisition
completion time. A naive clock or decreasing recorded page clock fails.

Date boundaries are interpreted in `America/New_York` and encoded in UTC: start
is local midnight; end is the final microsecond before the next local midnight.
Daily provider timestamps must be offset-aware and resolve to exactly New York
midnight. Session dates are derived in that zone, including daylight-saving
changes. The caller supplies the actual session calendar; normalization neither
infers holidays from received rows nor generates weekday sessions. A supplied
session must lie inside the request dates and have opening/closing timestamps on
its declared local date. Received bars must belong to declared sessions, whose
closes must precede acquisition.

The default `BarAvailabilityPolicy(mode="observed")` sets every normalized row's
`available_at` to acquisition completion. This is a conservative observed bound;
it does not establish when the historical bar first became available. A historical
close-plus-delay reconstruction requires explicit
`mode="assumed_close_plus_delay"`, `delay_seconds` from 0 to 86,400 and a nonblank
`rationale`. Such rows carry `availability_basis="assumed"`; their availability
cannot exceed acquisition. The policy and warnings accompany the normalized
result. A reconstructed clock does not make later provider adjustments or
revisions causally available in the past.

`NormalizedHistoricalBars` contains bars sorted by `(symbol, session date)`,
`MissingBar` exclusions, warnings and the availability policy. `missing_policy` is
required: `"error"` rejects missing symbol/session pairs; `"exclude"` records the
exact missing pairs without filling them. Duplicate keys, unexpected symbols,
invalid OHLCV and unavailable/incomplete sessions fail under either policy.

The acquisition module's `HistoricalBar` is an observation envelope, distinct from
the v2 class with the same name. It carries the legacy `AdjustedDailyBar`, provider
timestamp, acquisition/availability times, availability basis, adjustment, feed and
`ExactOHLCV`. Source JSON decimals are preserved before the legacy float projection.
Exact OHLC range validation also prevents binary rounding from hiding a source
range violation. V2 conversion uses `ExactOHLCV` directly; it never reconstructs
source decimals from the legacy float values.

## Corporate-action scope and supported normalization

`CorporateActionsRequest.types="all"` omits the provider's type filter. An explicit
nonempty tuple can request `forward_split`, `reverse_split` and/or `cash_dividend`
for a targeted probe. Filtered acquisitions emit
`corporate_action_inventory_filtered` and cannot become complete v2 action receipts.
An all-type response containing an unsupported category fails normalization; it
cannot silently remove an observed spin-off or merger.

The inclusive action query dates filter **process dates**, not ex-dates. Every
action acquisition therefore carries
`process_date_window_does_not_certify_ex_date_coverage` and
`provider_creation_time_unverified`. Exhausted pagination proves completion of
that query. It does not prove a complete ex-date inventory, absence of delayed
announcements, or point-in-time availability. The snapshot's complete-inventory
attestation, expected action IDs and source evidence remain separate obligations.

Supported records use caller-supplied `symbol -> security_id` mappings. Forward and
reverse splits convert exact `new_rate / old_rate` values to reduced integer
numerator/denominator terms and must agree with their reported direction. Ordinary
domestic cash dividends require an ex-date and payable date, preserve exact cash
amounts, and use the framework's declared USD convention. An explicitly non-USD
provider value is rejected. An absent currency field is not turned into a claim
that the provider reported a currency; action receipts retain `currency=None`.

Cash and split rates require at most 64 encoded characters, at most 32 decimal
coefficient digits and finite positive magnitudes in `[1e-9, 1e9]`. Reduced split
numerator and denominator terms must each be at most one billion. Values outside
these supported bounds fail before unbounded integer fraction expansion. These
bounds are implementation support limits, not empirical properties of dividends
or splits.

The normalizer rejects missing required fields, invalid dates/ratios, unknown
identity, process dates outside the queried window, duplicate/contradictory shared
actions, special/foreign dividends and unsupported action classes. A split and
cash dividend for the same security/ex-date are rejected as
`ambiguous_dividend_share_basis`: the wire record supplies no evidence that its
cash rate uses the shared domain's required post-split share basis. Independently
specified synthetic accounting can test that convention; provider normalization
does not invent it. Normalized action availability is acquisition time with basis
`"observed"`; this helper offers no historical action-availability reconstruction.
The action normalizer is transport-agnostic. A producer assembling a synthetic v2
fixture from mocked action responses must explicitly construct synthetic-labeled
shared action records; the receipt converter does not rewrite action evidence.
Observed or reconstructed historical timestamps must never be substituted for
invented fixture timestamps without the corresponding evidence declaration.

## V2 integration and provenance responsibilities

The bridge converts observations and receipts; it does not write snapshots or
certify a dataset. Its caller supplies stable security IDs, acquisition IDs and
an explicit `mocked` flag. `mocked=True` produces `provider="synthetic"` receipts
and synthetic bar availability labels. Otherwise the receipt names Alpaca and bar
availability retains its observed/assumed basis. Descriptive fixture/source labels
belong in the manifest's source and availability evidence fields. Mock flags
cannot authenticate a real observation: callers remain responsible for truthful
source declarations.

`to_snapshot_bar` accepts raw execution observations only. It maps exact prices,
volume, symbol, session date and availability to
`historical_models.HistoricalBar`; the explicit security/acquisition IDs supply
its remaining references. A point-in-time symbol mapping must cover the specific
bar date. Action identity likewise needs an independently supported mapping at its
ex-date; a single ticker string is not evidence of a permanent security identity.

`to_acquisition_provenance` verifies each page endpoint and base query against the
typed request, validates the complete token chain, and requires terminal
`next_page_token=None`. This verification also applies to manually constructed
`HistoricalAcquisition` objects. Every page timestamp must be aware,
nondecreasing and inside the request/completion interval; the final page timestamp
must equal acquisition completion. The receipt records the exact first-page
`query_parameters` without a pagination token, ordered `page_sha256` values and
`page_query_sha256` for every actual page query. A query hash is SHA-256 of its
UTF-8 JSON object with sorted keys and compact `,`/`:` separators. Opaque page-token
values remain inside the retained acquisition; receipts retain their query hashes.
Different pagination can change receipt hashes while producing identical exact v2
observation values. Per-page hashes remain source provenance, not observation
identity.

The snapshot producer must additionally provide the complete calendar and its
qualified authority/version, price/volume session convention, stable identity
history, availability evidence, file bytes/sizes/hashes, freeze/revision metadata,
rights declarations, exclusions and independently justified complete action
inventory. Calendar labeling alone does not establish whether provider daily
price and volume aggregation match the selected execution convention. Corrected
inputs require a new immutable revision; provider `asof` is not revision evidence.

The v2 loader verifies recorded contracts and file integrity; these checks cannot
prove vendor truth, calendar completeness or legal permissions. Historical
storage/retention/entitlement must be confirmed before a real v2 dataset is
accepted. Raw-data redistribution and publication permissions require their own
recorded decisions. R4-A's synthetic fixtures confer no rights over provider data.

## Errors and verification

`HistoricalAcquisitionError.code` and its message contain a closed implementation
failure code. Provider response text, raw exception messages and authentication
values are not copied into these errors. Input-schema violations instead raise
Pydantic `ValidationError`; callers must distinguish malformed caller input from
provider/transport failure. HTTP 403 is `forbidden`, because its status alone does
not identify an entitlement versus account/authentication problem.

| Area | Failure codes |
| --- | --- |
| Configuration and transport | `missing_credentials`, `invalid_body_limit`, `invalid_total_body_limit`, `invalid_timeout`, `endpoint_rejected`, `redirect_rejected`, `transport_failed`, `body_limit_exceeded`, `total_body_limit_exceeded` |
| HTTP outcomes | `authentication_failed`, `forbidden`, `invalid_request`, `rate_limited`, `provider_failed` |
| Payload and pagination | `invalid_json`, `invalid_page`, `pagination_cycle`, `page_limit_exceeded` |
| Rate policy and clocks | `invalid_retry_header`, `retry_budget_exceeded`, `naive_clock`, `clock_regressed` |
| Bar normalization | `invalid_normalization_request`, `invalid_calendar`, `invalid_bar_timestamp`, `unexpected_session`, `unexpected_symbol`, `incomplete_session`, `invalid_ohlcv`, `duplicate_session`, `missing_sessions`, `availability_after_acquisition` |
| Action normalization | `unknown_security_identity`, `action_outside_process_window`, `unsupported_corporate_action`, `invalid_corporate_action`, `ambiguous_dividend_share_basis` |
| V2 bridge (`HistoricalNormalizationError`) | `raw_execution_required`, `filtered_action_inventory`, `invalid_acquisition_query`, `invalid_pagination_chain`, `invalid_acquisition_times` |

The focused synthetic verification commands are:

```bash
uv run --offline --no-sync pytest tests/unit/test_alpaca_historical.py tests/unit/test_historical_normalization.py -q
uv run --offline --no-sync ruff check packages/data/alpaca_historical.py packages/data/historical_normalization.py tests/unit/test_alpaca_historical.py tests/unit/test_historical_normalization.py
uv run --offline --no-sync mypy packages/data/alpaca_historical.py packages/data/historical_normalization.py
```

Tests include global/empty-page pagination, bounds and retry exhaustion, rate
headers, DST, missing/duplicate sessions, exact decimals, query-chain forgery,
page-independent converted values and raw-only admission. Peer review added
regressions for response-read/close failures and sanitized tracebacks, split
category/ratio contradictions, explicit non-USD values, unsupported all-inventory
actions, ambiguous coincident dividends and bounded decimal/fraction processing.
These are software and synthetic arithmetic checks. They do not qualify actual
provider access, licensed historical inputs, calendar/aggregation suitability or
empirical strategy performance.

# R4-B data qualification — 2026-11-17

**Historical checkpoint record:** R4-B engineering was subsequently accepted at
`a6d3a09`; this failed dataset/qualification is preserved. Later pilot acquisition and
action-scope findings are reported separately in [R4-B.1 qualification](R4B1_DATA_QUALIFICATION.md).

**Dataset-to-R4-C verdict: BLOCKED.** The bounded preflight established authenticated
IEX response access for this account and sample, not a qualified historical study
dataset. The special-dividend classification failure is preserved; no pilot, larger
candidate, strategy run, optimization or holdout performance inspection followed.
Engineering verification is reported [separately](R4B_VERIFICATION.md).

## Rights and evidence authority

Sources checked 2026-11-17:

- [Alpaca paper-only documentation](https://docs.alpaca.markets/us/docs/paper-trading)
  explicitly limits paper-only market-data use to IEX.
- [Basic market-data documentation](https://docs.alpaca.markets/us/docs/about-market-data-api)
  describes free Basic, IEX coverage, historical data since 2016 and 200 historical
  calls/minute. The broader delayed-history wording does not resolve paper-only SIP use.
- [Corporate-action reference](https://docs.alpaca.markets/us/reference/corporateactions-1)
  documents process-date filtering, all-type discovery, pagination, data-quality filters
  and absence of guaranteed creation/availability time.
- Owner-reported Alpaca Support **#397685** authorizes personal noncommercial
  research/backtesting and local storage within entitlements. The private ticket was
  not independently retrieved or published. This is explicit owner-provided authority,
  not an inference from an HTTP success or a general redistribution license.

| Operation | R4-B classification | Evidence or unresolved condition |
| --- | --- | --- |
| Personal noncommercial IEX research/backtesting and local analysis/storage | Authorized within account entitlements | Owner-reported support plus official paper/Basic documentation |
| Historical IEX response access for this account | Verified for narrow completed sample | One explicit `feed=iex`, `adjustment=raw`, `1Day` GET returned valid rows |
| Historical SIP use | Unresolved; not requested | Paper-only restriction governs; no silent fallback or entitlement probe |
| Persistent/post-account retention and long-lived frozen research datasets | Requires clarification | Local storage authorization does not by itself settle retention duration |
| Public independent code/synthetic examples | Project-owned material only | No provider data included |
| Public empirical charts/statistics | Requires clarification; deferred | Ticket did not expressly settle derived-result publication |
| Raw/adjusted vendor observations or reconstructible datasets | No publication authorized | Kept private; not committed |
| Complete 2016–2019 corporate-action inventory | Unverified and restricted | Neither a successful query nor an early event would establish completeness |

No subscription/plan change, payment, broker-account mutation, live/paper order or SIP
request occurred. Successful authentication is not independent verification of account
plan settings or a grant of data rights. No account endpoint was queried.

## Registered budget and actual acquisition

The plan hash is
`6eb3b0b4e425884aeda36ef284dd237047650b9caa55d34e5ef14c245bba0c49`.
It fixes symbols/windows before observations, allows at most 100 authenticated attempts,
250 MiB body contents, 1 GiB retained contents and 900 seconds. All-status accounting is
more conservative than counting successful bodies alone. The runner used **two GETs,
both HTTP 200, 1,457 received/successful body bytes**, with no retries. It made no
additional authenticated requests after the action normalization failure. Actual
response rate-limit headers were not retained; no throttling response was observed.
The documented 200/minute rate is not an experimentally established throughput claim.

| Source/feed and window | Local acquisition | Coverage/completeness | Actions, identity and availability | Next phase |
| --- | --- | --- | --- | --- |
| Alpaca Basic/IEX raw SPY/QQQ daily, 2025-01-06–2025-01-10 | Acquired privately; one page | 8 expected/8 observed rows; four sessions each; no missing/duplicate/invalid rows | Only acquisition-observed availability; current-ticker identity uncertain | Restricted preflight sample only |
| Alpaca corporate actions SPY/QQQ, process dates 2024-01-01–2024-03-31, all types/quality | Acquired privately; one terminal page | Two cash-dividend records; exhaustion proves this query only | One `special=true`; strict normalizer rejects; complete historical inventory unproved | BLOCKED |
| Planned IEX pilot SPY/QQQ, 2024–2025 | NOT ACQUIRED: stopped before pilot | 502 scheduled sessions/1,004 expected pairs are calendar counts, not observed coverage | Not qualified | BLOCKED |
| Planned IEX candidate SPY/QQQ, 2020–2025 | NOT ACQUIRED | 1,508 scheduled sessions/3,016 expected pairs; no acquired candidate coverage | Not qualified | BLOCKED |
| Four planned narrow IEX probes, 2016–2019 | NOT REQUESTED | No R4-B evidence of early-year coverage | Action completeness and identities remain restricted | BLOCKED |
| Planned AAPL/NVDA split and ETF adjustment diagnostics | NOT REQUESTED | No R4-B empirical split/adjustment verification | Synthetic regression coverage only | Unverified |
| SIP, any period | NOT REQUESTED | No entitlement conclusion inferred from prior API successes | Written clarification still needed | BLOCKED |

Per-symbol observed bar coverage is identical: SPY **4/4**, QQQ **4/4** completed
sessions (January 6, 7, 8 and 10). January 9 is the official Carter memorial closure,
not a missing row. The field/type/range checks passed for raw OHLCV; daily timestamps
matched New York midnight. This winter-only sample does not independently verify actual
provider behavior across DST, early closes, long pagination or all calendar years.
Those cases are exercised with synthetic HTTP/calendar tests and remain empirical
qualification requirements. IEX volume/extrema/opening prices are venue observations;
neither raw basis nor schema validity establishes consolidated SIP-equivalent execution.
The requested feed is recorded, not independently inferred from underlying exchange prints.

## Corporate-action and independent-source qualification

All observed categories were inventoried before deciding support. Both returned records
are in `cash_dividends`; the normalizer rejects the special flag rather than silently
treating it as an ordinary dividend. The response lacks explicit currency fields;
R4-A's domestic-ordinary USD modeling assumption is unchanged and does not justify
inventing independent currency evidence. No provider announcement/revision history is
available from this query. An effective/ex-date or process date is not first information
availability, and a payable date is not cash received at ex-date.

Unknown-category count can be zero while economically unsupported records exist.
The deterministic finding `action_normalization_unsupported_corporate_action` is the
relevant failure. The frozen source classification is never overwritten with issuer
interpretation. The independent-source supplement below is diagnostic only; it cannot
retroactively turn a failed source record into an admitted v2 action inventory.

Independent issuer workbooks and any extracted reconciliation rows remain private.
Three bounded official workbooks were obtained: [SPDR distribution history](https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/spdr-etf-historical-distributions.xlsx),
[Invesco 2024](https://www.invesco.com/content/dam/invesco/us/en/documents/tax-document/ce-ici-primary-and-secondary-distribution-file-file-ivz-etf-2024-02-10-2025.xlsx)
and [Invesco 2025](https://www.invesco.com/content/dam/invesco/us/en/documents/tax-documents/ICI-Primary-and-Secondary-and-NRA-File-IVZ-ETF-2025.xlsx).
They provide 16 extracted 2024–2025 SPY/QQQ event records (eight each), with ex/pay dates
and amounts, but no established explicit ISO currency or historical declaration time.
Inventory completeness remains unverified.

Both retained Alpaca events have **2023 effective dates**, despite the 2024 process-date
query. One matches the broader downloaded SPDR history exactly on ex-date/pay-date/rate;
the other, which carries the special flag, is outside the downloaded Invesco books'
coverage. Its classification is therefore unverified. Absence from a different-year
workbook is not evidence of a missing/incorrect provider event. No normalization gate or
source flag changed. The 2024–2025 issuer rows cannot certify unacquired provider history.
Their receipt/field-verification results are recorded in the verification report. Missing
or unavailable verification remains explicit; this report does not claim a complete
issuer or provider action history. All-type process-date discovery also cannot establish
ex-date completeness, particularly for 2016–2019. QQQ's documented December 2025 fund
reorganization is an additional future candidate identity/action-inventory concern,
not a reason to silently shorten the registered data-quality window.

## Time, identity, revision and admission

The private manifest uses **observed acquisition availability**, not fictitious historical
publication dates. Event/session dates, actual receipt/acquisition UTC timestamps and
subsequent correction metadata are distinct. No historical correction time, permanent
identifier or announcement timestamp was fabricated. Logical `research:SPY`/`research:QQQ`
mappings are explicitly uncertain current-query mappings, not point-in-time membership.
Sampling present-day ETFs is survivor selection, not a survivorship-free equity universe.

Strict `market-snapshot/v2` admission is not attempted with invented `complete` inventory,
confirmed retention or causal history. The separate failed `historical-candidate/v1`
envelope retains source pages, exact normalized raw bars, complete query receipts,
hashes and explicit failures. Its aggregate report is **status FAIL, technical FAIL,
next phase BLOCKED**: the preflight bar component passes, while no primary study input
exists and action normalization fails. This is an honest negative qualification result.
Corrections require a new immutable identity; the original evidence remains unchanged.

## Scientific implications and narrowly scoped next work

The original proposed 2012–2018 design period remains unchanged and unsupported by
Alpaca's documented 2016 start. A 2016–2018 alternative or any later reduced period
requires a versioned proposal, contamination audit and owner approval. The data-quality
pilot/candidate windows above are not registered strategy-evaluation splits. No final
holdout performance has been opened.

Before authorizing historical strategy execution:

1. Resolve the special-distribution semantics with reliable issuer/provider evidence and
   a separately specified, tested supported mode; do not remove the rejection to progress.
2. Obtain explicit retention/frozen-snapshot and public derived-result rights. SIP needs
   separate paper-only entitlement evidence; IEX requires a declared venue-limited study
   and execution/volume limitations if retained as the research source.
3. Complete a newly bounded pilot and independent action reconciliation, then only a
   conditional larger acquisition. Audit provider aggregation/session conventions,
   missing rows, symbol changes and early-year coverage. No forward filling is acceptable.
4. Register any defensible temporal/universe restriction and realistic availability
   reconstruction before decisions are simulated. Contemporary corrected data do not
   supply an untouched historical information set.
5. Specify compatible raw next-open execution, split treatment, dividend receivables/
   payment dates, SPY total-return and exposure-adjusted benchmarks, risk-free assumption
   and warm-up. Earnings blackouts block unsupported single-stock studies; ETF-only
   qualification does not satisfy the original stock-universe protocol.
6. Keep AI/news comparisons neutral or explicitly unavailable until credible frozen
   as-of evidence exists. No historical AI output or uplift may be fabricated.

The recommended next authorization is a **data-blocker resolution and bounded requalification**
step. R4-C empirical execution is not ready. Public release of measured returns/charts
also remains a separate rights and methodological gate.

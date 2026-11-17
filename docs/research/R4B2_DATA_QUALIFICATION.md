# R4-B.2 frozen pilot qualification — 2026-11-17

**Pilot data: BLOCKED. R4-C readiness: BLOCKED.** Partial independent currency resolution
does not satisfy all applicable admission conditions. Engineering verification is a
separate PASS, subject to independent acceptance. There were **zero new authenticated
provider requests**, no larger acquisition and no historical strategy/benchmark run.

## Immutable inputs and 16-event audit

The original R4-B manifest remains
`8f9ed18dd45602979ca7ff1b35b6de332908ff75f26b325130ddffe0fba1335e`.
The frozen pilot manifest remains
`44d4de820bbad745cc14b2cad11f6adf34b412b58d33f7b9aefa886a39df444f`, at
`datasets/private/r4b/session-r4b1-20261117-v1/frozen/evidence/manifest.json`.
Its 22-file inventory contains 1,004/1,004 expected raw IEX daily observations:
502 sessions per symbol, January 2, 2024 through December 31, 2025. Existing calendar,
DST, holidays, early-close labels and OHLCV checks pass. That does not certify
consolidated-market volume, regular-session OHLC, auction prices or historical vintages.

The process-date action query returned 24 cash rows: 16 applicable, two prior-ex and six
future-ex rows. All remain immutable and traceable. R4-B.1's complete fresh-flat/raw
scope conditions continue to govern exclusions; no in-period action is excluded here.

The table identifies **every applicable distribution** without publishing protected
dates or amounts. `Exact` means direct Decimal equality; `representation` means unequal
source decimal strings with equal binary64 values, not an accepted tolerance. All rows
match issuer ticker/CUSIP/event keys. This is economic matching, not permanent or
point-in-time security identity. Raw currency is absent in every row. Provider special
and foreign flags are false in every row; independent regular/special semantics remain
unverified for all 16. Tax character is not used to negate a special flag.

| Event label | Ex-date | Payable date | Exact amount | Independent payout currency |
| --- | --- | --- | --- | --- |
| SPY 2024 Q1 | Match | Match | Exact | USD, explicit bounded policy receipt |
| SPY 2024 Q2 | Match | Match | Exact | USD, explicit bounded policy receipt |
| SPY 2024 Q3 | Match | Match | Exact | USD, explicit bounded policy receipt |
| SPY 2024 Q4 | Match | Match | Exact | Unresolved: payment crosses policy coverage |
| SPY 2025 Q1 | Match | Match | Exact | Unresolved |
| SPY 2025 Q2 | Match | Match | Exact | Unresolved |
| SPY 2025 Q3 | Match | Match | Exact | Unresolved |
| SPY 2025 Q4 | Match | Match | Exact | Unresolved |
| QQQ 2024 Q1 | Match | **Disagreement** | Representation unresolved | Unresolved |
| QQQ 2024 Q2 | Match | Match | Representation unresolved | Unresolved |
| QQQ 2024 Q3 | Match | Match | Representation unresolved | Unresolved |
| QQQ 2024 Q4 | Match | Match | Representation unresolved | Unresolved |
| QQQ 2025 Q1 | Match | Match | Representation unresolved | Unresolved |
| QQQ 2025 Q2 | Match | Match | Representation unresolved | Unresolved |
| QQQ 2025 Q3 | Match | Match | Representation unresolved | Unresolved |
| QQQ 2025 Q4 | Match | Match | Representation unresolved | Unresolved |

Exact private fields and page/record/source hashes are retained in the SPY matrix
`r4b2-spy-audit-20261117-v1/audit/per-event-matrix-v1.json`, SHA
`062e79458c08c7e51bfa95d5060e12ff7b3709415de37e1399a46470b876544f`, and QQQ matrix
`qqq-period-audit-r4b2-20261117-v2/audit/private-qqq-field-proof.json`, SHA
`0a17d40db1b95049832da705a6a3497c02b6b0ccf56b040c5236717f57022442`, both below
`datasets/private/r4b/`. No event key is missing or duplicated in this comparison.

## Official Alpaca semantics checked November 17, 2026

The [June 3, 2026 changelog](https://docs.alpaca.markets/us/changelog/2026-06-03-market-data-9dddd18)
adds region filtering, ISIN and currency. It supplies no absent-means-USD rule or guarantee
of retrospective field backfill. The current [OpenAPI](https://docs.alpaca.markets/us/openapi/market-data-api.json)
defines cash currency as an optional string, without a default or nullable type. Its
shared description permits USD, non-applicable or unknown interpretations of an empty
value. No US-cash-specific rule resolves an absent value. Domestic status and USD bar
quotes do not establish payout currency.

The [July 30 quality changelog](https://docs.alpaca.markets/us/changelog/2026-07-30-data-quality-1bddaa3)
explains that already-processed actions can appear under `complete` despite incomplete
fields. The [action endpoint](https://docs.alpaca.markets/us/reference/corporateactions-1)
filters process dates. Quality selection and terminal pagination prove neither field
repair nor complete ex-date inventory or historical announcement availability. No new
query was made hoping for different values.

The native schema reports OpenAPI 3.1.2/API version 1.1; rendered documentation identifies
1.4. This version distinction and current-versus-historical applicability are retained.
Seven native documentation captures, transformed rendered extracts and exact selected
schema fields are separately identified in the private API-evidence package. Native
OpenAPI SHA is `9c2a7a50aa0585ede66cb963ed8bdc73d9d1dd69ff1e1fd06a6ee027651a96a3`.

## Period-applicable issuer evidence and limits

The retained [SPDR historical distribution workbook](https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/spdr-etf-historical-distributions.xlsx)
matches all eight SPY identities, ex/record/payment dates and exact cash amounts.
Twelve inspected capital-component cells are blank and four explicitly zero; blanks
remain unknown. Neither ordinary-income tax treatment nor a quarterly schedule proves
that each event has independently confirmed `special=False`.

The [January 2024 SEC-filed SPY prospectus](https://www.sec.gov/Archives/edgar/data/884394/000119312524017688/d315180d497.htm),
Singapore supplement S-11, explicitly describes the Trust's Trustee distributions in
USD, separately from exchange quotation/conversion. Together with exact U.S. issuer
identity/event matches it supports three bounded, unknown-currency-only resolutions.
The fourth 2024 ex-date event pays after replacement by the
[January 2025 prospectus](https://www.sec.gov/Archives/edgar/data/884394/000119312525013533/d875286d497.htm).
That inspected text supplies no explicit USD-distribution clause. We do not extend the
2024 interpretation across it. Australian CDI rows describe underlying USD and converted
AUD separately, but their different timing/rounded gross values do not supply a verified
one-to-one U.S. event binding here. No arbitrary rounding or CDI substitution is applied.

The retained [Invesco 2024](https://www.invesco.com/content/dam/invesco/us/en/documents/tax-document/ce-ici-primary-and-secondary-distribution-file-file-ivz-etf-2024-02-10-2025.xlsx)
and [2025](https://www.invesco.com/content/dam/invesco/us/en/documents/tax-documents/ICI-Primary-and-Secondary-and-NRA-File-IVZ-ETF-2025.xlsx)
workbooks match all eight QQQ ex-date keys, seven payment dates and the correct
total-cash component. All eight rate pairs encode the same binary64 number; issuer
cells display eight decimals. That supports a serialization explanation, not authoritative
exact decimal intent. No tolerance, economic-error assertion or amount rewrite follows.

The [January 2024 QQQ filing](https://www.sec.gov/Archives/edgar/data/1067839/000119312524016662/d881880d485bpos.htm),
[May 2024 settlement supplement](https://www.sec.gov/Archives/edgar/data/1067839/000119312524151108/d817473d497.htm)
and [January 2025 filing](https://www.sec.gov/Archives/edgar/data/1067839/000119312525013448/d902673d485bpos.htm)
provide period-specific policy. The default payment-calendar formula corroborates the
issuer's disputed payable date, subject to trustee variation notices; actual credit time
and an event-specific contrary notice remain unverified. The provider disagreement is
retained, not silently replaced. Neither original prospectus establishes global USD
distribution currency in the inspected policy text. A later Hong Kong-holder USD clause
does not prove U.S./DTC payout currency for earlier events.

Seven QQQ events precede the December 2025 reorganization; one is on/after it. Current
ticker/CUSIP matching and the absence of a returned structural event do not establish
an unchanged legal identity or full action inventory. The earlier 2023 provider-special
event remains preserved; its tax character does not remove the flag or its in-period
blocker for the unacquired 2020–2025 candidate.

All new retrievals are November 17, 2026 observations. Original issuer/source retrievals
remain November 17, 2026 receipts. Document/filing dates, event times and retrieval times
remain distinct. No source proves original announcement/first-availability timestamps
or unchanged historical versions. Sources, retrieval timestamps, bytes, hashes and
remaining uncertainties are indexed privately; [verification](R4B2_VERIFICATION.md)
publishes only safe identifiers and hashes.

## IEX proxy-execution assessment

Official [aggregation rules](https://docs.alpaca.markets/us/docs/market-data-faq#how-are-bars-aggregated)
describe New York calendar-day bars with field-specific eligible trade conditions.
Extended-hours conditions may affect volume without affecting OHLC. The open is not
proved to be a 09:30 or primary-market auction fill. IEX high/low/volume are not
consolidated US-market observations. [Streaming rules](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data)
allow late updates/corrections; the [historical endpoint](https://docs.alpaca.markets/us/reference/stockbars)
does not expose a revision-vintage or regular-session filter. `asof` identifies the
security associated with a ticker, not the historical data version.

A separately approved **retrospective IEX venue-price proxy** could use an expressly
modeled next-session eligible price with costs and unattainability caveats. It could
not claim actual auction fills, genuine point-in-time publication, unchanged vintages,
consolidated execution quality or historically executable stops from these bars alone.
Full daily volume is not established as available at the existing close-plus-one-minute
cutoff. Strict v2's regular-session price/calendar and availability contract cannot be
satisfied merely by relabeling these bars. A new timing/source convention, qualified
raw/corporate-action/benchmark accounting, warm-up and owner-reviewed registration would
be required. No such convention is approved or implemented here.

## Admission gates and owner decision matrix

The following **seven gate groups** remain open; they are evidence requirements, not
scores. G1: complete economic distribution fields/classification. G2: complete cash and
structural action inventory. G3: permanent identity/history and universe limitations.
G4: execution/aggregation convention compatible with the actual source. G5: causal
availability/revision evidence or an explicitly reviewed restricted interpretation.
G6: retention/publication rights within entitlements. G7: approved feasible temporal
design, warm-up, contamination audit and credible news evidence or a neutral-only limit.
Public derived-result rights do not prevent already-authorized private local diagnostics,
but do block an unrestricted public empirical handoff.

| Owner option; no scope selected here | Quantified benefit | Unmet gates and limitation | Smallest next step |
| --- | --- | --- | --- |
| **A: propose SPY-only/shorter study** | SPY has 8/8 exact date/amount matches; three currency proofs. A 2024-ex-date subset has four events, one still currency-unresolved. Removing QQQ removes eight representation questions, one date conflict and its reorganization concern. | All seven groups remain open. Three resolved events do not approve a shorter window; such a window also needs warm-up/boundary actions. One asset/year cannot support the original multiyear robustness or untouched-holdout claims. | Owner reviews a versioned source/timing/universe/date/warm-up proposal and missing SPY evidence before any study. No silent truncation or exclusion. |
| **B: evaluate a different appropriately licensed source** | Could address source-wide G1–G6 rather than design around this feed. No alternative is currently verified or acquired. | Require raw session definitions, exact actions/payment currency, structural coverage, identity history, revisions/availability and storage/retention/derived-publication rights. G7 still requires registration review. No coverage or zero-cost entitlement assumed. | Authorize a bounded documentation/licensing feasibility comparison, with no subscription, acquisition or R4-C execution. |
| **C: deliver reproducible software; empirical research pending** | Retains accepted R1–R4-B engineering, public synthetic examples and R4-B.2 tests; needs zero further market acquisition. | All seven historical gate groups remain pending; historical-study completion and empirical AI/performance claims remain unavailable. | Owner explicitly chooses framework-only presentation and labels the empirical completion gate open. |

**Recommended next action:** a bounded source-feasibility review under option B, against
these seven gate groups. This recommends evidence gathering, not a changed study scope
or a provider purchase. The original proposed design/OOS/final periods remain unchanged.

Support #397685 remains owner-reported authorization for personal noncommercial IEX
research and local storage within Basic entitlements. It does not resolve historical SIP,
post-account retention or public derived-chart/statistics rights. Raw/adjusted observations,
workbooks, sensitive receipts and empirical diagnostics remain private. All broader
2012-onward coverage, 2016–2019 action completeness and historical AI/news requirements
remain unsupported. No dataset is accepted and R4-C has not begun.

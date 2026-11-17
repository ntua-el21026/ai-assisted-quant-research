# R4-B.1 historical dataset qualification — 2026-11-17

**Dataset-to-R4-C: BLOCKED.** The full registered 2024–2025 raw IEX pilot was acquired
and its bar coverage passed. Applicable corporate-action qualification failed; the
larger 2020–2025 acquisition was not attempted. No historical strategy, holdout
performance, parameter selection, benchmark return or AI-uplift experiment ran.

## Original blocker and independent event evidence

The original R4-B manifest remains
`8f9ed18dd45602979ca7ff1b35b6de332908ff75f26b325130ddffe0fba1335e`;
its unchanged qualification remains
`0a64c25cc9e9b179715da631ceb381e2beac01ef4f62b2f2e1fd9440f93b3621`.
Its two cash events are 2023-effective observations returned by a 2024 process-date
query. The [Alpaca reference](https://docs.alpaca.markets/us/reference/corporateactions-1)
documents process-date filtering and does not guarantee corporate-action creation time.
Neither pagination nor an ex-date establishes historical availability/completeness.

A newly retained [official 2023 Invesco workbook](https://www.invesco.com/content/dam/invesco/us/en/documents/tax-document/ce-ici-primary-and-secondary-distribution-file-and-nra-file-ivz-etf-2023.xlsx)
has five QQQ event rows and one unique match to the flagged event. Security identifier,
symbol, ex-date, record date and exact amount agree. The issuer characterizes the
entire amount as income/ordinary dividends; capital-gain and return-of-capital fields
are zero. **The payable date disagrees with the provider.** Both reported payment dates
fall after 2024-01-01. The provider's special flag is preserved; ordinary tax character
does not prove regular/special distribution classification or resolve its semantics.
Historical QQQ payout currency and declaration availability remain unverified.

Retrieval was one unauthenticated GET, 345,473 bytes, 2026-11-17 11:19:22 UTC.
Workbook SHA-256:
`293872a9b42934d33852b5ae362dc2222d6a2f550c644d3f5f63082986f63ce1`.
Private source/extraction/comparison package:
`datasets/private/r4b/issuer-semantics-20261117-v1/`; index SHA
`ab918d905bb11506800d996ec5aadd511faf55a4499597976df5df3cd0a1f92a`.
Exact economic fields remain in `comparison/flagged-event-v1.json`, hash
`7b6c2517143bd3a461d9efd20556514b6b2a79e8ca620dd90f559c177b320ea1`.
No proprietary event rows/rates or sensitive receipts are published here.

## What was resolved

The explicit fresh-flat/raw pilot context excludes both prior-ex-date cash events
because opening positions, orders and receivables are empty and starting cash is
independent of past distributions. Eligibility is zero even when payment occurs later.
This is not a conclusion that the source payment date is correct. Carry-in, inherited
receivables, earlier history and adjusted inputs do not receive that exclusion.
Every source row, flag and source/record hash remains traceable.

The same event is economically relevant inside 2020–2025 and remains unsupported or
unverified there. No special-accounting extension or canonical payment-date override
was justified. Accepted exact Decimal accounting, ex-date receivables, payment cash,
split interactions and replay rules remain unchanged. No adjusted execution price or
cash double counting was introduced.

## New bounded acquisition

The [new plan](../../experiments/configs/r4b1_acquisition.json) and
[scope/evidence policy](../../experiments/configs/r4b1_requalification.json) were fixed
before new observations. They preserve the old primary symbols, feed, basis and
windows; old preflight pages are reused. No diagnostic or larger acquisition was added
after inspecting results. Request plan SHA:
`5c4744d6dd0dd73a6ff590bd6727b05cc9ea7ad14c11a03a015007866e816a88`;
policy SHA:
`a36004e4f37496d4480d15cca3dc470d84358f6079ef090d01cf406d4c717641`.

| Source/query | Observed result | Qualification |
| --- | --- | --- |
| Original IEX/raw preflight, SPY/QQQ January 6–10, 2025 | Reused original page; no GET | 8/8 bars; original times/hashes preserved |
| Original all-type action preflight, 2024-Q1 process dates | Reused original page; no GET | 2 pilot-outside cash events under the explicit zero-entitlement contract |
| IEX/raw daily SPY/QQQ, 2024-01-01–2025-12-31 | 2 HTTP-200 pages | **1,004/1,004** expected symbol-session rows; no missing, duplicate or invalid rows |
| All-type SPY/QQQ actions, inclusive process dates 2024-01-01–2026-11-16, `data_quality=all` | 1 HTTP-200 terminal page; 24 cash rows | 16 applicable, 2 prior-ex outside, 6 future-ex outside; all 24 lack currency; applicable normalization fails |
| Conditional 2020–2025 candidate | NOT REQUESTED | Pilot scientific/action gates and known relevant event remain blocked |

New authenticated consumption: **3 GETs / 115,947 received bytes**, all HTTP 200,
no retries. Original consumption remains charged: aggregate **5 requests / 117,404 bytes**.
The authority records no outstanding request. Acquisition exited **1** with terminal
`invalid_corporate_action`, retained the failed candidate, and stopped before larger
requests. No SIP, account, broker, payment or subscription endpoint was called.

Each symbol has 502 observed sessions, covering the scheduled January 2, 2024 through
December 31, 2025 window. Calendar/DST/closure/early-close labels validate against the
versioned 2020–2025 official schedule; these are session-coverage checks, not evidence
that provider OHLCV aggregates uniformly represent regular trading hours. Raw source
decimals are retained; no tradable observation was forward filled.

New private manifest:
`datasets/private/r4b/session-r4b1-20261117-v1/frozen/evidence/manifest.json`, SHA
`44d4de820bbad745cc14b2cad11f6adf34b412b58d33f7b9aefa886a39df444f`.
Freeze: **2026-11-17 11:56:04.824475 UTC**. It inventories 22 files. Its envelope's
2020–2025 span identifies the registered conditional candidate; actual completed
query roles establish the acquired 2024–2025 pilot. It does not contain full candidate
coverage and is not an admitted market-snapshot/v2 input.

## Applicable actions and independent comparison

The relevant 16 events have no established currency in the raw response. The new
scope report emits `applicable_cash_currency_unverified`; values are not filled from
bar quote currency or domestic status. The normalized action file is omitted on failure,
not written as an invented empty inventory. Eight excluded observations remain source
evidence; exclusion never claims those source fields are verified.

The unchanged R4-B issuer inputs provide 16 2024–2025 ex-date keys. A separate private
raw-field diagnostic observes all 16 keys, with no duplicate key: 16 ex-date matches,
15 payable-date matches/one disagreement, and eight raw rate matches/eight differences.
This is not a normalized reconciliation PASS. Field/rate interpretation is retained
with source precision qualifications; source differences are not automatically called
provider errors, rounded away or overwritten. Normalization-blocked source records are
not falsely counted as absent provider observations.

A new precision audit locates all eight rate differences in QQQ's correct total-cash
column. Its explicit Excel format has eight decimal places; each raw XML value matches
the preserved extraction, and all eight source/provider pairs represent the **same
binary64 value**. Component selection and foreign tax do not explain the differences.
This supports numeric serialization precision as their cause; it does not establish
different economic payouts. Authoritative exact decimal intent remains unverified.
No acceptance tolerance, amount overwrite or source correction was applied. The
payment-date discrepancy remains independent of this representation issue.

Precision evidence is frozen under
`datasets/private/r4b/rate-precision-diagnostic-r4b1-20261117-v1/`; index SHA
`c8f178c251f8246d0ae49e0f78a07f774c982e43c811f935c9192023b5845981`.
Its summary SHA is
`4c225000aaa93a1688bc1996e203242264949fb5042a423fbf9460ddf089d2ec`.
Both diagnostic operators ran offline with zero new network requests.

The private diagnostic is
`datasets/private/r4b/raw-issuer-diagnostic-r4b1-20261117-v1/`; index SHA
`14c77e7e5dc0d2dc9c4a67b3ca42b72888f6ffe6b86b19d4a2be04a317d7b951`.
Source inventory only establishes observed cash categories. It does not prove that all
relevant structural events were returned. QQQ's previously documented December 2025
fund reorganization remains an identity/action-completeness concern, not an event to
silently omit because no corresponding provider category appeared.

## Currency and aggregation evidence

The [SEC-filed SPY 2024 prospectus](https://www.sec.gov/Archives/edgar/data/884394/000119312524017688/d315180d497.htm)
explicitly denominates Trustee distributions in U.S. dollars (S-11). The
[Australian issuer page](https://www.ssga.com/au/en_gb/intermediary/etfs/state-street-spdr-sp-500-etf-spy)
separates underlying USD distributions from AUD conversion for CDI holders; those
payment currencies must not be interchanged. SPY has useful independent USD evidence.
The [current QQQ prospectus](https://www.invesco.com/content/dam/invesco/hk/en/pdf/prospectus/Invesco_QQQ_prospectus_EN.pdf)
states USD policy from December 2025 with a later 2026 supplement; that is not evidence
to backdate the policy across 2024/early-2025. No provider currency field was overridden.

The three retained documents total **2,123,995 response-body bytes** from three explicit
download invocations; redirect hops were not individually logged. They remain private
under `datasets/private/r4b/r4b1-currency-evidence-20261117/`. Receipt SHA:
`89ff4fd640440857b864ffb7a65eb761a5f7cc08162444981ebbad77fd98829a`.

| Currency source retained 2026-11-17 | Bytes | Document SHA-256 |
| --- | --- | --- |
| SEC SPY prospectus | 1,154,039 | `e6b7acb1c3805621e83689f83e236c954f940a47a1279cc280567d971700122f` |
| State Street AU SPY page | 283,801 | `88916c66e7abab6fc95295d77d768bdf3eccd5df2ed3fdbba4a8dbe6668ca9cd` |
| Current QQQ prospectus | 686,155 | `d081d97895cc5546bc6c8172299c68ff38a16609532d683cc6bc7e8644fc67d7` |

[Alpaca's aggregation rules](https://docs.alpaca.markets/us/docs/market-data-faq#how-are-bars-aggregated)
group daily observations by New York calendar day and use field-specific sale conditions.
Extended-hours/odd-lot trades can affect volume without daily OHLC; official auction
conditions are not equivalent to the first eligible IEX trade. The daily open is not a
verified 09:30/primary-auction execution price. No regular-session selector exists in
the [daily-bar endpoint](https://docs.alpaca.markets/us/reference/stockbars).
Late-trade updates/corrections are documented in the
[streaming reference](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data#updated-bars-updatedbars).
**Inference:** full-day volume cannot be treated as known at regular close plus one
minute without additional qualification. Current rules do not establish unchanged
historical semantics or a frozen daily revision vintage throughout the pilot.

## Rights, time, identity and next step

Owner-reported Support #397685 and official Basic/paper-only documentation authorize
personal noncommercial IEX research and local storage within entitlements. Historical
SIP, public derived-result publication and post-account retention remain unresolved.
No successful response is treated as a rights grant. All actual observations,
independent materials and empirical diagnostics remain private.

Actual acquisition time, event/ex-date, process date, payment time and correction
observation remain distinct. No timestamp is backdated. Logical ticker mappings are
uncertain rather than proven permanent historical identities. Complete cash pagination
does not establish full action inventory, survivorship-free membership or point-in-time
history. Observed contemporary corrected data do not establish historical first publication.

The smallest legitimate next step is an evidence-backed payment/amount/currency
resolution and an explicit provider aggregation/availability contract, followed by a
new immutable action-resolution/admission attempt. A separately reviewed SPY-only or
alternative-source proposal may be considered; this checkpoint does not remove QQQ,
shorten the data, alter registered dates, redefine the holdout or start R4-C. The old
2012–2018 proposal and later segments remain unchanged and unsupported where data are
unavailable. V2 admission and historical strategy execution remain blocked.

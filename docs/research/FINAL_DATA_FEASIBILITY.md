# Final data feasibility — 2026-11-17

**Data decision: NO-GO. Empirical work: STOP. Recommended final closure: B,
engineering framework delivered with empirical validation pending.** The existing
authorized IEX pilot remains inadmissible. None of the three permitted alternatives
has both established authorization and sufficiently qualified evidence for this study.
Public documentation can establish conditional license permissions, including the
EODHD private-retention permissions corrected below. It does not establish the owner's
applicable eligibility, actual account entitlement or authorization for new acquisition.

This finite review closes the source-feasibility decision. It authorizes no additional
acquisition, subscription, source integration, R4-B continuation or R4-C experiment.
The framework's executable engineering evidence and its incomplete empirical research
status must be reported separately. This final-closure outcome B is distinct from the
earlier R4-B.2 option B, which proposed the documentation comparison completed here.

## Governing requirements and review boundary

The [v0.7 specification](../app/AI_Assisted_Quant_Research_SPEC_v0.7.md),
[research protocol](RESEARCH_PROTOCOL.md) and
[R4-B.2 qualification](R4B2_DATA_QUALIFICATION.md) govern this assessment. The required
study retains SPY as market proxy, at least one distinct tradable asset from the existing
universe, a multiyear interval with at least 200 sessions of feature warm-up, positive
relative strength and the existing risk thresholds. SPY alone has zero relative
strength against itself and cannot satisfy that trading requirement. Shortening the
window or removing QQQ does not resolve the source-wide admission gates.

Raw execution prices, research adjustments, economic actions, calendars and information
availability must remain explicit. A historical daily bar is not evidence of an
attainable auction fill. Originally proposed research splits are not established as
untouched holdouts. A restricted interpretation or revised temporal design would need
an explicit versioned amendment after a genuine data GO; none is designed or adopted
here. Negative-only AI and neutral fallback remain unchanged, and no historical
AI-uplift claim becomes available through this review.

Exactly three alternatives were considered: **Tiingo, EODHD and Massive**. Official
public documentation and terms were checked on **November 17, 2026** using Firecrawl
search and document retrieval. Documentation capabilities are distinguished below
from executed data qualification. No observation from any alternative was acquired or
tested, and no alternative account, entitlement or credential was inspected.

## Existing authorized pilot

The frozen SPY/QQQ 2024–2025 IEX pilot has manifest SHA-256
`44d4de820bbad745cc14b2cad11f6adf34b412b58d33f7b9aefa886a39df444f`.
The preserved [R4-B.1 qualification](R4B1_DATA_QUALIFICATION.md) and
[R4-B.2 audit](R4B2_DATA_QUALIFICATION.md) establish:

- **Bars:** 1,004/1,004 expected observations, 502 sessions per symbol, with the
  implemented calendar and OHLCV checks passing. This covers two years, rather than
  the unacquired 2020–2025 candidate or the original proposed research history.
- **Actions:** 24 retained cash rows; 16 applicable and eight outside the declared
  fresh-flat/raw scope. No applicable event is excluded. All 16 raw payout currencies
  are absent; independent bounded evidence resolves three SPY fields, leaving 13
  unresolved. There is one QQQ payable-date conflict. Eight SPY amounts match exactly;
  the eight QQQ decimal representations differ while denoting the same binary64
  values. Exact source decimal intent remains unverified; this is not an established
  economic-rate error and supplies no tolerance or overwrite rule. Independent
  regular/special classification remains unresolved for all 16 events.
- **Execution and causality:** venue-limited daily data does not certify
  regular-session OHLC, auction execution or consolidated-market volume. A symbol
  mapping `asof` parameter does not establish historical publication/revision vintages.
  A retrospective IEX proxy would require a separately approved interpretation; it
  cannot enter strict v2 by relabeling the fields or availability timestamp.
- **Rights and identity:** owner-reported Support #397685 covers personal
  noncommercial IEX research/local storage within the reported Basic entitlement.
  Post-account retention, public empirical derived-result rights and permanent
  historical security/universe identity remain unresolved. The authorization does
  not extend to SIP or another vendor.

All seven existing gate groups remain open: complete economic fields/classification;
complete cash and structural-action inventory; permanent identity/history/universe;
execution and aggregation semantics; causal availability/vintages; retention and
publication rights; and a feasible registered temporal design with warm-up,
contamination assessment and credible news evidence or an explicit neutral-only limit.
Passing bar coverage is therefore insufficient for an empirical GO. The preserved
provider total remains **five authenticated IEX requests / 117,404 body bytes**. This
review makes no new provider request.

## A–J comparison

The labels below define the ten checks used in this report. A documented field or
advertised history is a capability, not a guarantee that every required record is
complete, correct, historically available or licensed for the intended use.

| Check | Tiingo | EODHD | Massive |
| --- | --- | --- | --- |
| **A — Coverage, history and universe** | EOD pricing advertises 30+ years and US stock/fund coverage. Actual SPY/asset/warm-up coverage is untested. [T1][t1], [T4][t4] | Paid EOD pricing advertises 30+ years; free history is one year. A documented symbol/rename/delisting surface does not itself certify the required universe. [E1][e1], [E4][e4] | Stocks Basic advertises two years, Starter five, Developer ten, Advanced 20+; lookback depends on the plan and review date. Actual required coverage is untested. [M5][m5] |
| **B — Raw and adjusted bars** | EOD supplies raw and split/dividend-adjusted OHLCV, with cash-dividend and split fields. Adjusted prices cannot substitute for raw simulated fills. [T1][t1] | OHLC is raw; `adjusted_close` includes splits/dividends, while volume is already split-adjusted. This mixed basis needs explicit treatment and verification. [E1][e1] | Aggregates default to split adjustment; `adjusted=false` requests unadjusted bars. That switch does not make them dividend-adjusted total-return bars. [M1][m1] |
| **C — Cash and structural actions** | Separate distribution/split APIs document dates, amounts, frequency and active/cancelled splits. Some dividend dates can be null. Detailed dividend history is advertised from 2023; complete earlier fields and broader structural inventory are unproven. [T2][t2], [T3][t3], [T6][t6] | JSON documents ex/declaration/record/payment dates, payment currency and historical unadjusted amounts; dates/period may be null. Split ratios can also encode reorganization/spin-off adjustments. This is not a complete economic structural-event ledger. [E2][e2] | Dividend schema documents payment currency, dates and explicit recurrence classification, including unknown. Split schema distinguishes forward/reverse splits and stock dividends. Complete structural actions and event-level accuracy remain untested. [M2][m2], [M3][m3] |
| **D — Currency and security identity** | Reviewed distribution schema does not establish payout currency or permanent historical identity. Symbology limits delisted support to unrecycled tickers and describes further permanent-ticker support as expansion work. [T2][t2], [T5][t5] | Dividend payout currency and separate listing currency/identifiers are documented. Fundamentals expose FIGI/ISIN and update fields; these are not proof of complete effective-dated identity or knowledge-time history. [E2][e2], [E3][e3] | Dividend payment currency and dated ticker metadata with CIK/FIGIs/listing currency are documented. Older metadata fields may be empty. Effective-date queries do not alone prove historical first-publication vintages. [M2][m2], [M4][m4] |
| **E — Session, calendar and execution** | EOD availability is documented, but reviewed pages do not establish the exact regular-session aggregation, auction/open convention and calendar contract required by strict v2. [T1][t1] | Daily trading-date OHLC is documented; reviewed pages do not fully specify eligible-sale/session boundaries or establish auction/open attainability. [E1][e1] | ET aggregates use qualifying trades and can span premarket, regular and after-hours periods. No eligible trade means no bar. Session filtering/aggregation and the execution/calendar contract would need explicit qualification. [M1][m1] |
| **F — Availability, corrections and revisions** | Most US EOD data is available at 17:30 in the documentation's EST wording; corrections update through 20:00. No historical vintage selector is established. An EOD close-plus-one-minute cutoff is unsupported by this evidence. [T1][t1] | Major US updates are documented within 15 minutes after close; other markets can be later. Adjusted closes are recomputed. Reviewed endpoints do not establish historical availability/revision snapshots. [E1][e1] | Dated reference metadata is useful, but reviewed aggregate/action schemas do not establish immutable as-known-at vintages or historical delivery cutoffs. An event date is not an observation timestamp. [M1][m1], [M2][m2], [M4][m4] |
| **G — Durable storage and retention** | Current §1.6 forbids durable source/derived storage on Starter/trial. Eligible paid source data must be deleted after the paid entitlement ends; retention exceptions are unavailable to Starter/Power. This conflicts with an unconditionally permanent frozen dataset. [T0][t0] | Confirmed conditional permission: qualifying Non-Professional users may store data privately for noncommercial use. Active-subscription downloads and provenance may be kept after cancellation/downgrade; private derived outputs may be retained indefinitely. This does not establish the owner's eligibility or entitlement. [E6][e6], [E7][e7], [E8][e8] | Current §8 limits use to licensed information and requires deletion after the relevant license ends, generally within 30 days. Downgrade leaves only the new entitlement's permitted information. Per-request licensing is not perpetual. [M6][m6] |
| **H — Public derived results and redistribution** | §1.6 conditionally permits qualifying non-substitutive, non-reconstructive derived products outside Starter/trial restrictions; §7.3 separately limits raw redistribution. A particular public chart/table and source-specific rights still require assessment. [T0][t0] | Personal-use permission restricts redistribution and public display of original/repackaged data. Private research outputs are allowed; public derived statistics/charts require separate licensing assessment and are not automatically permitted by aggregation or non-reconstructibility. Project-specific public rights remain unresolved. [E6][e6], [E7][e7], [E8][e8] | Personal retained analyses that neither contain nor reconstruct source information are distinguished from publication/sharing. Reviewed personal terms do not establish permission for this project's public empirical report; source-specific restrictions also apply. [M6][m6] |
| **I — Authorized access and cost** | No alternative access authorization is established. Advertised individual Power is $30/month; commercial internal use is $50/month. Free access does not permit frozen research storage under current terms. No plan is purchased. [T0][t0], [T4][t4] | No authorized account/plan is established. EOD is advertised at $19.99/month; ALL-IN-ONE, including the separate fundamentals surface, is $99.99/month. Free one-year history cannot satisfy this multiyear design. [E4][e4] | No authorized account/classification is established. Advertised monthly Stocks tiers are $0/$29/$79/$199. A cheaper tier's shorter rolling history does not automatically cover the proposed dates plus warm-up. [M5][m5], [M6][m6] |
| **J — Existing implementation and remaining work** | Repository has an adjusted-bar provider for the historical paper-validation path, not a qualified v2 action/raw/history pipeline. Reuse would still require scoped normalization, preservation and admission evidence. No integration is implemented. | No qualifying adapter/retained dataset is established by this review. Mixed volume basis, action fields and nullable dates would require dedicated normalization/provenance tests after authorization. No integration is implemented. | Richer schemas reduce some field uncertainty but do not supply a verified adapter, source-wide qualification or rights. Session and dated-identity semantics would need explicit tests after authorization. No integration is implemented. |

The current Tiingo terms are dated **November 5, 2026**; Massive's market-data terms
are dated **November 3, 2026**. Their current provisions must not be silently applied
as evidence of an earlier account agreement. Prices above are advertised public plan
prices as checked, not quotes, purchases, total implementation costs or proof of
entitlement. Source-specific supplements and tax/plan eligibility can affect access.

For Tiingo, read-only source inspection was restricted to module/API/configuration
names and response-field mappings: `TiingoEodProvider.adjusted_daily_bars`,
`normalize_tiingo_eod_records`, `AdjustedDailyBar`, the `adjOpen`/`adjHigh`/`adjLow`/
`adjClose`/`adjVolume` fields and `tiingo_eod_client_from_env` usage. No `.env` file,
credential value, account plan or unrelated credential was opened. An existing
credential or adapter would not extend the owner's Alpaca-only authorization.

## Decision and closure

**No candidate is demonstrated to pass all A–J checks, and no alternative has established
authorization for acquisition.** Tiingo offers relevant EOD/action surfaces but has material storage,
identity and historical-field limitations. EODHD offers relevant raw/action fields but
its confirmed conditional private-storage and post-cancellation retention permissions
do not establish this owner's eligibility, account entitlement or acquisition
authorization. Public derived-result licensing, historical availability and exact
contract compatibility remain unestablished. Massive offers the clearest reviewed currency/classification and
dated-identity fields, but those capabilities do not establish actual record quality,
the required source/timing contract, retention/publication rights or authorized access.
These findings are not a quality ranking or proof that any provider cannot support a
differently licensed study.

The permitted next action is **engineering closure with empirical validation pending**.
Preserve the frozen pilot and its failed admission, deliver reproducible offline and
synthetic demonstrations, and label historical strategy, benchmark, AI-uplift and
generalization findings unavailable. Do not acquire another dataset, build another
adapter, change the execution contract, weaken v2 admission, remove positive relative
strength, alter risk thresholds, truncate the study or relabel an exposed period as an
untouched holdout. There is no further source investigation or owner scope question in
this closure task. No R4-C or additional R4-B phase is initiated.

## Original source inventory and executed limits

All links below were checked through official-domain documentation/search on
**2026-11-17**. They are public capability/legal evidence, not archived market
observations or immutable licensed evidence snapshots. Connector cache timestamps can
precede the check date; no native document checksum is claimed.

| ID | Official source | Evidence access |
| --- | --- | --- |
| T0 | [Tiingo terms of use][t0] | Official search text plus final official-page retrieval; §1.6 independently checked |
| T1 | [Tiingo EOD documentation][t1] | Document target, HTTP 200 |
| T2 | [Tiingo dividend documentation][t2] | Document target, HTTP 200 |
| T3 | [Tiingo split documentation][t3] | Document target, HTTP 200 |
| T4 | [Tiingo pricing][t4] | Document target, HTTP 200 |
| T5 | [Tiingo symbology][t5] | Document target, HTTP 200 |
| T6 | [Tiingo dividend product][t6] | Official search excerpt; advertised detail-history limitation |
| E0 | [EODHD official overview][e0] | Document target, HTTP 200; used to locate official documentation |
| E1 | [EODHD historical EOD documentation][e1] | Document target, HTTP 200 |
| E2 | [EODHD splits/dividends documentation][e2] | Document target, HTTP 200 |
| E3 | [EODHD fundamentals documentation][e3] | Document target, HTTP 200; field descriptions only |
| E4 | [EODHD pricing][e4] | Document target, HTTP 200 |
| E5 | [Attempted EODHD legal path][e5] | Document target, HTTP 404; no terms grant inferred |
| M1 | [Massive custom aggregates][m1] | Document target, HTTP 200 |
| M2 | [Massive dividends][m2] | Document target, HTTP 200 |
| M3 | [Massive splits][m3] | Document target, HTTP 200 |
| M4 | [Massive ticker overview][m4] | Document target, HTTP 200 |
| M5 | [Massive pricing][m5] | Document target, HTTP 200 |
| M6 | [Massive market-data terms][m6] | Document target, HTTP 200; §§1/4/5/8 reviewed |

The bound was three alternatives, at most six targeted searches and at most 18
official document targets. Executed operations were **six searches, 18 document
targets and six search-quality feedback submissions**. The first 17 targets used
Firecrawl: 16 returned HTTP 200 and one returned HTTP 404 according to connector
metadata. The last permitted target independently retrieved Tiingo's official terms
through the web reader and confirmed §1.6; it was not a market-data request. The failed
EODHD legal-path lookup was not retried. Its terms search returned no results; the
separately authorized correction below resolves that review's private-retention
permission gap using three different official URLs. The original inventory contains **19 distinct
cited source URLs**: 18 document targets and the search-only Tiingo dividend product.

Tools used were `firecrawl_search`, `firecrawl_scrape`,
`firecrawl_search_feedback` and `web.run` (one official-page open), plus local read-only
Git/text/AST inspection and writing
this report. The document targets are counted individually even when batched in one
tool invocation. Connector-internal HTTP attempts and response-body byte counts are
opaque; no hard native byte ceiling or independently verified transport accounting is
claimed for this documentation review. **There were zero authenticated provider requests,
zero provider-data endpoint requests, zero native downloads, zero vendor-observation
captures, zero signups/purchases and zero credential inspections.** Public example
observations embedded in documentation were not used or retained as a dataset and
are not reproduced here. No code or test change, numerical experiment or empirical
qualification run is part of this report.

## EODHD licensing correction — 2026-11-17

The initial review used the wrong legal path, [E5][e5], which returned HTTP 404.
That failed lookup did not establish an absence of EODHD storage or retention
permission. The user subsequently supplied three exact official URLs and explicitly
authorized this bounded documentation correction. All three were checked through
`firecrawl_scrape` on **November 17, 2026, at approximately 14:13 UTC**, with the
following observed results:

| ID | Corrective official source | Observed tool result |
| --- | --- | --- |
| E6 | [EODHD Terms and Conditions][e6] | HTTP 200; title: Terms and Conditions; connector cache timestamp 2026-11-17 13:06:23 UTC |
| E7 | [EODHD storage and cancellation help][e7] | HTTP 200; title: Cancel a Plan, Keep Your Data, Refunds; cache timestamp 2026-11-16 02:59:09 UTC |
| E8 | [EODHD personal-use help][e8] | HTTP 200; title: What a Personal Plan Allows; cache timestamp 2026-11-16 13:03:31 UTC |

The governing terms permit qualifying Non-Professional users acting personally for
their own investment activities to store and analyze data privately for noncommercial
purposes. Use on behalf of another person, a business or an organization is outside
that personal scope. The help pages explicitly interpret those terms as permitting
local raw/normalized data, backups and audit/provenance records, including retention
of active-subscription downloads after cancellation or downgrade. Private research
outputs may be kept indefinitely, whether or not their source values are
reconstructible, provided neither the data nor the outputs are shared. New data or
revisions remain subject to an applicable active entitlement. [E6][e6], [E7][e7], [E8][e8]

These permissions do not extend automatically to public portfolio results. Personal
plans restrict raw/repackaged redistribution and public data display. The personal-use
help page separately directs publication of derived rankings, signals and backtest
statistics to licensing assessment using the actual outputs and audience; transforming
or aggregating data is not an automatic publication grant. The help pages identify
the terms as governing personal plans and say a separate permission letter is generally
unnecessary for the described qualifying personal uses. This report therefore does
not require a special letter for already-covered private use, infer a public-derived
license or determine the owner's personal/professional status. [E6][e6], [E7][e7], [E8][e8]

This correction changes G, H and the EODHD decision explanation. It removes a blanket
unresolved-private-retention finding. **The empirical NO-GO and STOP remain unchanged:**
the owner's applicable eligibility, actual entitlement and new-acquisition
authorization were not established or inspected; public-result licensing and source
qualification remain unresolved. No provider observation, account or credential was
accessed, and no study, implementation, purchase or additional investigation is
initiated by the correction.

The corrective authorization covers **three page targets, all HTTP 200, zero searches
and zero data/API acquisition requests**. These are additional to the preserved
original **18-target / 19-source-URL** review, rather than a reset or retrospective
expansion of that review's budget. Across the two authorizations there are **21
document targets and 22 distinct cited source URLs**; the original six searches and
six feedback submissions are unchanged. The original E5 HTTP 404 remains recorded at
its different URL. No native downloads, account access, credential inspection or
independently verified connector byte accounting is claimed.

[t0]: https://app.tiingo.com/tos/
[t1]: https://www.tiingo.com/documentation/end-of-day
[t2]: https://www.tiingo.com/documentation/corporate-actions/dividends
[t3]: https://www.tiingo.com/documentation/corporate-actions/splits
[t4]: https://www.tiingo.com/about/pricing
[t5]: https://www.tiingo.com/documentation/appendix/symbology
[t6]: https://www.tiingo.com/products/corporate-actions/stock-etf-mutual-fund-dividend-api
[e0]: https://eodhd.com/
[e1]: https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
[e2]: https://eodhd.com/financial-apis/api-splits-dividends
[e3]: https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds
[e4]: https://eodhd.com/pricing
[e5]: https://eodhd.com/terms-conditions
[e6]: https://eodhd.com/financial-apis/terms-conditions
[e7]: https://eodhd.com/help/storage
[e8]: https://eodhd.com/help/personal-use
[m1]: https://massive.com/docs/rest/stocks/aggregates/custom-bars
[m2]: https://massive.com/docs/rest/stocks/corporate-actions/dividends
[m3]: https://massive.com/docs/rest/stocks/corporate-actions/splits
[m4]: https://massive.com/docs/rest/stocks/tickers/ticker-overview
[m5]: https://massive.com/pricing
[m6]: https://massive.com/legal/market-data-terms-of-service

# Quantitative Trading Research Protocol

- **Governing specification:** [Research Framework v0.7](../app/AI_Assisted_Quant_Research_SPEC_v0.7.md)
- **Status:** R1–R4-B engineering reviewed; R4-B.2 targeted correction verified, acceptance pending. Pilot bars pass internal quality; historical admission/studies remain blocked.

## 1. Scientific objective

Evaluate the robustness of a deterministic end-of-day US equity/ETF strategy and the incremental effect of a bounded, negative-only AI/news risk overlay, while separately demonstrating correctness and recovery in local simulated workflows.

These are engineering experiments, not investment recommendations or evidence of expected future profits. The hypotheses must be registered in a versioned experiment configuration **before** final evaluation results are examined.

| ID | Question | Null/baseline | Proposed comparison |
| --- | --- | --- | --- |
| RQ1 | How robust are deterministic filters across regimes and costs? | Unfiltered/ablated deterministic strategy and transparent SPY-based benchmarks | Full configured strategy over temporal OOS windows and cost stresses |
| RQ2 | What changes when adverse-news AI evidence is considered? | Exactly the same deterministic decisions with AI forced neutral | Frozen, as-of-valid negative-only overlay; assess both return and risk/exposure effects |
| RQ3 | Can a simulated research workflow recover correct state after faults? | Independently computed reference ledger and expected workflow result | Failure/retry/replay versus uninterrupted local run; compare state and side-effect counts |

Do not claim causal benefit, statistical significance or generalization without an analysis that supports it. For RQ2, a neutral or unusable historical-news dataset is a limitation, not grounds to fabricate outputs.

## 2. Data and provenance

### Market data

- R4-B uses explicitly selected **Basic/IEX**, supported by official paper-only documentation and owner-reported Support #397685 for personal noncommercial research and local storage. Historical SIP remains conditional on separate written entitlement evidence; no SIP observations were acquired in R4-B. IEX prices, volume and extrema are venue-limited, not consolidated-market execution evidence. Persistent/post-account retention and public derived-result rights remain unresolved.
- Public example: small synthetic, hand-audited OHLCV fixtures committed under `tests/fixtures/` or a clearly labeled equivalent, with no proprietary redistribution.
- One frozen manifest per dataset: source and license, retrieval/freeze UTC timestamp, date coverage, symbol universe, raw/adjusted basis, corporate actions, timezone, calendar, schema version, per-file SHA-256, normalization version, missing-data exclusions and survivorship caveat.
- Validate unique `(symbol, session)` keys, sorted sessions, nonnegative volume, finite valid OHLC, consistent fields and adequate feature warm-up; reject malformed data or produce explicit exclusion records according to the versioned policy.
- Do not forward-fill missing tradable prices into order execution. Market closures, corporate actions and delisted/absent symbols must be documented rather than hidden.

R4-A provides an explicit v2 contract and isolated action/benchmark accounting, documented
in [R4-A contracts](R4A_IMPLEMENTATION.md). Its synthetic checks do not approve historical
inputs, establish first-publication timestamps, change the proposed dates below, or
execute a strategy study. Payment-open reinvestment is a declared analytical assumption;
empirical comparison conventions must be registered and supported by the eventual data.

R4-A was independently accepted at `0dd0875` for synthetic engineering. The separately
authorized [R4-B qualification](R4B_DATA_QUALIFICATION.md) predeclares SPY/QQQ pilot
2024–2025 and conditional candidate 2020–2025 as **data-quality windows**, not new study
splits. Acquisition stopped during preflight on an unsupported special-dividend flag;
neither window was acquired. A `historical-candidate/v1` envelope retains negative evidence
without weakening strict v2 admission. Observed acquisition times are never backdated
to historical decision cutoffs. No protocol dates, strategy, benchmarks, parameters,
holdout status or final-period performance have been changed or inspected.

R4-B engineering was independently accepted at `a6d3a09`. Separately authorized
[R4-B.1](R4B1_DATA_QUALIFICATION.md) acquired the original 2024–2025 IEX pilot and
distinguished prior cash events under an explicit fresh-capital/no-inherited-entitlement,
raw-only data-quality context. That context does not authorize a new study period,
carry-in portfolio or shortened warm-up. Relevant actions remain unqualified; the
larger 2020–2025 candidate was not acquired. Provider daily OHLCV has field-specific
calendar-day aggregation and does not establish a 09:30/auction execution convention.
Historical availability, identities, retention and full action reconciliation remain
unresolved. No threshold, hypothesis, benchmark definition, research split or holdout
status changes here, and R4-C has not begun.

[R4-B.2 qualification](R4B2_DATA_QUALIFICATION.md) audits all 16 applicable pilot cash
events without new authenticated requests. A narrowly bounded independent policy
receipt resolves three SPY currencies; raw records, strict normalization and v2 admission
are unchanged. Thirteen currency fields and additional action/source/scientific gates
remain unresolved. IEX venue-price proxy timing, a narrower study or an alternative
source are owner-review options; none is registered or approved by this diagnostic work.
No proposed split, threshold, holdout status, benchmark or execution convention changes.

### AI/news evidence

- Frozen input articles need stable IDs/hashes, source, publication time, observed availability time, symbol relevance and legal redistribution status.
- Frozen structured outputs need model ID/version, prompt/template hash, schema version, invocation/cutoff time, validity outcome, adverse-event classification and neutral-fallback reason.
- Only information available at the simulated decision cutoff can affect that decision. Retroactive news labeling must not leak future outcomes into decisions.
- If sharing full content is prohibited, provide source metadata, hashes and a license-safe illustrative dataset; report that exact third-party evidence may require licensed access.

## 3. Temporal splits and model-selection integrity

**Proposed initial split**, subject to actual historical coverage and an explicit contamination audit:

| Segment | Proposed dates | Permitted use |
| --- | --- | --- |
| Design | 2012–2018 | Hypotheses, baseline parameters, engineering checks |
| Rolling OOS development | 2019–2023 | Anchored expanding-window validation and predeclared tuning/selection |
| Final evaluation | 2024 to dataset freeze | One final evaluation after all choices are frozen |

Because the earlier trading-bot project existed before v0.7, these dates **must not automatically be called untouched**. Audit earlier strategy work and reports for potential exposure to the 2024+ period. If there was prior exposure, label the segment *final evaluation with potential design contamination* or select a truly prospective future test; do not conceal it.

For every rolling fold record train end, evaluation start/end, warm-up period, parameter set, universe membership and data availability cutoff. Do not shuffle market dates or use future sessions to compute percentile ranks, earnings blackouts, liquidity screens or model features.

## 4. Decision and execution conventions

The baseline will be an EOD strategy. Completed daily bars for session `t` are available only **after** that session's close. Signals using those bars become eligible for execution at the **next valid session** under the configured entry convention. Same-bar closing-price fills are forbidden for such signals.

- Every order has decision date/time, earliest eligible fill session, action, symbol, quantity, reason and deterministic ID.
- Fill price derives from documented raw tradable prices (next-session open by default), spread/slippage and fees. If the required price is absent, reject or defer according to policy; never silently substitute a future close.
- Stops/targets use a conservative, explicit OHLC ordering policy. Overnight gaps through a stop must not be filled at an unattainable stop price by assumption.
- A fixed ordering of simultaneous orders and portfolio capacity rules prevents iteration-order dependence.
- Portfolio equity includes marked-to-market open positions; realized P&L, fees, cash and positions must reconcile. End-of-sample open positions remain identified as open rather than fabricated as closed trades.
- Long-only, unleveraged simulation is the primary study. Simulated shorting and scale-ins are optional, separately tested extensions.

## 5. Benchmarks and ablations

Primary comparisons, contingent on source coverage and consistent price/dividend basis:

1. SPY buy-and-hold total return.
2. Exposure-adjusted SPY comparator with a documented cash/benchmark convention.
3. Equal-weight approved-universe comparator, carrying survivorship warnings when historical membership is incomplete.
4. The full deterministic strategy with AI forced neutral.

Predeclared ablations should use identical data, costs and splits. Candidate factors from v0.6 include regime gate, relative strength, volume filter, fail-fast exit, time stop, breakout lookback and ATR stop/trailing coefficients. Distinguish *remove one factor* experiments from parameter selection; do not select a winning ablation after opening the final holdout and then re-label it as predeclared.

The AI overlay comparison must also report changed exposure and trade counts; improved drawdown from simply avoiding risk is not by itself evidence of superior prediction. Retain rejected-candidate and news-coverage counts.

The implemented execution bound uses the neutral portfolio as a causal opening-session
shadow: an AI entry must match a neutral executable entry's ID, symbol and session, with
no larger quantity. Reduced or vetoed entries cannot fund substitute trades. The session
exposure invariant is gross marked USD notional, also enforced against the paired control;
equity-normalized ratios are descriptive and use each portfolio's own equity denominator.
This distinction is necessary because avoiding a profitable trade can lower equity even
while reducing shares and USD exposure. Decisions remain timestamp-causal; the shadow is
consulted only during execution, after the corresponding session open becomes available.

## 6. Costs, scenarios and uncertainty

Use v0.6 cost assumptions as an initial **declared experimental grid**, not observed fill quality:

| Cost component | Baseline | Stress |
| --- | ---: | ---: |
| Fee proxy | 1 bp/side | Explicitly varied |
| Entry slippage | 10 bps | 25 bps |
| Routine exit slippage | 10 bps | Explicitly varied |
| Stop exit slippage | 20 bps | 40 bps |

Execution must distinguish modeled stop exits from routine exits. State if commission, borrow fees, dividend/cash interest, taxes and market impact are omitted; such omissions are limitations.

Use fixed-seed trade-sequence resampling, monthly block bootstrap and missed-fill/slippage stress where mathematically meaningful. The prior v0.6 proposal of 10,000 bootstrap draws is a default target for the **full** experiment, while unit tests should use small deterministic runs. Do not present resampled intervals as independent future-market guarantees.

## 7. Metric definitions and edge cases

Report units and annualization assumptions alongside each result.

- Return: total and annualized return when sample length permits; account for initial equity correctly.
- Risk: signed maximum drawdown and its magnitude, annualized Sharpe with explicitly stated risk-free assumption, Sortino with root-mean-square downside deviation relative to a stated target, and optional Calmar.
- Trading: closed trade count, win rate, mean gain/loss, profit factor, average holding time, turnover, average/gross exposure, costs and unfilled/rejected counts.
- AI: input coverage, structured-output validity, neutral fallback count, changed decisions and relative exposure.
- Systems: completed/failed/retried work, duplicate side-effect count, final state equivalence and replay success.

R3 systems comparisons use an ordinary uninterrupted offline runner as an independent
artifact reference, plus explicit expected ledger states/cardinalities. Recovered runs
must match run IDs, deterministic file hashes, accounting results and one committed
result/completion event. Attempt/audit counts can increase after retry and are reported
separately. SQLite commits and filesystem publication remain separate resources;
reconciliation verifies a prior durable hash checkpoint rather than assuming atomicity.
Executed local SDK and process-interruption scenarios, including their untested crash,
power-loss and concurrency limits, are recorded in [R3 verification](R3_VERIFICATION.md).

Undefined metrics must be `null`/N/A with a reason (e.g., no losing trades, zero downside deviation, insufficient returns), not fabricated zeros, infinities or favorable replacements. Include numerical unit fixtures and comparisons with an independent reference calculator.

## 8. Experiment registration and result schema

Each experiment configuration records:

- Experiment ID and hypothesis, dataset manifest reference/hash, symbol universe, train/test split, market/calendar convention.
- Strategy/config version and frozen parameters, execution model and cost grid.
- Baseline/ablation/AI policy, frozen AI evidence hash, random seed and iteration counts.
- Output schema version, code commit and expected warnings/limitations.

The runner produces the artifacts required by [specification §9](../app/AI_Assisted_Quant_Research_SPEC_v0.7.md#9-reproducibility-and-artifact-contract). All generated graphs and tables must trace to a run ID and machine-readable metrics. Do not manually edit numbers in the report.

The same snapshot, configuration, code revision and seed must generate identical deterministic content. Separate timestamps or host-specific environment data into a clearly identified nondeterministic metadata section so reproducibility can be tested.

## 9. Research-completion evidence and publication

The final technical report should explain methodology, data limitations, architecture, experimental setup, results, ablations, reliability evidence, threats to validity and future work. The README should lead with the actual result of one reproducible run and explain how to rerun it.

A license-safe synthetic reference run verifies the engineering pipeline; it does **not** answer RQ1 about historical market behavior. Research completion therefore requires an actual, provenance-checked historical study with at least one valid chronological evaluation period, realized simulation results, predeclared benchmarks and limitations. Use a shorter transparently justified window if the proposed 2012-onward split cannot be supported; never synthesize missing years. If historical data are unavailable, the reproducible framework may be delivered but the **empirical research completion gate remains pending**. The AI uplift question may remain inconclusive if a credible as-of historical news corpus is unavailable; that limitation must be prominent.

Use these labels precisely:

- **Synthetic demonstration:** artificial or hand-constructed input used to verify behavior.
- **Historical backtest:** measured strategy behavior on historical market data under modeled execution.
- **Out-of-sample evaluation:** data excluded from the specified fitting/selection procedure, with contamination caveats.
- **Local reliability experiment:** test-server/fake-ledger failure and replay evidence, not cloud or broker-operational proof.

No deployment, live readiness, proven profitability or achieved AI uplift can be claimed. Result publication is deferred until the experiments execute and their provenance has been verified.

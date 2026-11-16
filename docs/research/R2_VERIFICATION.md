# R2 implementation and verification — 2026-11-16

R2 Tasks 5–8 and the mandatory R1 cooldown correction are implemented. The automated
checks below pass. **External acceptance remains pending**; this document does not
declare R2 independently accepted. All executed research examples use original synthetic
market/news inputs. They establish engineering behavior, not historical performance,
AI predictive benefit, statistical significance or investment suitability. R3 has not begun.

## Repository preflight and commit provenance

Starting `main`, cached `origin/main` and actual GitHub `main` were clean and equal at
`656414d24a5e2c19a872d709c6defbba6d16d26a`. GitHub repository metadata identified
ID `1228937377`, name `ai-assisted-quant-research`, full name
`ntua-el21026/ai-assisted-quant-research` and default branch `main`; this was an API
identity check, not an old-URL redirect. `origin` is
`git@github.com:ntua-el21026/ai-assisted-quant-research.git` for fetch and push.
The repository's existing public visibility was not changed.

The root instructions, v0.7 specification, research protocol/architecture, both R1
handoffs, approved plan and checkpoint Prompt 2 were read completely before changes.
Work stayed on `main`; no branch, PR, tag, deployment, schedule, broker operation,
provider acquisition or Actions configuration was created or activated.

| Commit | Scope |
| --- | --- |
| `838e9848c56749fc515eeec878747a7fce5832d8` | Mandatory research-only cooldown correction, verified before R2 work |
| `dca59ddc8fb46185097da0254a3998242f4372b7` | Independent research metrics and aligned price benchmarks |
| `98f7f0117eea07c10fa23384715345f04d0d1814` | Frozen offline AI replay, lazy compatible AI exports and synthetic evidence |
| `10cb6881d57e8f931057cf687597aa0f910255bf` | Measured causal-feature cache, frozen reference and parity tests |
| `ba6437ae3d5b7bac90acfcfef4f1fe0cdac0f160` | Registered chronological experiments, ablations and uncertainty |
| `bd2f422f47d139c2396321b38d1b2986b50a83e5` | Integrated offline matrix CLI and atomic nested artifacts |
| `4bf244d20748f85686abb7c5f435445895c65d64` | Review regressions: resolved AI identity, neutral execution bounds, truthful warm-up provenance |

The measured/hash-indexed executions below identify **source commit `4bf244d`**.
Documentation follows that commit. Since the actual Git HEAD is an identity input,
a later documentation commit changes run IDs and manifest hashes even when source,
data and numerical results are identical. The final handoff supplies the final
documentation SHA. The post-commit publication receipt is retained locally as
`results/r2-final-handoff.json`, recording actual HEAD/origin/GitHub equality and clean
tracked status; publication is claimed only after that check succeeds.

## Mandatory R1 correction

The independent issue was reproduced through **actual research decisions**:
RISK_OFF could be followed by non-confirming CAUTION with entries allowed while the
cooldown counter remained positive. Five of ten initial regression cases failed.
The research adapter now imposes its no-entry overlay on every non-RISK_OFF state
while the incoming counter is positive. The historical operational classifier
`packages/strategy/regime.py` remains unchanged.

For a RISK_OFF observation at session index 199 and configured length N, subsequent
sessions `200 .. 199+N` forbid entries, and `200+N` is the first eligible recovery
session if other filters pass. Thus N=0 allows 200, N=1 allows 201 and N=3 allows 203.
Repeated RISK_OFF at 201 resets the interval: N=3 blocks 202–204 and permits 205.
Missing proxy observations independently block decisions and consume one elapsed
calendar session; they do not pause time or bypass the remaining cooldown.

`tests/unit/test_research_cooldown.py` covers lengths 0/1/3, repeated RISK_OFF,
unavailable proxy, exact boundaries and several consecutive non-confirming CAUTION
observations. RED was **5 failed/5 passed**, then GREEN **10 passed**. The correction
gate also passed 61 affected cases, the full **732 passed/9 skipped** suite, Ruff
and scoped mypy before commit `838e984` and before any R2 implementation.

The [R1 implementation contract](R1_IMPLEMENTATION.md) reconciles CAUTION semantics:
the frozen research baseline retains ordinary filters and gross caps, halves and
floors decision quantity, and does not implement legacy FinalScore-80, half-gross-cap
or persistent-RISK_OFF flattening rules. This is a declared baseline simplification,
not new strategy tuning. Registered regime ablation removes the gate and its sizing
multiplier; all other numerical portfolio constraints and protective stops remain.

## Implemented interfaces and compatibility

| Module/interface | Implemented contract |
| --- | --- |
| `research.metrics.evaluate_research_metrics` | `ResearchMetricReport`: values, units, definitions, assumptions and exact null reasons; `MetricSettings` registers annualization/risk-free/target/ddof |
| `research.benchmarks.evaluate_benchmarks` | Exact strategy-calendar alignment, SPY B&H, lagged-exposure SPY, equal initial universe allocation; explicit missing/basis limitations |
| `research.feature_cache.CausalFeatureCache` | Precomputes unchanged deterministic feature recurrences; availability/prefix checks preserve causal histories, warm-up, timestamps and all reasons |
| `research.validation.load_matrix_config` | Hash-bound baseline YAML plus versioned matrix registration; fixed folds, costs, variants, AI policy, metric/resampling settings and case budget |
| `build_walk_forward_folds` | Anchored chronological development folds; final range is separate and opt-in; actual recursive prefix is distinguished from configured training start |
| `run_experiment_matrix` | Fixed parameters, no fitting/ranking/selection; reset cash/positions per fold; paired controls and complete case provenance |
| `research.resampling` | Fixed-seed trade bootstrap, trade-order Monte Carlo and monthly block bootstrap; explicit insufficiency/overflow outcomes |
| `research.ai_replay.load_frozen_ai_evidence` | Bounded local files, SHA-256/size verification, frozen model/prompt/schema/article/output provenance, resolved file-presence fingerprint |
| `replay_ai_evidence` / `apply_research_ai_overlay` | Candidate-bound as-of replay, verified adverse events only, integer quantity reduction/block, neutral fallback, preserved IDs/timestamps/stops and diagnostics |
| `backtesting.execution.run_causal_backtest` | Existing default R1 behavior; optional `neutral_entry_fills` gates AI entries only at the eligible opening session |
| `research.runner.evaluate_research` | `ExperimentRunSummary`; integrated offline matrix execution and immutable publication; CLI `evaluate`, optional `--include-final` |
| `research.matrix_artifacts` / `artifacts` | Root matrix plus nine complete artifacts per case, deterministic nested paths/hashes and atomic staged publication |

`run_research`/CLI `run`, `ResearchConfig`, default simulator behavior and the legacy
`run_backtest` API remain compatible. The old engine/metrics and operational regime
classifier have no diff from the starting commit. R1's compatibility artifacts retain
null/deferred research ratios; use `evaluate` for the new statistical reports.
Legacy `packages.ai` public exports retain their names/identities through lazy loading;
canonical imports do not load provider clients or broker dependencies.
Research filter ablations are rejected for operational candidates.

Changes are concentrated in the modules above, `packages/strategy/signals.py`'s optional
research-only ablation argument, `packages/ai/__init__.py`, the benchmark script,
registered YAML, synthetic AI fixtures, research tests and active documentation.
No dependency, Python/Node package metadata, lockfile, legacy evidence, historical
specification, archived instruction, deployment record or workflow was changed.

## Numerical and causality verification

Independent literal expectations are asserted in
`tests/unit/test_research_metrics_benchmarks.py` and `test_research_validation.py`:

| Fixture | Hand-derived expectation |
| --- | --- |
| Initial 100; equities 90, 120, 96 | Total return -0.04; signed max drawdown -0.20, including the initial-capital peak |
| Returns 0.1, -0.1, 0.2; A=3; annual RF .331 | Session RF .1; mean 1/15; sample variance 7/300; Sharpe `-1/sqrt(7)` = -0.3779644730092272 |
| Same returns, target zero | Downside RMS over all three returns `sqrt(.01/3)`; Sortino 2.0 |
| Same returns, annual target .331 | Session target .1; downside RMS `sqrt(.04/3)`; Sortino -0.5 |
| Initial 100; terminal 118.8; A=N=3, min sample 3 | Annualized return .188; default min 252 makes the short-sample annualized return null |
| Initial 1000; buy 10 at 10.1/base 10; sell at 10.89/base 11 | Both-side turnover .2099; fees 2.099; slippage 2.1; net P&L 5.801; fixed-execution gross P&L 10 |
| Same entry held at mark 11 | Unrealized net P&L 7.99; entry costs included; no invented terminal sale |
| SPY first open 100, closes 110/99/118.8, capital 100 | B&H equity 110/99/118.8; with flat QQQ equal allocation 105/99.5/109.4 |
| Prior EOD exposures 1/0/1 | Analytical exposure-adjusted SPY equity 100/90/90; current/future exposure cannot weight its own return |
| Bootstrap P&Ls 1/1, capital 100 | All 20 seed-7 draw net-P&L percentiles 2; return .02 |
| Permute P&Ls 10/-5, capital 100 | Every terminal return .05; worst ordering drawdown -.05 |
| Two zero-return months | Seed-11 monthly return interval lower/median/upper all zero; one observed month is explicitly insufficient |

Sharpe uses compounded per-session risk-free rate and registered sample ddof=1;
Sortino uses compounded target and RMS downside over **all** observations. Default
annualization is 252 sessions/year and requires 252 observations for annualized return.
No trades/losses/downside/variance, zero-equity transitions, missing fill provenance,
overflow and insufficient samples produce null with reasons. Open holdings are censored,
separate from closed trade statistics. The gross/net bridge retains actual fills and
quantities; it is not a cost-free counterfactual strategy rerun.

Benchmarks are frictionless fractional-unit **price-return** comparators on declared
raw, action/dividend-free coverage, with zero cash yield and no invented closing sale.
The exposure comparator is analytical and uses prior EOD exposure. Missing prices omit
the entire affected comparator; approved-universe gaps do not cause survivor reweighting.
No dividend-inclusive historical SPY series is available or claimed.

The R1 numerical fixtures still pass, including next-open fees, routine/stop/gap exits,
simultaneous symbol/cash competition, duplicates, missing bars, terminal holdings and
P&L conservation. The full-range reference still closes one QQQ share with P&L
**-19.5168864 USD**, fees **.0328864 USD**, final cash/equity **9980.4831136 USD**.

Feature-cache tests compare every decision field and serialized record with the frozen
post-correction, pre-optimization implementation, including delayed/missing observations,
RISK_OFF/CAUTION, reversed inputs, cache identity, future-price mutation and exit history.
All three measured scales retain identical complete decision hashes. Integration tests
also mutate the excluded final period and verify unchanged development artifacts.

## Frozen AI evidence and review corrections

The reference model outputs/articles are **hand-authored synthetic illustrations created
on 2026-11-16**, using an artificial 2025 replay timeline. They are not actual provider
responses, model invocations or historical observations. Descriptor files and original
fixture licensing retain this distinction. The research-bound model descriptor freezes
the R1 baseline/data identity; no real model or provider is contacted.

Two records bind exact QQQ decision IDs: the index-200 adverse event blocks the one-share
candidate; index-202 reduces two shares to one. Artificial publication 19:00, observed
availability 19:05, analysis 19:10 and output availability 19:11 UTC precede the 20:01
decision. Replay requires symbol/URL/title/source/hash citation binding, legal temporal
ordering and prior event dates. Future, malformed, unavailable, conflicting or missing
evidence is neutral; declared byte-integrity violations fail explicitly. Latest eligible
invalid output does not trigger cherry-picking an older favorable record. Duplicated
adverse evidence is deduplicated. Raw positive/sizing/block fields cannot add authority.

A fresh internal review of `656414d..bd2f422` reproduced two Important findings and
one provenance issue. All entered one regression-led correction wave:

1. **Resolved input identity:** missing declared output/article files previously changed
   results while keeping the run/case IDs. Two regressions first failed. The manifest
   hash is now accompanied by a canonical `resolved-ai-evidence/v1` fingerprint of
   logical references, declared hashes/sizes, actual verified/missing status and verified
   hashes/sizes. Complete, missing-output and missing-article inputs have different root
   and case IDs; repeated identical incomplete bundles reproduce exactly. Artifacts
   preserve statuses and warnings. Relocating an identical bundle preserves its identity.
2. **Replacement trades:** a veto previously released capacity for a later two-share
   entry absent from the neutral portfolio. Three regressions first failed. The new
   `neutral-shadow-entry/v1` guard checks only the matching eligible opening's executable
   neutral entry ID/symbol/quantity. It never filters earlier decisions with future fills.
   Tests cover replacement trades, cross-symbol capacity, reductions, excessive quantities
   and later fills that cannot authorize an earlier order. Matrix execution also enforces
   pointwise gross USD exposure no greater than control.
3. **Warm-up provenance:** the reviewer labeled a later configured-start mismatch Minor;
   it was regraded Important because accepted configurations misstated their recursive
   input prefix. The failing regression now passes: `train_start` remains configured,
   while `warmup_start` records the actual snapshot start and changes fold identity.

The exposure contract is interpreted as nonincreasing executable entry identities,
share quantities and session gross **USD notional**, matching `EquityPoint.gross_exposure`.
Equity-normalized ratios use each portfolio's actual denominator and can increase when
avoiding a profitable trade lowers equity. Enforcing unconditional ratio monotonicity
would require an additional liquidation/allocation policy; none was introduced. This
explicit interpretation is submitted for external review, rather than silently adding
unregistered strategy rules.

In the first registered baseline/cost-baseline development pair, neutral buys one QQQ
share on October 10. Its October 9/10/13/14 gross exposures are **0/178/182/186 USD**,
net P&L **7.8041822 USD**. Negative-only vetoes it and rejects substitute entries;
its gross exposure and P&L are zero. Two candidate changes are recorded; no AI benefit
claim follows. With absent evidence, paired simulation results match exactly.

## Registered experiments and uncertainty

`experiments/configs/ablations.yaml` hash-binds the unchanged R1 baseline. The 210-session,
three-symbol reference registers initial training 200 sessions, development windows 4,
and a separate two-session final range October 21–22, 2025. Development folds are
October 9–14 and October 15–20. The synthetic final segment was deliberately examined
for engineering isolation tests; it is not an untouched empirical holdout.

Four fixed variants are baseline, without regime, without relative strength and without
volume. Baseline entry/routine/stop slippage is 10/10/20 bps, stress 25/25/40 bps;
both use 1 bp per side on slipped notional. Both AI policies share identical market
path, weights, budgets, costs and folds. There is no optimization, fitting or ranking.
Two folds × four variants × two costs × two policies produce **32 cases/16 pairs**;
explicit `--include-final` gives **48 cases/24 pairs**. The maximum registered case budget
is 64. Portfolios reset each fold; complete causal historical prefixes feed indicators.

Seed 0 and 200 draws, confidence .95 and minimum two units are registered. Method seeds
derive deterministically from base seed, case ID and method name. Percentiles use linear
interpolation. Trade bootstrap resamples closed absolute P&Ls; order Monte Carlo permutes
them without replacement. They exclude open unrealized P&L and are conditional accounting
experiments. Monthly bootstrap preserves within-calendar-month order, includes partial
observed months and truncates the final sampled block to the original session count.
Insufficient trade/month samples remain null. The full-study 10,000-draw protocol target
is deferred; 200 is an explicit engineering configuration, not a silently reduced claim.
No independence, nonstationarity, selection-bias or multiple-comparison correction is implied.

Before its execution, a supplementary mechanical engineering registration was frozen at
`results/r2-qualification/registration.yaml`: 756 synthetic weekdays/five artificial symbols,
252 training sessions, three 126-session development windows and a separate excluded final
126 sessions. Fixed variants/costs remain identical; AI evidence is explicitly absent,
so negative and neutral controls agree. It executes **48 cases**, each with **4–8 closed
trades** and non-null outputs from all three uncertainty methods. This exercises paths
that are honestly undefined in the tiny reference, without inventing historical samples.

## Performance qualification

The repeated full-history feature computation was measured **before the extensive matrix**.
The bounded cache reuses the existing deterministic feature recurrences; no strategy
parameter, numeric result, timestamp or rejection reason was changed. The independent
original implementation remains frozen in
`tests/reference/research_signals_before_r2_optimization.py` (SHA below).

| Artificial scale | Original signals + simulation | Final-source signals + simulation, median of 3 |
| --- | ---: | ---: |
| 210 sessions × 3 symbols | .732481 s, median of 3 | .017240 s |
| 756 sessions × 5 symbols | 14.306565 s, one observation | .247750 s |
| 2,520 sessions × 14 symbols | 357.959668 s, one observation | 3.134566 s |

The final 2,520×14 attempts took 3.089030/3.294476/3.134566 seconds. Its signal stage took
1.293397/1.370436/1.385180 seconds, simulator 1.795633/1.924040/1.749386 seconds.
All attempts produced 35,280 identical decisions and 92 closed synthetic trades.
Setup/input generation and artifact export are excluded from these **core** measurements.
The supplementary **complete** 48-case `evaluate_research` pipeline took **3.217725** and
**3.074024** seconds, including parsing/verification, source/environment fingerprints,
all cases/statistics/resampling, serialization and atomic publication. Initial Python
imports, input generation and subsequent byte verification are excluded.

Host: Intel Core Ultra 9 275HX, 24 logical/affinity CPUs, x86_64 WSL2 Linux
6.18.33.2, CPython 3.14.7, Python binary64 prices/statistics and integer shares.
Some earlier baseline measurements shared the host with development checks; the larger
original scales have only one observation. Timings are descriptive host observations,
not a controlled speedup/general scalability guarantee. No additional speculative
optimization was made; the simulator remains an evident future cost at larger scales.
Raw observations, source/script hashes and input fingerprints remain ignored under
`results/r2-performance/`; final observations identify source `4bf244d`.

## Executed commands and outcomes

The existing project `.venv` was preserved. CPython 3.14.7, uv .12.9, Pytest 9.0.3,
Ruff .15.12, mypy 1.20.2, Pydantic 2.13.3 and PyYAML 6.0.3 were used. No package
installation, dependency upgrade or system/GPU environment change was required.

| Exact command | Outcome |
| --- | --- |
| `uv run --offline --no-sync pytest tests/unit/test_research_cooldown.py -q` | RED 5 failed/5 passed, then GREEN 10 passed before R2 |
| `uv run --offline --no-sync pytest tests/unit/test_research_metrics_benchmarks.py -q` | Initial RED 26 failures; expanded GREEN 31 cases |
| `uv run --offline --no-sync pytest tests/unit/test_research_ai_replay.py -q` | Initial RED 37 missing-feature failures/1 existing pass; expanded to 49 final cases |
| `uv run --offline --no-sync pytest tests/unit/test_research_feature_cache.py -q` | Initial missing-cache RED; GREEN 9 parity cases |
| `uv run --offline --no-sync pytest tests/unit/test_research_validation.py -q` | Initial 5 missing-interface failures; additional safety regressions RED→GREEN; final 8 cases |
| `uv run --offline --no-sync pytest tests/integration/test_research_experiments.py -q` | Initial 7 failures, then GREEN; added provenance regression; final 8 cases |
| `uv run --offline --no-sync pytest tests/unit/test_research_ai_replay.py -k resolved_evidence -q` | Review I1 RED 2 failed, then GREEN 2 passed/47 deselected |
| `uv run --offline --no-sync pytest -q tests/unit/test_research_ai_execution.py tests/unit/test_research_execution.py -k 'neutral_shadow or registered_ai_fills'` | Review I2 RED 3 failed; GREEN 3 passed |
| `uv run --offline --no-sync pytest tests/unit/test_research_fold_provenance.py -q` | Regraded review M1 RED 1 failed, then GREEN 1 passed |
| `uv run --offline --no-sync pytest tests/unit/test_research_*.py tests/integration/test_research_cli.py tests/integration/test_research_experiments.py -q` | **174 passed**, 8.18 s, zero skips/errors |
| `uv run --offline --no-sync pytest -q -rs` | **841 passed, 9 skipped, 0 failed/errors**, 22.68 s; 3 existing Temporal warnings |
| `uv run --offline --no-sync ruff check .` | PASS, repository-wide |
| `uv run --offline --no-sync mypy packages/research packages/backtesting packages/data/snapshots.py packages/data/quality.py packages/risk packages/strategy/signals.py packages/ai/__init__.py scripts/benchmark_research_pipeline.py` | PASS, 30 source files |
| `uv lock --check --offline` | PASS, 27 lock entries |
| `uv sync --locked --group dev --offline --check` | PASS, 25 installed packages, would make no changes |
| `uv run --offline --no-sync npm test` | PASS, frontend-only historical-preview safety checks; no deployment |
| `python3 scripts/check_markdown_links.py` | PASS, 87 Markdown files/115 local links, no failures/unchecked fragments |
| `git diff --check` | PASS |
| `gh api repos/ntua-el21026/ai-assisted-quant-research --jq '{id, name, full_name, default_branch, html_url}'` | PASS, canonical repository identity above |
| `git remote -v` and `git ls-remote origin refs/heads/main` | Canonical SSH URL; remote still starting SHA before final publication |

The full suite includes affected historical strategy/risk/execution/AI/metric and local
Temporal tests. Its nine preexisting skips are Alpaca write/read-only (2), managed DB (2),
news (1), OpenAI (3) and Telegram (1); their external gates were not enabled. The three
warnings are existing Temporal/Pydantic converter deprecations. Existing tests were not
deleted, weakened or skipped to obtain green. Two intermediate agent broad runs encountered
intentional RED tests while parallel code was incomplete; the settled 827/835-case and
final 841-case suites passed. Intentional RED and intermediate failures are not counted
as successful verification.

Additional standard-library assertions compared Python name/version/requirement with
`uv.lock`, and Node name/version/engines/dependency groups with both lock root entries:
PASS. Git no-diff checks protected historical engine/metrics/regime, old specs/evidence/
history/prompts, deployment files and lockfiles. Case-insensitive `rg` found only intentional
old names in historical specs/runbooks/deployment records and audit search terms; no
unresolved active repository-name link was introduced. The Markdown checker validates local
targets/fragments offline, not external website availability. No new binary or credential
file appears in the final diff.

## Reproduction commands and hashes

After locked dependency setup, execute each command with two new output destinations:

```bash
uv run --offline --no-sync python -m packages.research.cli evaluate \
  --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --output results/r2-verified-a
uv run --offline --no-sync python -m packages.research.cli evaluate \
  --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --output results/r2-verified-b
```

The same commands with `--include-final` and destinations `results/r2-final-verified-a`
and `results/r2-final-verified-b` executed the opt-in final pair. R1 compatibility used
`python -m packages.research.cli run --config experiments/configs/baseline.yaml
--dataset tests/fixtures/market_snapshot/manifest.json --output results/r1-r2compat-a`
and `results/r1-r2compat-b`, under the same `uv run --offline --no-sync` prefix.
The network/import-guarded integration test additionally runs the CLI with provider
credentials absent, provider imports forbidden and socket connections refused.

The three final performance commands were:

```bash
uv run --offline --no-sync python scripts/benchmark_research_pipeline.py --sessions 210 --symbols 3 --repeats 3 --output results/r2-performance/final-210x3
uv run --offline --no-sync python scripts/benchmark_research_pipeline.py --sessions 756 --symbols 5 --repeats 3 --output results/r2-performance/final-756x5
uv run --offline --no-sync python scripts/benchmark_research_pipeline.py --sessions 2520 --symbols 14 --repeats 3 --output results/r2-performance/final-2520x14
```

The initial baseline commands used the same scales with `reference-*` destinations,
three repeats for 210 and one for the two larger scales, before optimization. Current
`--implementation reference` explicitly loads the byte-preserved original generator.
The supplementary registration was derived before execution from the committed matrix
with unchanged variants/costs/settings, `initial_train_sessions=252`,
`evaluation_sessions=126`, final dates from synthetic session indices 630/755,
AI manifest/hash null, and a hash-bound generated 756×5 base config. Its two executions
used `evaluate_research(registration, dataset, output)`; exact orchestration and all-byte
verification are retained as `results/r2-qualification/run_qualification.py`, invoked by
`uv run --offline --no-sync python -m results.r2-qualification.run_qualification`.
Inputs regenerate using the committed benchmark script; the ignored supplementary
registration hash and dataset hash are recorded below rather than presented as real data.

| Input | SHA-256 |
| --- | --- |
| Market manifest, 29,084 bytes | `7057ce77e118a3adfebbda8aba85a317b3b74ba30bcd1ae2da055b1410f582ed` |
| Market bars, 48,754 bytes | `fcc5d1fc39bdfde3752a50db8fb5bf0208799e0b3a7cffe52d809ce2e8a487f2` |
| R1 baseline YAML, 2,365 bytes | `db86c1719fa691e6002509f0349216063cea9f7317f1481bd52a9f7920fe6dc5` |
| R2 registration YAML, 1,465 bytes | `e9a24b6f33af4c0c85c7991927a6328c368a1933af60aea16cb1b5e76699a8d9` |
| Research-bound synthetic AI manifest | `3c7d2220d7a8effb2d903adcd4fbb2a69e3c04224d891f9eb1471a1539e1cf5f` |
| Resolved complete research AI evidence | `379bb60aa4788d8ea8134e0f69493580191112287d4d41504b1090684d6a0345` |
| Additional illustrative AI manifest | `866070d388820d461d35125b6f5f81dd5526099bfa164f7ee0ddb1d3caf8bed8` |
| Frozen original causal signal implementation | `223f51452bc56644a81d5ef50b8e8e60c999dd84badc316f6542d6d1db9f8e69` |
| Supplementary registration | `44ea876dfd7f51a7dfc4cbfb69de3d59bbba7c6d770ba1ec42fbd6a224dad4a3` |
| Supplementary 756×5 market manifest | `00272fed47a20b6c014ef1562fca03f0294d92c0da99453378b120d1d5c366c1` |

Exact original/final decision hashes match all records at each scale:

- 630 records: `83915cb0cc396f3d4065bca45e2c59501df7f243ed5390784aa4f4b015c20ccd`.
- 3,780 records: `49e774c350f7e8c0d87a94d57433fd93df3ed512cd3704c673a96c1675468195`.
- 35,280 records: `f630ef32a51e811711d086ebee90d5f0be740326b2eb312a3eab1d3996fcb936`.

At source `4bf244d`, every indexed file was SHA-verified in both runs, every deterministic
byte including `hashes.json` compared equal, and recursive inventories contained exactly
the indexed files plus `hashes.json` and excluded `runtime.json`:

| Pair | Cases | Deterministic files including index | Aggregate deterministic SHA-256 |
| --- | ---: | ---: | --- |
| R1 compatibility | 1 | 8 | `0ca380efae07a59fb066b710522f0290e2d5700708862e1b9b66f9e0502a5d88` |
| R2 development | 32 | 295 | `33b22677d040688be914d1d7a70fe1f9d2255655e1aadd1fbbc37edf0af78093` |
| R2 including final | 48 | 439 | `416ee71c35693d4c1be92fd8a7ae716900ec8d9162ad0df3726bc3777ddbd326` |
| Supplementary matrix | 48 | 439 | `c556b7948342b73317b16c7c771ce3852c10810ce87bed2e680df3850c39930f` |

Development run ID is `9ec119260f5a9c36d0da91f159f5a7433ff3319416c316eb2d5da20a5d54c605`;
including-final ID is `f2ceab045567a23268a6c2574181ddc5c905fa8e1eb1f47c95968b04ffbdfddd`;
supplementary ID is `a3bce3b8a39bd48f39faaafa500992d48ac950d2e28db7272d6ad51fe151270d`.
The SHA-256 of development `hashes.json` itself is
`c85d71adf2ccfb80c6d7639c66b665e616c705831f29e43221a6f7de76812f3d`;
including-final is `d82866eff1d9e4982298b6b9d0fe1da4df01f1addb33822a1757bd89ecb983a4`;
supplementary is `5c48a17f20b21df4c74d4e5ce977251e394a822564893b82617e95bc755ee08e`.
The aggregate hashes the canonical indexed filename→digest map, excluding the index
itself to avoid recursion. `runtime.json` holds timestamps, elapsed time and host details;
actual Python/dependency versions belong to the deterministic declared environment input.

This independent standard-library check reproduces the canonical pair verification:

```python
import hashlib, json
from pathlib import Path
a, b = Path('results/r2-verified-a'), Path('results/r2-verified-b')
index = json.loads((a / 'hashes.json').read_bytes())['sha256']
expected = set(index) | {'hashes.json', 'runtime.json'}
for root in (a, b):
    assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()} == expected
for name, digest in index.items():
    for root in (a, b):
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    assert (a / name).read_bytes() == (b / name).read_bytes()
assert (a / 'hashes.json').read_bytes() == (b / 'hashes.json').read_bytes()
```

Root artifacts are manifest/config/folds/matrix/comparisons/report plus the hash index.
Each case has manifest, effective config including ablation/fold/cost/AI/settings,
trades, equity, metrics/accounting, benchmarks, AI diagnostics, uncertainty and report.
Files are fsynced in a sibling staged directory, then atomically renamed under an
exclusive sibling publication lock. Nested write-failure, path-escape and lock tests
pass. Existing outputs are immutable. Abrupt-crash staging and recovery are R3 concerns.

## Rulings, limitations and external review

Rulings made during implementation, with their practical costs:

- Correct cooldown in the research adapter and preserve the operational classifier:
  historical callers retain their old behavior and require separately authorized work.
- Retain the frozen CAUTION simplification and fixed baseline parameters: results
  evaluate this documented strategy, not every v0.6 narrative rule.
- Keep research metrics separate from legacy helpers: callers must explicitly use
  `evaluate`/research reports for the corrected statistical conventions.
- Preserve complete recursive historical prefixes and report actual warm-up start:
  computation may cost more, while exact recurrence and provenance remain intact.
- Interpret exposure bounds as executable entry/quantity and marked USD notional;
  independent equity ratios remain descriptive. A stronger ratio policy requires
  external agreement and a distinct registered strategy rule.
- Decline historical performance, predictive AI authenticity/benefit, significance and
  untouched-holdout claims: empirical questions remain unanswered without credible data.
- Keep R3/recovery, deployment, production concurrency and power-loss guarantees outside
  R2: this checkpoint does not establish systems/release completion.
- Root reran broad/static/hash checks where the internal reviewer declined independent
  execution; hardware timing remains descriptive, with no performance guarantee.
- Preserve unrelated operational history and tests: legacy limitations remain visible.

No internal-review minors are deferred. The warm-up issue was promoted and corrected
because it affected accepted experiment provenance. The internal review is not external
acceptance. Its one correction wave passed the complete suite; no second review was used
to substitute for regression evidence.

Known limits remain full-or-none integer fills, fixed initial-capital decision sizing,
OHLC-only intraday assumptions, no actions/dividends/delistings, taxes/interest/impact,
short synthetic folds, conditional uncertainty and unaudited real historical universe/
calendar/holdout exposure. Missing held-position data fails explicitly. No licensed
historical news corpus, real model calls or empirical strategy study was supplied.
Other Python minors/platforms were not executed. The existing local Temporal tests
remain legacy coverage; no R3 research workflow/recovery implementation was added.

The R2 implementation and synthetic verification are ready for **external review** of
statistical conventions, causal shadow execution, exposure interpretation, AI provenance,
fold isolation and reproducibility. Full empirical and framework completion remain pending.
Stop here; do not begin R3 without a new authorization.

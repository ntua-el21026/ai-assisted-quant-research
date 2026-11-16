# R1 verification handoff — 2026-11-16

R1 Tasks 1–4 are implemented. The R1 software gate passes the checks below on a fresh
project environment; the owner's independent review remains pending. R2 has not begun.
The full research framework remains in development. This is synthetic engineering evidence,
not an empirical historical study or a trading recommendation.

Starting `main`: `38901a6ceb2bfff4a2d7d31b6cddbd08ffa1aee2` (initially clean and equal to
both cached `origin/main` and `git ls-remote origin refs/heads/main`). GitHub repository metadata
returned ID `1228937377`, name `ai-assisted-quant-research`, and canonical full name
`ntua-el21026/ai-assisted-quant-research`; verification used that identity, not a redirect.
`origin` was set explicitly to `git@github.com:ntua-el21026/ai-assisted-quant-research.git`.

Implementation commits, in order:

| Commit | Work |
| --- | --- |
| `19b5fb6` | Active naming/scope corrections and tested offline Markdown-link checker |
| `746ce34` | Manifest-backed snapshot loader, quality gates and synthetic reference |
| `9673a7c` | Causal feature/regime/candidate/risk adapter and explicit configuration |
| `52d6eeb` | Next-session execution, accounting and backward-compatible result fields |
| `0fd06e3` | Canonical offline runner and deterministic/atomic artifacts |
| `ed16914` | Review regressions and corrections for risk timing, stops and provenance |

This verification document follows those source commits. The final handoff identifies the
final documentation commit and remote synchronization result. No branch, PR, tag, deployment,
schedule, broker write or Actions change is part of R1.

## Interfaces and changed files

The complete contracts, execution phases, limitations and CLI are documented in
[R1 implementation](R1_IMPLEMENTATION.md) and [dataset format](../../datasets/README.md).
Source changes are concentrated in:

- `packages/data/snapshots.py` and `quality.py`: frozen `DatasetSnapshot`, local loader and stable errors.
- `packages/research/models.py`, `signals.py`: explicit `ResearchConfig`, `ResearchSignalSet`,
  cutoff-aware features, accepted/rejected decisions and deterministic IDs.
- `packages/risk/checks.py`, `__init__.py`: numerical simulation adapter and lazy legacy short exports.
- `packages/backtesting/execution.py`, `models.py`: `run_causal_backtest`, order events and terminal positions.
- `packages/research/config.py`, `runner.py`, `artifacts.py`, `cli.py`: frozen configuration parsing,
  `run_research -> ExperimentRunSummary`, source/config/data identity and atomic publication.
- `experiments/configs/baseline.yaml`, synthetic manifest/CSV, four R1 test files, link checker/tests,
  active README/architecture/status documentation and retained-preview labels.

`run_backtest`, its engine/metric source, legacy tests, old specifications, historical evidence,
archived instructions and deployment records remain intact. The new fields on `BacktestResult`
have defaults. No Python or Node dependencies or lock contents changed.

## Executed verification

Environment: CPython **3.14.7**, uv **0.12.9**, pinned Pytest **9.0.3**, Ruff **0.15.12**,
mypy **1.20.2**, Pydantic **2.13.3** and PyYAML **6.0.3**. The initial checkout had no `.venv`;
`uv sync --locked --group dev` created it and installed 25 pinned packages successfully.
No system Python or numerical/GPU stack was modified. Other supported Python minors were not
executed during this checkpoint.

| Exact command | Observed outcome |
| --- | --- |
| `uv sync --locked --group dev` | PASS, fresh environment installed |
| `uv run --locked --group dev pytest tests/unit/test_research_snapshots.py -q` | Initial RED, 18 missing-loader failures |
| `uv run --offline --no-sync pytest tests/unit/test_research_snapshots.py -q` | GREEN, 18 passed |
| `uv run --offline --no-sync pytest tests/unit/test_research_signals.py -q` | Initial RED 5 missing-adapter failures; expanded to 10 final cases |
| `uv run --offline --no-sync pytest tests/unit/test_research_execution.py -q` | Initial RED 13 missing-simulator failures; expanded to 17 final cases |
| `uv run --offline --no-sync pytest tests/integration/test_research_cli.py -q` | Initial RED 4 missing-runner failures/4 closed-input cases; expanded to 10 final cases |
| `uv run --offline --no-sync pytest tests/unit/test_research_signals.py tests/unit/test_strategy_signals.py tests/unit/test_regime.py tests/unit/test_risk_checks.py tests/unit/test_m44_frozen_readiness.py -q` | PASS, 36 cases before added review regressions |
| `uv run --offline --no-sync pytest tests/unit/test_research_execution.py tests/unit/test_backtesting_metrics.py tests/unit/test_execution_intent.py tests/unit/test_strategy_exits.py -q` | PASS, 26 cases before added review regressions |
| `uv run --offline --no-sync pytest -q -rs` | **722 passed, 9 skipped, 0 failed/errors; 3 legacy warnings** |
| `uv run --offline --no-sync ruff check .` | PASS, repository-wide |
| `uv run --offline --no-sync mypy packages/data/snapshots.py packages/data/quality.py packages/research packages/backtesting packages/risk scripts/check_markdown_links.py` | PASS, 21 source files |
| `python3 scripts/check_markdown_links.py` | PASS before this handoff: 83 Markdown files, 108 local links, 0 failures/unchecked fragments; run again for the final document inventory |
| `uv lock --check --offline` | PASS, 27 resolved lock entries |
| `uv sync --locked --group dev --offline --check` | PASS, checked 25 installed packages; no changes |
| `uv run --offline --no-sync npm test` | PASS, frontend-only safety checks; no deployment performed |
| `git diff --check` | PASS |

The 55 final R1 cases are snapshot 18, signals 10, execution 17 and offline integration 10.
An additional 12 tests exercise the link checker. The complete suite includes affected legacy
and local Temporal tests. Its nine skips are existing explicitly gated external tests: Alpaca
write/read-only, two managed-database cases, news provider, three OpenAI cases and Telegram.
Those services were not activated. Three legacy Temporal converter warnings concern Pydantic
v1-style conversion APIs. They do not originate in the offline research runner.

A bare `npm test` initially returned 127 because the host has no `python` executable on its
plain PATH. Running the same package command inside uv supplied the project Python and passed.
Earlier broad runs also caught concurrently introduced link-checker tests and a missing explicit
historical v0.6 AGENTS link; these were corrected without altering any legacy test. Intentional
RED tests and these intermediate failures are not represented as passing runs.

Python/Node lock consistency was also checked with standard-library assertions: project name,
version and Python requirement match `uv.lock`; Node name/version/engines and dependency groups
match both root entries in `package-lock.json`. A no-diff Git check verified the old specs,
evidence/history/prompts, deployment files and legacy backtest engine/metrics against the start.

## Numerical and causal evidence

Independent literal fixtures, checked to USD absolute tolerance `1e-8`, use entry/routine/stop
slippage 10/10/20 bps and fees 1 bp per side on slipped notional:

| Case | Hand-derived result |
| --- | --- |
| 10-share next-open entry at 100 | Fill 100.1; fee 0.1001; cash 8998.8999; equity at close 102 is 10018.8999 |
| Routine next-open exit at 110 | Fill 109.89; exit fee 0.10989; net P&L 97.69001; final equity 10097.69001 |
| Stop 95, intraday low below stop | Fill 94.81; net P&L -53.09491; final equity 9946.90509 |
| Stop 95, opening gap to 90 | Fill 89.82; net P&L -102.98992; final equity 9897.01008 |
| Terminal position at close 110 | Cost basis 1001.1001; unrealized P&L 98.8999; equity 10098.8999 |
| Two symbols, cash 1000, five shares each at 100 | First sorted symbol fills; cash 499.44995; second rejected; equity 999.44995 |
| Canonical synthetic fixture | One share enters at 174.174 and exits at 154.69; fees 0.0328864; P&L -19.5168864; final cash/equity 9980.4831136 |

Tests cover exact-next-session timing, missing prices without deferral, absent terminal sessions,
opening/intraday phase separation, duplicate IDs/orders, cash/risk competition, rejected partial
exits, open positions and zero-trade paths. Equity reconciles to cash plus marks and initial
capital plus realized/unrealized P&L. Future price mutations and future earnings publication
leave earlier decisions identical; delayed observations and inadequate warm-up block features.

The fresh internal source review found and reproduced three decision/exit defects and two
provenance defects. All five received failing regressions before correction: full subsequent-
session cooldown, additive earnings windows, actual-close trailing watermark, effective stop
update/parent metadata, and one-read configuration provenance. The complete 722-case suite
passed after the correction wave. The owner's independent review is still required before R2.

## Fixture hashes and reproducibility

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `tests/fixtures/market_snapshot/manifest.json` | 29084 | `7057ce77e118a3adfebbda8aba85a317b3b74ba30bcd1ae2da055b1410f582ed` |
| `tests/fixtures/market_snapshot/bars.csv` | 48754 | `fcc5d1fc39bdfde3752a50db8fb5bf0208799e0b3a7cffe52d809ce2e8a487f2` |
| `experiments/configs/baseline.yaml` | 2365 | `db86c1719fa691e6002509f0349216063cea9f7317f1481bd52a9f7920fe6dc5` |

The integration test executes the canonical CLI twice, recomputes every digest and checks
byte parity of all deterministic files, including `hashes.json`. `runtime.json` is explicitly
excluded. Final-checkout smoke runs use these commands and new ignored destinations:

```bash
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --output results/r1-verified-a
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json --output results/r1-verified-b
python3 - <<'PY'
import hashlib, json
from pathlib import Path
first, second = Path('results/r1-verified-a'), Path('results/r1-verified-b')
index = json.loads((first/'hashes.json').read_text())['sha256']
for name, digest in index.items():
    assert hashlib.sha256((first/name).read_bytes()).hexdigest() == digest
    assert (first/name).read_bytes() == (second/name).read_bytes()
assert (first/'hashes.json').read_bytes() == (second/'hashes.json').read_bytes()
print('PASS: eight deterministic artifacts match; runtime metadata excluded')
print(json.dumps(index, sort_keys=True, indent=2))
PY
```

Seven required deterministic artifacts plus their hash index are byte-reproducible. The
manifest includes the actual Git revision and dependency versions, so changing either produces
a different run identity. The final handoff links the generated hash index and reports its
aggregate digest. Generated results stay ignored; no large/private/provider data is committed.

## Naming/remnant audit

The case-insensitive `rg` audit included hidden active files while excluding `.git`, `.venv`,
`.superpowers`, ignored results and Node dependencies. It searched `Endeavour`, `ai-trading-bot`,
previous GitHub URLs, autonomous/deployment claims and metadata/lock identity.

- Canonical clone and active GitHub repository links already used the new name. No old GitHub
  repository URL or unresolved active repository-name reference remains.
- Active dashboard title/heading and README now use canonical research identity and explicit
  historical-preview labels. The core package docstring was corrected.
- Old names/paths remain intentionally in v0.2–v0.6 specifications, `docs/history`, dated
  operational/deployment records, the preserved systemd working directory/container image,
  legacy strategy/prompt identities and matching tests. These retain historical meaning.
- The research checkpoint prompt contains the two old names as explicit audit search terms.
  Mentions inside this verification report likewise describe the audit rather than active paths.
- Local Markdown targets/fragments pass the offline checker. External HTTP availability is
  not claimed by that checker; the canonical repository identity was independently verified.

## Rulings and limits

R1 supports declared raw/action-free coverage and rejects unsupported adjustments/actions;
incorrect provider declarations cannot be independently established from OHLCV alone. A real
study needs a verified exchange calendar and point-in-time provenance. Fixed feature periods
are validated explicitly instead of silently accepting settings the legacy helper ignores.
Research Sharpe/Sortino, aligned benchmarks and comparison statistics are null/deferred to R2.

The review's unimplemented R2 AI, R3 Temporal/recovery and empirical historical claims remain
outside the user's R1 authorization. The cost of these scope decisions is explicit: those
paths and claims remain unverified until their own checkpoints. No minors remain deferred
from the internal review. Full-or-none fills, fixed initial-capital decision sizing,
OHLC-only stop assumptions, missing-position-data failure, unmodeled actions/dividends/taxes/
interest/market impact/delistings and retained crash staging/lock evidence remain documented
limitations. R1 software correctness does not imply research completion or trading readiness.

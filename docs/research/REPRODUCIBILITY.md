# Reproduce the public engineering demonstration

**Engineering implementation verified; historical empirical research pending.**
The reference uses original CC0 synthetic prices and a synthetic weekday calendar.
It demonstrates connected software behavior, not market performance, an exchange
calendar, historical AI accuracy or an untouched evaluation period.

## 1. Set up pinned dependencies

Use Python 3.12+ and [uv](https://docs.astral.sh/uv/). The closure environment was
Python 3.14.7; other supported Python versions were not independently qualified here.
Initial cloning/dependency setup can need internet access. Execution below is offline.
An existing clone can start with `uv sync` from its repository root.

```bash
git clone https://github.com/ntua-el21026/ai-assisted-quant-research.git
cd ai-assisted-quant-research
uv sync --locked --group dev
```

For a prepared dependency cache, `uv sync --locked --group dev --offline` performs
setup without downloads. No API key, broker account, Temporal server or managed
database is needed. Keep the same checkout and installed dependency versions for
the two runs: revision, source and environment provenance are deterministic inputs.

## 2. Run the complete data-to-accounting path twice

From the repository root, use two fresh output directories. Existing results are
immutable; the commands refuse to overwrite them. To repeat this entire sequence,
choose two new names consistently rather than deleting earlier evidence.

```bash
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --output results/reviewer-demo-one
uv run --offline --no-sync python -m packages.research.cli run \
  --config experiments/configs/baseline.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --output results/reviewer-demo-two
```

This calls the actual snapshot validator, causal feature computation, deterministic
strategy/regime/risk decisions and next-session simulator. It does not use a scripted
order list, request a provider, import the broker runtime or require credentials.
Features warm up inside the 210-session synthetic series. Decision rationale and
rejections are retained alongside fills; stop/gap behavior, fees, equity and terminal
positions are recorded.

## 3. Verify hashes, inventories, paired bytes and the accounting target

The following is a small inspection command for this fixed, flat public example.
It does not add a verifier API or alter the accepted artifact contracts.

```bash
uv run --offline --no-sync python - <<'PY'
import hashlib
import json
import math
from pathlib import Path

roots = [Path("results/reviewer-demo-one"), Path("results/reviewer-demo-two")]
expected = {
    "manifest.json", "config.snapshot.json", "trades.csv", "equity.csv",
    "metrics.json", "comparisons.json", "report.md",
}
indexes = []
for root in roots:
    assert {p.name for p in root.iterdir()} == expected | {"hashes.json", "runtime.json"}
    assert all(p.is_file() and not p.is_symlink() for p in root.iterdir())
    index = json.loads((root / "hashes.json").read_bytes())
    assert index["schema_version"] == "research-hashes/v1"
    assert set(index["sha256"]) == expected
    for name, digest in index["sha256"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    indexes.append(index)
assert indexes[0] == indexes[1]
for name in expected | {"hashes.json"}:
    assert (roots[0] / name).read_bytes() == (roots[1] / name).read_bytes()
manifest = json.loads((roots[0] / "manifest.json").read_bytes())
metrics = json.loads((roots[0] / "metrics.json").read_bytes())
assert manifest["dataset"]["kind"] == "synthetic"
assert metrics["values"]["trade_count"] == 1
assert metrics["accounting"]["open_positions"] == []
assert math.isclose(metrics["accounting"]["final_equity"], 9980.4831136,
                    rel_tol=0, abs_tol=1e-8)
print("PASS: seven deterministic artifacts, exact inventories and paired bytes verified")
print("SYNTHETIC: one closed trade; final equity USD 9980.4831136")
PY
```

`runtime.json` contains timestamps, elapsed duration and host details and is deliberately
excluded. `hashes.json` is compared byte-for-byte in addition to verifying every indexed
digest. Full run IDs/hashes vary with source revision and recorded environment; numerical
targets remain the accepted fixture expectations. This check does not authenticate an
arbitrary third-party result or establish scientific validity for real market inputs.

## 4. Inspect the result

| Artifact | What a reviewer can trace |
| --- | --- |
| `manifest.json` | Dataset/config/source hashes, revision, dependency versions and limitations |
| `config.snapshot.json` | Effective fixed strategy, regime, risk and cost parameters |
| `trades.csv` | 630 entry decisions plus one stop exit; reasons, eligible sessions, two fills and costs |
| `equity.csv` | Cash, equity and exposure across 210 synthetic sessions |
| `metrics.json` | One closed trade, no terminal positions and reconciled accounting |
| `comparisons.json` | Explicit R1-compatible deferred comparison status; use R2 below |
| `report.md` | Generated method/accounting report with synthetic labeling and warnings |

The independent numerical check starts with USD 10,000, buys one share at
`174 × 1.001 = 174.174`, and exits after a gap at `155 × 0.998 = 154.690`.
Fees total `0.0328864`; realized P&L is `−19.5168864`; final cash/equity is
`9980.4831136`. The entry decision follows the synthetic session close and fills
at the next eligible session open. These are invented fixture prices and arithmetic,
not historical observations or claims of investment performance. Existing numerical
tests use absolute tolerance `1e-8` USD for binary64 calculations.

## 5. Optional existing research and systems paths

The fixed R2 synthetic matrix adds chronological folds, aligned benchmarks, cost stress,
ablations, fixed-seed uncertainty and frozen synthetic negative-only AI comparisons:

```bash
uv run --offline --no-sync python -m packages.research.cli evaluate \
  --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --output results/reviewer-matrix
uv run --offline --no-sync python -m packages.research.historical_demo \
  --dataset tests/fixtures/historical_snapshot/manifest.json \
  --security-id synthetic:001 --initial-cash 1000 \
  --output results/reviewer-actions
```

The second command is the separate **synthetic v2 action/benchmark demonstration**;
its name does not imply historical strategy execution. V1 strategy simulation and
v2 action accounting remain separate accepted interfaces.

With an already available Temporal SDK test-server executable, the finite optional
R3 command runs the actual research activity, local SQLite ledger and history replay:

```bash
uv run --offline --no-sync python -m apps.workers.app.research_local \
  --experiment-id reviewer-synthetic-example \
  --config experiments/configs/ablations.yaml \
  --dataset tests/fixtures/market_snapshot/manifest.json \
  --state results/reviewer-local-workflow \
  --test-server-binary /path/to/existing/temporal-test-server
```

This example path must be replaced with an existing executable. The CLI does not
download one or connect to Temporal Cloud. Repeating the same request/state under
unchanged source/environment verifies the committed result without duplicate effects.
Changing an identity-bound request fails explicitly. SQLite transactions and filesystem
publication are separate; [R3 verification](R3_VERIFICATION.md) states tested recovery
properties and untested power-loss/distributed-concurrency limits.

For the complete fresh test/static-check evidence, source decision and scientific
limitations, see [the final handoff](FINAL_PROJECT_HANDOFF.md). The data formats and
public fixture license are documented in [datasets](../../datasets/README.md).

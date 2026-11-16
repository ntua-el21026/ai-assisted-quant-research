"""Frozen experiment registrations and anchored chronological scoring, with no fitting."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Any, Literal, Self, TypedDict

import yaml
from pydantic import Field, PrivateAttr, model_validator

from packages.backtesting.execution import run_causal_backtest
from packages.backtesting.models import BacktestResult
from packages.data.snapshots import DatasetSnapshot
from packages.research.ai_replay import (
    AIReplayDiagnostic,
    FrozenAIEvidence,
    load_frozen_ai_evidence,
    replay_ai_evidence,
)
from packages.research.artifacts import canonical_json
from packages.research.benchmarks import BenchmarkComparison, evaluate_benchmarks
from packages.research.feature_cache import CausalFeatureCache
from packages.research.metrics import (
    MetricSettings,
    ResearchMetricReport,
    evaluate_research_metrics,
)
from packages.research.models import ExecutionCosts, ResearchConfig, ResearchModel
from packages.research.resampling import (
    bootstrap_trade_pnl,
    monte_carlo_trade_order,
    monthly_block_bootstrap,
)
from packages.research.signals import generate_research_signals


class WalkForwardSettings(ResearchModel):
    initial_train_sessions: int = Field(ge=1)
    evaluation_sessions: int = Field(ge=1)
    warmup_sessions: int = Field(default=200, ge=200)
    final_start: date | None = None
    final_end: date | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.initial_train_sessions < self.warmup_sessions:
            raise ValueError("insufficient_training_warmup")
        if (self.final_start is None) != (self.final_end is None) or (
            self.final_start and self.final_end and self.final_start > self.final_end
        ):
            raise ValueError("invalid_final_evaluation_range")
        return self


class AblationSpec(ResearchModel):
    variant_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    disabled_filters: tuple[Literal["regime", "volume", "relative_strength"], ...] = ()

    @model_validator(mode="after")
    def registered(self) -> Self:
        if len(set(self.disabled_filters)) != len(self.disabled_filters):
            raise ValueError("duplicate_ablation_filters")
        if len(self.disabled_filters) > 1:
            raise ValueError("one_factor_ablation_required")
        return self


class CostScenario(ResearchModel):
    cost_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    execution: ExecutionCosts


class ResamplingSettings(ResearchModel):
    iterations: int = Field(ge=1, le=100000)
    confidence_level: float = Field(gt=0, lt=1)
    minimum_units: int = Field(default=2, ge=2)


class MatrixSettings(ResearchModel):
    schema_version: Literal["experiment-matrix/v1"]
    walk_forward: WalkForwardSettings
    ablations: tuple[AblationSpec, ...]
    costs: tuple[CostScenario, ...]
    ai_policies: tuple[Literal["AI_NEUTRAL", "AI_NEGATIVE_ONLY"], ...]
    resampling: ResamplingSettings
    metrics: MetricSettings = Field(default_factory=MetricSettings)
    holdout_status: Literal["synthetic_engineering_only", "potential_design_contamination"]
    max_cases: int = Field(default=128, ge=1, le=10000)
    ai_manifest: str | None = None
    ai_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def frozen_grid(self) -> Self:
        baseline = [a for a in self.ablations if a.variant_id == "baseline"]
        if len(baseline) != 1 or baseline[0].disabled_filters:
            raise ValueError("one_unchanged_baseline_required")
        if len({a.variant_id for a in self.ablations}) != len(self.ablations):
            raise ValueError("duplicate_variant_id")
        if not self.costs or len({c.cost_id for c in self.costs}) != len(self.costs):
            raise ValueError("nonempty_unique_cost_scenarios_required")
        if not self.ai_policies or len(set(self.ai_policies)) != len(self.ai_policies):
            raise ValueError("nonempty_unique_ai_policies_required")
        if "AI_NEUTRAL" not in self.ai_policies:
            raise ValueError("neutral_control_required")
        if (self.ai_manifest is None) != (self.ai_manifest_sha256 is None):
            raise ValueError("ai_manifest_and_hash_required_together")
        return self


class MatrixResearchConfig(ResearchConfig):
    matrix: MatrixSettings
    registration_sha256: str | None = None
    baseline_input_sha256: str | None = None
    _ai_path: Path | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def unchanged_baseline_cost(self) -> Self:
        baseline = [c for c in self.matrix.costs if c.cost_id == "baseline"]
        if len(baseline) != 1 or baseline[0].execution != self.execution:
            raise ValueError("baseline_cost_must_match_frozen_research_config")
        return self


class WalkForwardFold(ResearchModel):
    fold_id: str
    role: Literal["rolling_oos_development", "final_evaluation"]
    train_start: date
    train_end: date
    warmup_start: date
    warmup_end: date
    minimum_warmup_start: date
    evaluation_start: date
    evaluation_end: date


class MatrixCaseResult(ResearchModel):
    case_id: str
    pair_id: str
    fold: WalkForwardFold
    variant_id: str
    cost_id: str
    ai_policy: Literal["AI_NEUTRAL", "AI_NEGATIVE_ONLY"]
    effective_config: dict[str, Any]
    result: BacktestResult
    metrics: ResearchMetricReport
    benchmarks: BenchmarkComparison
    ai_diagnostics: tuple[AIReplayDiagnostic, ...]
    uncertainty: dict[str, dict[str, Any]]


class ExperimentMatrixResult(ResearchModel):
    schema_version: Literal["research-matrix-results/v1"] = "research-matrix-results/v1"
    cases: tuple[MatrixCaseResult, ...]
    final_evaluation_included: bool
    selection_policy: str = "fixed_registered_parameters_no_fitting_or_ranking"
    warnings: tuple[str, ...]
    evidence_sha256: str | None


def load_matrix_config(path: Path) -> MatrixResearchConfig:
    raw = path.read_bytes()
    doc = yaml.safe_load(raw)
    if not isinstance(doc, dict) or set(doc) != {
        "schema_version",
        "baseline_config",
        "baseline_config_sha256",
        "matrix",
    }:
        raise ValueError("invalid_matrix_registration_fields")
    if doc["schema_version"] != "research-matrix-registration/v1":
        raise ValueError("unsupported_matrix_registration")
    base_path = path.parent / str(doc["baseline_config"])
    data = base_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != doc["baseline_config_sha256"]:
        raise ValueError("baseline_config_hash_mismatch")
    base = ResearchConfig.model_validate(yaml.safe_load(data))
    config = MatrixResearchConfig.model_validate(
        {
            **base.model_dump(mode="json"),
            "matrix": doc["matrix"],
            "registration_sha256": hashlib.sha256(raw).hexdigest(),
            "baseline_input_sha256": digest,
        }
    )
    if config.matrix.ai_manifest:
        config._ai_path = path.parent / config.matrix.ai_manifest
    return config


def build_walk_forward_folds(
    config: ResearchConfig, sessions: tuple[date, ...], *, include_final: bool = False
) -> tuple[WalkForwardFold, ...]:
    if not isinstance(config, MatrixResearchConfig):
        raise ValueError("matrix_configuration_required")
    if not sessions or sessions != tuple(sorted(set(sessions))):
        raise ValueError("calendar_must_be_sorted_unique")
    dates = tuple(d for d in sessions if config.date_start <= d <= config.date_end)
    settings = config.matrix.walk_forward
    if len(dates) <= settings.initial_train_sessions:
        raise ValueError("insufficient_sessions_after_training_warmup")
    if settings.final_start is not None:
        if settings.final_start not in dates or settings.final_end not in dates:
            raise ValueError("final_range_outside_declared_calendar")
        final_index = dates.index(settings.final_start)
        if final_index < settings.initial_train_sessions:
            raise ValueError("final_range_overlaps_initial_training")
    else:
        final_index = len(dates)
    folds = []
    for start in range(settings.initial_train_sessions, final_index, settings.evaluation_sessions):
        end = min(start + settings.evaluation_sessions, final_index) - 1
        folds.append(_fold(dates, start, end, settings.warmup_sessions, "rolling_oos_development"))
    if include_final:
        if settings.final_start is None or settings.final_end is None:
            raise ValueError("final_evaluation_not_registered")
        start = dates.index(settings.final_start)
        folds.append(
            _fold(
                dates,
                start,
                dates.index(settings.final_end),
                settings.warmup_sessions,
                "final_evaluation",
            )
        )
    if not folds:
        raise ValueError("no_registered_evaluation_folds")
    return tuple(folds)


def _fold(dates: tuple[date, ...], start: int, end: int, warmup: int, role: str) -> WalkForwardFold:
    fields = {
        "role": role,
        "train_start": dates[0],
        "train_end": dates[start - 1],
        "warmup_start": dates[0],
        "minimum_warmup_start": dates[max(0, start - warmup)],
        "warmup_end": dates[start - 1],
        "evaluation_start": dates[start],
        "evaluation_end": dates[end],
    }
    digest = hashlib.sha256(canonical_json({k: str(v) for k, v in fields.items()})).hexdigest()
    return WalkForwardFold.model_validate({"fold_id": digest, **fields})


class _SamplingParameters(TypedDict):
    initial_cash: float
    iterations: int
    confidence_level: float
    minimum_units: int


def _uncertainty(
    result: BacktestResult, config: MatrixResearchConfig, case_id: str
) -> dict[str, dict[str, Any]]:
    settings = config.matrix.resampling
    params: _SamplingParameters = dict(
        initial_cash=config.initial_cash,
        iterations=settings.iterations,
        confidence_level=settings.confidence_level,
        minimum_units=settings.minimum_units,
    )
    pnls = tuple(t.pnl for t in result.trades)
    returns = []
    previous = config.initial_cash
    for p in result.equity_curve:
        returns.append(p.equity / previous - 1 if previous > 0 else 0.0)
        previous = p.equity

    def seed(name: str) -> int:
        return int(hashlib.sha256(f"{config.seed}:{case_id}:{name}".encode()).hexdigest()[:16], 16)

    return {
        "trade_bootstrap": bootstrap_trade_pnl(pnls, seed=seed("trade"), **params),
        "trade_order_monte_carlo": monte_carlo_trade_order(
            pnls, seed=seed("permutation"), **params
        ),
        "monthly_block_bootstrap": monthly_block_bootstrap(
            tuple(p.date for p in result.equity_curve), tuple(returns), seed=seed("month"), **params
        ),
    }


def run_experiment_matrix(
    snapshot: DatasetSnapshot,
    config: ResearchConfig,
    *,
    include_final: bool = False,
    evidence: FrozenAIEvidence | None = None,
) -> ExperimentMatrixResult:
    if not isinstance(config, MatrixResearchConfig):
        raise ValueError("matrix_configuration_required")
    if snapshot.manifest_sha256 != config.dataset_manifest_sha256:
        raise ValueError("matrix_dataset_hash_mismatch")
    folds = build_walk_forward_folds(
        config, tuple(s.date for s in snapshot.sessions), include_final=include_final
    )
    budget = (
        len(folds)
        * len(config.matrix.ablations)
        * len(config.matrix.costs)
        * len(config.matrix.ai_policies)
    )
    if budget > config.matrix.max_cases:
        raise ValueError("matrix_case_budget_exceeded")
    frozen = evidence or (
        load_frozen_ai_evidence(config._ai_path) if config._ai_path else FrozenAIEvidence()
    )
    if (
        config.matrix.ai_manifest_sha256 is not None
        and frozen.manifest_sha256 is not None
        and frozen.manifest_sha256 != config.matrix.ai_manifest_sha256
    ):
        raise ValueError("ai_manifest_hash_mismatch")
    last = max(f.evaluation_end for f in folds)
    cache = CausalFeatureCache(
        snapshot, config.strategy.atr_period, through_date=last, proxy_symbol=config.regime.proxy
    )
    cases = []
    for fold in folds:
        for variant in sorted(config.matrix.ablations, key=lambda a: a.variant_id):
            for cost in sorted(config.matrix.costs, key=lambda c: c.cost_id):
                base = ResearchConfig.model_validate(
                    {
                        **{
                            k: v
                            for k, v in config.model_dump().items()
                            if k not in {"matrix", "registration_sha256", "baseline_input_sha256"}
                        },
                        "date_start": fold.evaluation_start,
                        "date_end": fold.evaluation_end,
                        "execution": cost.execution,
                    }
                )
                signals = generate_research_signals(
                    snapshot,
                    base,
                    feature_cache=cache,
                    disabled_filters=frozenset(variant.disabled_filters),
                )
                pair_id = hashlib.sha256(
                    canonical_json(
                        {
                            "fold": fold.model_dump(mode="json"),
                            "variant": variant.model_dump(mode="json"),
                            "cost": cost.model_dump(mode="json"),
                            "config": base.model_dump(mode="json"),
                        }
                    )
                ).hexdigest()
                for policy in sorted(config.matrix.ai_policies):
                    replay = replay_ai_evidence(
                        signals,
                        frozen,
                        snapshot.session_by_date[fold.evaluation_end].decision_at,
                        neutral_control=policy == "AI_NEUTRAL",
                    )
                    result = run_causal_backtest(snapshot, replay.signals, base)
                    case_id = hashlib.sha256(
                        canonical_json(
                            {
                                "pair_id": pair_id,
                                "ai_policy": policy,
                                "evidence_sha256": frozen.manifest_sha256,
                                "matrix": config.matrix.model_dump(mode="json"),
                                "seed": config.seed,
                            }
                        )
                    ).hexdigest()
                    cases.append(
                        MatrixCaseResult(
                            case_id=case_id,
                            pair_id=pair_id,
                            fold=fold,
                            variant_id=variant.variant_id,
                            cost_id=cost.cost_id,
                            ai_policy=policy,
                            effective_config=base.model_dump(mode="json"),
                            result=result,
                            metrics=evaluate_research_metrics(
                                result, base.initial_cash, settings=config.matrix.metrics
                            ),
                            benchmarks=evaluate_benchmarks(
                                snapshot, result, base, settings=config.matrix.metrics
                            ),
                            ai_diagnostics=replay.diagnostics,
                            uncertainty=_uncertainty(result, config, case_id),
                        )
                    )
    return ExperimentMatrixResult(
        cases=tuple(cases),
        final_evaluation_included=include_final,
        warnings=tuple(
            sorted(
                set(
                    (
                        *snapshot.warnings,
                        *frozen.warnings,
                        "fixed_parameters_no_train_fitting_or_final_selection",
                        "fold_portfolios_reset_cash_positions_do_not_carry_between_folds",
                        "conditional_resampling_not_independent_future_confidence",
                        f"holdout_status:{config.matrix.holdout_status}",
                    )
                )
            )
        ),
        evidence_sha256=frozen.manifest_sha256,
    )

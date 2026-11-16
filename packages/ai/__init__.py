"""Bounded AI/news exports, loaded lazily to keep offline imports provider-free."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from packages.ai.budget import (
        InMemoryRequestBudgetStore,
        RequestBudgetDecision,
        RequestBudgetKey,
        RequestBudgetService,
    )
    from packages.ai.dedupe import dedupe_articles, normalize_article, normalize_articles
    from packages.ai.fallback import (
        conflicting_sources_fallback,
        neutral_research_output,
        no_news_fallback,
        provider_outage_fallback,
    )
    from packages.ai.feedback import (
        AICalibrationMetrics,
        AICalibrationReport,
        AIFeedbackCalibrationService,
        AIFeedbackObservation,
        AISafetyState,
        build_ai_calibration_report_payload,
        build_ai_quality_event_payloads,
        compute_calibration_metrics,
    )
    from packages.ai.models import (
        AI_PROMPT_VERSION,
        AI_SCHEMA_VERSION,
        NEUTRAL_AI_SCORE,
        AICitation,
        AIEvent,
        AIProviderFailure,
        AITradeResearchOutput,
        DeterministicShortlistNewsRequest,
        NormalizedNewsArticle,
        ProviderNewsArticle,
    )
    from packages.ai.openai import (
        FakeOpenAIClient,
        OpenAIAnalysisResult,
        OpenAIModelConfig,
        OpenAIModelValidationResult,
        WebFallbackDecision,
        WebFallbackPolicy,
        WebFallbackResult,
        analyze_symbol_news_with_openai,
        build_openai_research_prompt,
        decide_web_fallback,
        openai_ai_research_json_schema,
        run_openai_web_fallback,
        validate_openai_model_availability,
    )
    from packages.ai.parser import parse_ai_trade_research_json, parse_ai_trade_research_or_fallback
    from packages.ai.persistence import (
        AIResearchPersistencePayload,
        build_ai_research_persistence_payload,
    )
    from packages.ai.prompts import load_prompt_template, prompt_template_path
    from packages.ai.providers import (
        ALPHA_VANTAGE_PROVIDER,
        MARKETAUX_PROVIDER,
        AlphaVantageNewsClient,
        FixtureNewsProviderClient,
        MarketauxNewsClient,
        NewsProviderConfig,
        ProviderFetchFailure,
        ProviderFetchResult,
        ProviderFirstNewsService,
        ShortlistNewsResult,
    )
    from packages.ai.scoring import (
        apply_deterministic_ai_policy,
        classify_hard_block,
        mapped_ai_score,
        raw_catalyst_score,
    )

_EXPORT_MODULES = {
    "AICalibrationMetrics": "packages.ai.feedback",
    "AICalibrationReport": "packages.ai.feedback",
    "AICitation": "packages.ai.models",
    "AIEvent": "packages.ai.models",
    "AIFeedbackCalibrationService": "packages.ai.feedback",
    "AIFeedbackObservation": "packages.ai.feedback",
    "AIProviderFailure": "packages.ai.models",
    "AIResearchPersistencePayload": "packages.ai.persistence",
    "AISafetyState": "packages.ai.feedback",
    "AITradeResearchOutput": "packages.ai.models",
    "AI_PROMPT_VERSION": "packages.ai.models",
    "AI_SCHEMA_VERSION": "packages.ai.models",
    "ALPHA_VANTAGE_PROVIDER": "packages.ai.providers",
    "AlphaVantageNewsClient": "packages.ai.providers",
    "DeterministicShortlistNewsRequest": "packages.ai.models",
    "FakeOpenAIClient": "packages.ai.openai",
    "FixtureNewsProviderClient": "packages.ai.providers",
    "InMemoryRequestBudgetStore": "packages.ai.budget",
    "MARKETAUX_PROVIDER": "packages.ai.providers",
    "MarketauxNewsClient": "packages.ai.providers",
    "NEUTRAL_AI_SCORE": "packages.ai.models",
    "NewsProviderConfig": "packages.ai.providers",
    "NormalizedNewsArticle": "packages.ai.models",
    "OpenAIAnalysisResult": "packages.ai.openai",
    "OpenAIModelConfig": "packages.ai.openai",
    "OpenAIModelValidationResult": "packages.ai.openai",
    "ProviderFetchFailure": "packages.ai.providers",
    "ProviderFetchResult": "packages.ai.providers",
    "ProviderFirstNewsService": "packages.ai.providers",
    "ProviderNewsArticle": "packages.ai.models",
    "RequestBudgetDecision": "packages.ai.budget",
    "RequestBudgetKey": "packages.ai.budget",
    "RequestBudgetService": "packages.ai.budget",
    "ShortlistNewsResult": "packages.ai.providers",
    "WebFallbackDecision": "packages.ai.openai",
    "WebFallbackPolicy": "packages.ai.openai",
    "WebFallbackResult": "packages.ai.openai",
    "analyze_symbol_news_with_openai": "packages.ai.openai",
    "apply_deterministic_ai_policy": "packages.ai.scoring",
    "build_ai_calibration_report_payload": "packages.ai.feedback",
    "build_ai_quality_event_payloads": "packages.ai.feedback",
    "build_ai_research_persistence_payload": "packages.ai.persistence",
    "build_openai_research_prompt": "packages.ai.openai",
    "classify_hard_block": "packages.ai.scoring",
    "compute_calibration_metrics": "packages.ai.feedback",
    "conflicting_sources_fallback": "packages.ai.fallback",
    "decide_web_fallback": "packages.ai.openai",
    "dedupe_articles": "packages.ai.dedupe",
    "load_prompt_template": "packages.ai.prompts",
    "mapped_ai_score": "packages.ai.scoring",
    "neutral_research_output": "packages.ai.fallback",
    "no_news_fallback": "packages.ai.fallback",
    "normalize_article": "packages.ai.dedupe",
    "normalize_articles": "packages.ai.dedupe",
    "openai_ai_research_json_schema": "packages.ai.openai",
    "parse_ai_trade_research_json": "packages.ai.parser",
    "parse_ai_trade_research_or_fallback": "packages.ai.parser",
    "prompt_template_path": "packages.ai.prompts",
    "provider_outage_fallback": "packages.ai.fallback",
    "raw_catalyst_score": "packages.ai.scoring",
    "run_openai_web_fallback": "packages.ai.openai",
    "validate_openai_model_availability": "packages.ai.openai",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = [
    "AI_PROMPT_VERSION",
    "AI_SCHEMA_VERSION",
    "NEUTRAL_AI_SCORE",
    "AICitation",
    "AICalibrationMetrics",
    "AICalibrationReport",
    "AIEvent",
    "AIFeedbackCalibrationService",
    "AIFeedbackObservation",
    "AISafetyState",
    "ALPHA_VANTAGE_PROVIDER",
    "AIProviderFailure",
    "AIResearchPersistencePayload",
    "AITradeResearchOutput",
    "AlphaVantageNewsClient",
    "DeterministicShortlistNewsRequest",
    "FakeOpenAIClient",
    "FixtureNewsProviderClient",
    "InMemoryRequestBudgetStore",
    "MARKETAUX_PROVIDER",
    "MarketauxNewsClient",
    "NewsProviderConfig",
    "NormalizedNewsArticle",
    "OpenAIAnalysisResult",
    "OpenAIModelConfig",
    "OpenAIModelValidationResult",
    "ProviderFetchFailure",
    "ProviderFetchResult",
    "ProviderFirstNewsService",
    "ProviderNewsArticle",
    "RequestBudgetDecision",
    "RequestBudgetKey",
    "RequestBudgetService",
    "ShortlistNewsResult",
    "WebFallbackDecision",
    "WebFallbackPolicy",
    "WebFallbackResult",
    "apply_deterministic_ai_policy",
    "analyze_symbol_news_with_openai",
    "build_ai_calibration_report_payload",
    "build_ai_quality_event_payloads",
    "build_ai_research_persistence_payload",
    "build_openai_research_prompt",
    "classify_hard_block",
    "conflicting_sources_fallback",
    "compute_calibration_metrics",
    "decide_web_fallback",
    "dedupe_articles",
    "load_prompt_template",
    "mapped_ai_score",
    "neutral_research_output",
    "no_news_fallback",
    "normalize_article",
    "normalize_articles",
    "openai_ai_research_json_schema",
    "parse_ai_trade_research_json",
    "parse_ai_trade_research_or_fallback",
    "prompt_template_path",
    "provider_outage_fallback",
    "raw_catalyst_score",
    "run_openai_web_fallback",
    "validate_openai_model_availability",
]

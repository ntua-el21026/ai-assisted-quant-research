"""Explicit YAML/JSON configuration; no provider or environment overrides."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from packages.research.models import ResearchConfig


def load_research_config(path: Path) -> ResearchConfig:
    try:
        return parse_research_config(path.read_bytes())
    except OSError as exc:
        raise ValueError(f"invalid_config: {exc}") from exc


def parse_research_config(data: bytes) -> ResearchConfig:
    """Validate exactly the frozen bytes used for input provenance."""
    try:
        return ResearchConfig.model_validate(yaml.safe_load(data))
    except (yaml.YAMLError, ValidationError) as exc:
        raise ValueError(f"invalid_config: {exc}") from exc

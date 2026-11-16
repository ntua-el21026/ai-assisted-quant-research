"""Explicit YAML/JSON configuration; no provider or environment overrides."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from packages.research.models import ResearchConfig


def load_research_config(path: Path) -> ResearchConfig:
    try:
        values = yaml.safe_load(path.read_bytes())
        return ResearchConfig.model_validate(values)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ValueError(f"invalid_config: {exc}") from exc

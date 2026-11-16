"""Lazy legacy registry exports; research activities have an isolated import path."""

from importlib import import_module
from typing import Any

_MODULES = {
    "ACTIVITY_FUNCTIONS": "contracts",
    "AI_ACTIVITY_FUNCTIONS": "ai",
    "BROKER_ACTIVITY_FUNCTIONS": "broker",
    "LEDGER_ACTIVITY_FUNCTIONS": "ledger",
    "REPORTING_ACTIVITY_FUNCTIONS": "reporting",
}


def __getattr__(name: str) -> Any:
    if name not in _MODULES:
        raise AttributeError(name)
    value = getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
    globals()[name] = value
    return value


__all__ = [
    "ACTIVITY_FUNCTIONS",
    "AI_ACTIVITY_FUNCTIONS",
    "BROKER_ACTIVITY_FUNCTIONS",
    "LEDGER_ACTIVITY_FUNCTIONS",
    "REPORTING_ACTIVITY_FUNCTIONS",
]

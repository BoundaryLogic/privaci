"""Table-name context priors for auto-detect confidence."""

from __future__ import annotations

import re

_SENSITIVE = (
    "patient",
    "user",
    "customer",
    "member",
    "employee",
    "visit",
    "clinical",
    "provider",
    "ticket",
    "support",
    "auth",
    "session",
    "contact",
    "person",
    "client",
)

_LOW_SENSITIVITY = (
    "product",
    "catalog",
    "config",
    "system",
    "inventory",
    "sku",
    "item",
    "warehouse",
)


def table_sensitivity(table_name: str) -> str:
    """Classify table context as ``sensitive``, ``low``, or ``neutral``."""
    lowered = table_name.lower()
    if _matches_any(lowered, _SENSITIVE):
        return "sensitive"
    if _matches_any(lowered, _LOW_SENSITIVITY):
        return "low"
    return "neutral"


def _matches_any(table_name: str, tokens: tuple[str, ...]) -> bool:
    for token in tokens:
        if token in table_name:
            return True
        if re.search(rf"(^|_){re.escape(token)}(_|$)", table_name):
            return True
    return False

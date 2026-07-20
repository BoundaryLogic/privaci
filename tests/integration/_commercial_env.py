"""Helpers when the commercial plugin is installed beside the public engine."""

from __future__ import annotations

import importlib.metadata
import os

_PLUGIN_GROUP = "privaci.plugins"


def commercial_plugin_installed() -> bool:
    """Return True when a commercial license or metering plugin is registered."""
    try:
        eps = importlib.metadata.entry_points(group=_PLUGIN_GROUP)
    except (ImportError, AttributeError, TypeError):
        return False
    return any(ep.name in {"usage_meter", "license_validator"} for ep in eps)


def ensure_commercial_dev_license() -> None:
    """Allow pipeline runs when commercial metering is active (local dev only)."""
    if commercial_plugin_installed():
        os.environ.setdefault("PRIVACI_COMMERCIAL_DEV_LICENSE", "1")

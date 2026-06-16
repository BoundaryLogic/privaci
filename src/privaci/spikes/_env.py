"""Environment helpers for spike scripts."""

from __future__ import annotations

import os


def dsn_from_env(name: str) -> str | None:
    """Return a database URL from the environment if set and non-empty."""
    value = os.environ.get(name, "").strip()
    return value or None

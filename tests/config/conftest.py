"""Shared fixtures for config tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.fixtures.constants import (
    SSN_PATTERN,
    SSN_REPLACEMENT,
    SUPPORTED_CONFIG_VERSION,
)


@pytest.fixture
def valid_config_dict() -> dict[str, Any]:
    """Return the proposal's reference config as a plain dict."""
    return {
        "version": SUPPORTED_CONFIG_VERSION,
        "tables": {
            "users": {
                "strategy": "transform",
                "columns": {
                    "first_name": {"action": "fake", "provider": "first_name"},
                    "email": {"action": "fake", "provider": "email"},
                    "ssn": {
                        "action": "regex_mask",
                        "pattern": SSN_PATTERN,
                        "replace": SSN_REPLACEMENT,
                    },
                    "password": {"action": "hash"},
                },
            },
            "audit_logs": {"strategy": "exclude"},
        },
    }


@pytest.fixture
def write_config(tmp_path: Path) -> Callable[[dict[str, Any] | str], Path]:
    """Return a helper that writes a config dict/str to a temp YAML file."""

    def _write(data: dict[str, Any] | str) -> Path:
        target = tmp_path / "mask-rules.yaml"
        text = data if isinstance(data, str) else yaml.safe_dump(data)
        target.write_text(text, encoding="utf-8")
        return target

    return _write

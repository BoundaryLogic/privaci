#!/usr/bin/env python3
"""Tests for scripts/check_public_repo_language.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    path = _REPO_ROOT / "scripts" / "check_public_repo_language.py"
    spec = importlib.util.spec_from_file_location("check_public_repo_language", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_module()


def test_scan_commit_message_rejects_growth_tier() -> None:
    # Act
    violations = _mod.scan_commit_message("Add Growth+ keyed masking for commercial")

    # Assert
    assert any("Growth" in v for v in violations)


def test_scan_commit_message_allows_plugin_contract_wording() -> None:
    # Act
    violations = _mod.scan_commit_message("Add object_writer plugin contract")

    # Assert
    assert violations == []


def test_find_violations_allowlists_adr_paths() -> None:
    # Act
    violations = _mod._find_violations(
        "AWS Marketplace subscription tiers",
        label="docs/adr/0007-public-commercial-split.md",
        rel="docs/adr/0007-public-commercial-split.md",
    )

    # Assert
    assert violations == []


def test_find_violations_allows_commercial_layer_in_cli() -> None:
    # Act
    violations = _mod._find_violations(
        "pdf requires the commercial layer",
        label="src/privaci/cli/app.py",
        rel="src/privaci/cli/app.py",
    )

    # Assert
    assert violations == []


def test_find_violations_rejects_commercial_plugin_in_contracts() -> None:
    # Act
    violations = _mod._find_violations(
        "Discover commercial plugin entry points",
        label="src/privaci/contracts/plugins.py",
        rel="src/privaci/contracts/plugins.py",
    )

    # Assert
    assert any("commercial plugin" in v for v in violations)


def test_scan_full_passes_on_current_tree() -> None:
    # Act
    violations = _mod.scan_full()

    # Assert
    assert violations == []

"""Tests for release and privacy guard scripts."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(filename: str):
    path = _REPO_ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_validate = _load_script_module("check_contract_version.py").validate_contract_version


def test_validate_contract_version_allows_pre_1_engine_with_contract_1() -> None:
    # Act / Assert
    _validate(package_version="0.1.0-beta.1", contract_version="1.0")


def test_validate_contract_version_requires_matching_majors_from_1_0() -> None:
    # Act / Assert
    _validate(package_version="1.2.3", contract_version="1.0")
    with pytest.raises(ValueError, match="incompatible"):
        _validate(package_version="2.0.0", contract_version="1.0")


def test_check_git_emails_passes_on_clean_repo() -> None:
    # Act
    exit_code = _load_script_module("check_git_emails.py").main()

    # Assert
    assert exit_code == 0


def test_check_contract_version_script_passes_when_installed() -> None:
    # Act
    exit_code = _load_script_module("check_contract_version.py").main()

    # Assert
    assert exit_code == 0

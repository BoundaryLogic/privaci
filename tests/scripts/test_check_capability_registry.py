"""Tests for scripts/check_capability_registry.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    path = _REPO_ROOT / "scripts" / "check_capability_registry.py"
    spec = importlib.util.spec_from_file_location("check_capability_registry", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_module()


def test_validate_test_paths_passes_for_current_registry() -> None:
    # Act
    issues = _mod.validate_test_paths()

    # Assert
    assert issues == []


def test_validate_ids_passes_for_current_registry() -> None:
    # Act
    issues = _mod.validate_ids()

    # Assert
    assert issues == []


def test_validate_new_tests_registered_allows_registry_update(
    mocker: pytest.Mock,
) -> None:
    # Arrange
    mocker.patch.object(
        _mod,
        "_staged_paths",
        return_value={"scripts/capability_test/registry.py"},
    )
    mocker.patch.object(
        _mod,
        "_staged_added_test_files",
        return_value=["tests/storage/test_new_feature.py"],
    )

    # Act
    issues = _mod.validate_new_tests_registered()

    # Assert
    assert issues == []


def test_validate_new_tests_registered_rejects_unregistered_file(
    mocker: pytest.Mock,
) -> None:
    # Arrange
    mocker.patch.object(_mod, "_staged_paths", return_value={"tests/storage/test_new.py"})
    mocker.patch.object(
        _mod,
        "_staged_added_test_files",
        return_value=["tests/storage/test_new.py"],
    )

    # Act
    issues = _mod.validate_new_tests_registered()

    # Assert
    assert len(issues) == 1
    assert "tests/storage/test_new.py" in issues[0]
    assert "registry.py" in issues[0]


def test_main_passes_on_clean_registry() -> None:
    # Act
    exit_code = _mod.main()

    # Assert
    assert exit_code == 0

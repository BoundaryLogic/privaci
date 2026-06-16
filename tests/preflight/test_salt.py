"""Tests for run salt resolution."""

from __future__ import annotations

import os

import pytest

from privaci.config.models import Config
from privaci.preflight.salt import resolve_run_salt
from privaci.secrets.resolver import SecretResolutionError
from tests.fixtures.constants import MIN_SALT_LENGTH, TEST_SALT


def test_resolve_run_salt_from_global_salt_literal() -> None:
    # Arrange
    config = Config(version="1.0", global_salt=TEST_SALT)

    # Act
    result = resolve_run_salt(config)

    # Assert
    assert result == TEST_SALT


def test_resolve_run_salt_expands_env_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("ANONYMIZATION_SALT", TEST_SALT)
    config = Config(version="1.0", global_salt="${ANONYMIZATION_SALT}")

    # Act
    result = resolve_run_salt(config)

    # Assert
    assert result == TEST_SALT


def test_resolve_run_salt_falls_back_to_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("ANONYMIZATION_SALT", TEST_SALT)
    config = Config(version="1.0")

    # Act
    result = resolve_run_salt(config)

    # Assert
    assert result == TEST_SALT


def test_resolve_run_salt_rejects_missing_value() -> None:
    # Arrange
    config = Config(version="1.0")
    os.environ.pop("ANONYMIZATION_SALT", None)

    # Act / Assert
    with pytest.raises(SecretResolutionError, match="No salt was configured"):
        resolve_run_salt(config)


def test_resolve_run_salt_rejects_short_value() -> None:
    # Arrange
    config = Config(version="1.0", global_salt="a" * (MIN_SALT_LENGTH - 1))

    # Act / Assert
    with pytest.raises(SecretResolutionError, match="minimum is"):
        resolve_run_salt(config)

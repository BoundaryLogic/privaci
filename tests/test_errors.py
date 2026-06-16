"""Tests for the PrivaCI exception hierarchy."""

from __future__ import annotations

import pytest

from privaci.errors import (
    CatalogError,
    ConfigError,
    L3NotInstalledError,
    MaskingError,
    PreflightError,
    PrivaCIError,
    SecretError,
    StateError,
)


def test_vault_pipe_error_is_base() -> None:
    # Arrange
    error = PrivaCIError("base")

    # Act
    caught: PrivaCIError | None = None
    try:
        raise error
    except PrivaCIError as exc:
        caught = exc

    # Assert
    assert caught is error


@pytest.mark.parametrize(
    ("exc_type", "message"),
    [
        (ConfigError, "bad config"),
        (CatalogError, "catalog fail"),
        (MaskingError, "mask fail"),
        (StateError, "state fail"),
        (SecretError, "secret fail"),
        (PreflightError, "preflight fail"),
        (L3NotInstalledError, "l3 missing"),
    ],
)
def test_subclass_inherits_vault_pipe_error(
    exc_type: type[PrivaCIError],
    message: str,
) -> None:
    # Arrange
    error = exc_type(message)

    # Act & Assert
    assert isinstance(error, PrivaCIError)
    assert str(error) == message


@pytest.mark.parametrize(
    ("exc_type", "expected_code"),
    [
        (ConfigError, 3),
        (CatalogError, 2),
        (PreflightError, 2),
        (MaskingError, 1),
        (StateError, 1),
        (SecretError, 4),
        (L3NotInstalledError, 3),
        (PrivaCIError, 1),
    ],
)
def test_default_exit_code_per_class(
    exc_type: type[PrivaCIError],
    expected_code: int,
) -> None:
    # Arrange
    error = exc_type("something happened")

    # Act & Assert
    assert error.exit_code == expected_code


def test_structured_message_includes_context_cause_remediation() -> None:
    # Arrange
    error = ConfigError(
        "Loading mask-rules.yaml",
        cause="Unknown action type 'shuffle' on column users.email",
        remediation="Use one of the supported actions; see docs/configuration.md.",
    )

    # Act
    rendered = str(error)

    # Assert
    assert "Context: Loading mask-rules.yaml" in rendered
    assert "Cause: Unknown action type" in rendered
    assert "Remediation: Use one of the supported actions" in rendered
    assert "See: docs/error-codes.md#exit-code-3-config-validation-failure" in rendered


def test_bare_context_keeps_plain_message() -> None:
    # Arrange
    error = StateError("checkpoint write failed")

    # Act & Assert
    assert str(error) == "checkpoint write failed"


def test_explicit_exit_code_overrides_class_default() -> None:
    # Arrange
    error = SecretError("bad db url", exit_code=2)

    # Act & Assert
    assert error.exit_code == 2

"""Tests for SecretStr and log redaction."""

from __future__ import annotations

import logging

from privaci.secrets import SecretRedactionFilter, SecretStr


def test_secret_str_redacts_repr_and_str() -> None:
    # Arrange
    secret = SecretStr("super-secret-value-1234567890")

    # Act
    repr_value = repr(secret)
    str_value = str(secret)
    raw = secret.get_secret_value()

    # Assert
    assert repr_value == "<redacted>"
    assert str_value == "<redacted>"
    assert raw == "super-secret-value-1234567890"


def test_register_secret_includes_short_values() -> None:
    # Arrange
    SecretRedactionFilter.clear_registered_secrets()

    # Act
    SecretRedactionFilter.register_secret("dev")

    # Assert
    assert len(SecretRedactionFilter._patterns) == 1


def test_redaction_filter_strips_registered_secret() -> None:
    # Arrange
    SecretRedactionFilter.clear_registered_secrets()
    SecretRedactionFilter.register_secret("leak-me-now")
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="failed with leak-me-now in message",
        args=(),
        exc_info=None,
    )
    filt = SecretRedactionFilter()

    # Act
    filt.filter(record)

    # Assert
    assert "leak-me-now" not in record.msg
    assert "<redacted>" in record.msg

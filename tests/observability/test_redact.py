"""Tests for event-payload PII redaction."""

from __future__ import annotations

import pytest

from privaci.observability.redact import redact_fields, redact_value


def test_redact_value_uses_length_and_hash_not_prefix() -> None:
    # Arrange
    ssn = "123-45-6789"

    # Act
    result = redact_value(ssn)

    # Assert
    assert result.startswith("***len=11:")
    assert "123" not in result
    assert "6789" not in result
    assert result == redact_value(ssn)


@pytest.mark.parametrize("value", [None, ""])
def test_redact_value_handles_empty(value: str | None) -> None:
    # Assert
    assert redact_value(value) == "***"


def test_redact_fields_redacts_unknown_string_fields() -> None:
    # Arrange
    fields = {
        "table_name": "users",
        "rows_processed": 100,
        "sample_value": "john@acme.com",
        "notes": "contains PII",
    }

    # Act
    result = redact_fields(fields)

    # Assert
    assert result["table_name"] == "users"
    assert result["rows_processed"] == 100
    assert "john" not in result["sample_value"]
    assert "john" not in result["notes"]
    assert result["sample_value"].startswith("***len=")


def test_redact_fields_returns_new_mapping() -> None:
    # Arrange
    fields = {"notes": "abc"}

    # Act
    result = redact_fields(fields)

    # Assert
    assert result is not fields
    assert fields["notes"] == "abc"

"""Tests for masked-value coercion to native COPY types."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest

from privaci.errors import MaskingError
from privaci.stream.coerce import coerce_value, table_needs_text_fallback


def _coerce(value: object, data_type: str) -> object:
    return coerce_value(value, data_type, column_path="public.t.c")


def test_date_string_becomes_date() -> None:
    # Act
    result = _coerce("1990-01-15", "date")

    # Assert
    assert result == dt.date(1990, 1, 15)


def test_integer_string_becomes_int() -> None:
    # Act & Assert
    assert _coerce("42", "integer") == 42


def test_numeric_string_becomes_decimal() -> None:
    # Act & Assert
    assert _coerce("12.50", "numeric(10,2)") == Decimal("12.50")


def test_uuid_string_becomes_uuid() -> None:
    # Arrange
    raw = "12345678-1234-4234-8234-1234567890ab"

    # Act
    result = _coerce(raw, "uuid")

    # Assert
    assert result == uuid.UUID(raw)


def test_text_value_passes_through() -> None:
    # Act & Assert
    assert _coerce("alex.rivera@fake.net", "character varying(255)") == (
        "alex.rivera@fake.net"
    )


def test_native_value_unchanged() -> None:
    # Arrange
    original = dt.date(2000, 5, 5)

    # Act & Assert
    assert _coerce(original, "date") is original


def test_none_passes_through() -> None:
    # Act & Assert
    assert _coerce(None, "date") is None


def test_invalid_value_for_type_raises_masking_error() -> None:
    # Act & Assert
    with pytest.raises(MaskingError) as exc_info:
        _coerce("deadbeef" * 8, "uuid")
    assert "incompatible" in str(exc_info.value)


def test_boolean_string_becomes_bool() -> None:
    # Act & Assert
    assert _coerce("true", "boolean") is True
    assert _coerce("false", "boolean") is False


def test_timestamp_string_becomes_datetime() -> None:
    # Act
    result = _coerce("2020-06-01T12:30:00", "timestamp without time zone")

    # Assert
    assert result == dt.datetime(2020, 6, 1, 12, 30, 0)


def test_bytea_hex_string_becomes_bytes() -> None:
    # Act
    result = _coerce("\\xdeadbeef", "bytea")

    # Assert
    assert result == b"\xde\xad\xbe\xef"


def test_invalid_boolean_raises_masking_error() -> None:
    # Act & Assert
    with pytest.raises(MaskingError):
        _coerce("maybe", "boolean")


def test_table_needs_text_fallback_for_ltree() -> None:
    # Arrange
    column_types = {"id": "bigint", "region_path": "ltree"}

    # Act & Assert
    assert table_needs_text_fallback(column_types) is True
    assert table_needs_text_fallback({"id": "bigint", "email": "text"}) is False

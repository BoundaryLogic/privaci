"""Unit tests for safe PostgreSQL identifier quoting."""

from __future__ import annotations

import pytest

from privaci.catalog.identifiers import (
    assert_safe_identifiers,
    qualify,
    quote_pg_identifier,
)
from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.errors import CatalogError


def test_quotes_plain_identifier() -> None:
    # Act & Assert
    assert quote_pg_identifier("users") == '"users"'


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('user"; DROP TABLE x', '"user""; DROP TABLE x"'),
        ('a"b"c', '"a""b""c"'),
        ('"', '""""'),
    ],
)
def test_doubles_embedded_quotes(raw: str, expected: str) -> None:
    # Act
    result = quote_pg_identifier(raw)

    # Assert
    assert result == expected


def test_rejects_empty_identifier() -> None:
    # Act & Assert
    with pytest.raises(CatalogError, match="empty identifier"):
        quote_pg_identifier("")


@pytest.mark.parametrize("bad", ["with\x00nul", "tab\tchar", "newline\n", "del\x7f"])
def test_rejects_control_characters(bad: str) -> None:
    # Act & Assert
    with pytest.raises(CatalogError, match="control character"):
        quote_pg_identifier(bad)


def test_qualify_quotes_both_parts() -> None:
    # Act & Assert
    assert qualify("public", "users") == '"public"."users"'


def _table(schema: str, name: str, columns: tuple[str, ...] = ()) -> TableInfo:
    cols = tuple(
        ColumnInfo(name=col, data_type="text", not_null=False) for col in columns
    )
    return TableInfo(schema_name=schema, table_name=name, columns=cols)


def test_assert_safe_identifiers_passes_clean_catalog() -> None:
    # Arrange
    tables = {"public.users": _table("public", "users", ("id", "email"))}

    # Act & Assert (no exception)
    assert_safe_identifiers(tables)


def test_assert_safe_identifiers_rejects_control_char_column() -> None:
    # Arrange
    tables = {"public.users": _table("public", "users", ("id\x00",))}

    # Act & Assert
    with pytest.raises(CatalogError, match="control character"):
        assert_safe_identifiers(tables)

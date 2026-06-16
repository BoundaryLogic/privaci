"""Unit tests for catalog model helpers."""

from __future__ import annotations

import pytest

from privaci.catalog.models import TableInfo, parse_table_id, table_id


def test_table_id_joins_schema_and_name() -> None:
    # Act & Assert
    assert table_id("public", "users") == "public.users"


def test_sql_ref_quotes_schema_and_table() -> None:
    # Arrange
    table = TableInfo(schema_name="public", table_name="users", columns=())

    # Act & Assert
    assert table.sql_ref == '"public"."users"'


def test_sql_ref_escapes_hostile_table_name() -> None:
    # Arrange
    table = TableInfo(schema_name="public", table_name='u"; DROP', columns=())

    # Act & Assert
    assert table.sql_ref == '"public"."u""; DROP"'


def test_parse_table_id_round_trips() -> None:
    # Act
    schema_name, table_name = parse_table_id("analytics.events")

    # Assert
    assert schema_name == "analytics"
    assert table_name == "events"


def test_parse_table_id_supports_dotted_schema_names() -> None:
    # Arrange
    identifier = table_id("analytics.prod", "events")

    # Act
    schema_name, table_name = parse_table_id(identifier)

    # Assert
    assert identifier == "analytics.prod.events"
    assert schema_name == "analytics.prod"
    assert table_name == "events"


def test_parse_table_id_rejects_missing_table() -> None:
    # Act & Assert
    with pytest.raises(ValueError, match="invalid table id"):
        parse_table_id("noschema")

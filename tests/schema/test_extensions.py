"""Tests for schema extension dependency detection."""

from __future__ import annotations

from privaci.catalog.graph import build_load_plan
from privaci.catalog.models import CatalogResult, ColumnInfo, TableInfo
from privaci.schema.extensions import emit_create_extension, required_extensions


def test_required_extensions_includes_ltree() -> None:
    # Arrange
    table = TableInfo(
        "public",
        "geo_locations",
        (
            ColumnInfo("id", "bigint", True),
            ColumnInfo("name", "text", True),
            ColumnInfo("region_path", "ltree", False),
        ),
    )
    catalog = CatalogResult(
        tables={table.identifier: table},
        load_plan=build_load_plan({table.identifier: table}),
    )

    # Act
    extensions = required_extensions(catalog)

    # Assert
    assert extensions == ["ltree"]


def test_emit_create_extension_is_idempotent() -> None:
    """Arrange / Act / Assert: extension DDL uses IF NOT EXISTS."""
    sql = emit_create_extension("ltree")

    assert sql == "CREATE EXTENSION IF NOT EXISTS ltree"

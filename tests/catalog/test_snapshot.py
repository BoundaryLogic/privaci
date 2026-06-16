"""Tests for canonical catalog snapshot serialization."""

from __future__ import annotations

from privaci.catalog.models import (
    CatalogResult,
    LoadLayer,
    LoadPlan,
    TableInfo,
    table_id,
)
from privaci.catalog.snapshot import canonical_snapshot_json


def test_canonical_snapshot_is_byte_identical_across_runs() -> None:
    # Arrange
    table = TableInfo(schema_name="public", table_name="users", columns=())
    catalog = CatalogResult(
        tables={table_id("public", "users"): table},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=("public.users",)),)),
        warnings=(),
    )

    # Act
    first = canonical_snapshot_json(catalog)
    second = canonical_snapshot_json(catalog)

    # Assert
    assert first == second
    assert '"public.users"' in first

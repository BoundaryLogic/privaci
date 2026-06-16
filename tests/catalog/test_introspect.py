"""Integration tests for live PostgreSQL catalog introspection."""

from __future__ import annotations

import pytest

from privaci.catalog import introspect_catalog
from privaci.catalog.snapshot import canonical_snapshot_json

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_introspect_acyclic_schema(catalog_schema: str) -> None:
    # Arrange
    import asyncpg

    conn = await asyncpg.connect(catalog_schema)

    # Act
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()

    # Assert
    assert "catalog_demo.orgs" in catalog.tables
    users = catalog.tables["catalog_demo.users"]
    assert users.primary_key == ("id",)
    assert any(fk.referenced_table == "orgs" for fk in users.foreign_keys)
    layer_ids = [list(layer.table_ids) for layer in catalog.load_plan.layers]
    orgs_index = next(
        i for i, layer in enumerate(layer_ids) if "catalog_demo.orgs" in layer
    )
    users_index = next(
        i for i, layer in enumerate(layer_ids) if "catalog_demo.users" in layer
    )
    assert orgs_index < users_index


async def test_introspect_self_referential_table(catalog_schema: str) -> None:
    # Arrange
    import asyncpg

    conn = await asyncpg.connect(catalog_schema)

    # Act
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()

    # Assert
    employees = catalog.tables["catalog_demo.employees"]
    assert employees.self_cycle is True


async def test_introspect_polymorphic_warning(catalog_schema: str) -> None:
    # Arrange
    import asyncpg

    conn = await asyncpg.connect(catalog_schema)

    # Act
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()

    # Assert
    assert any(
        warning.code == "polymorphic_fk_warning"
        and warning.table_id == "catalog_demo.comments"
        for warning in catalog.warnings
    )


async def test_snapshot_is_stable_for_unchanged_source(catalog_schema: str) -> None:
    # Arrange
    import asyncpg

    conn = await asyncpg.connect(catalog_schema)

    # Act
    try:
        first = canonical_snapshot_json(await introspect_catalog(conn))
        second = canonical_snapshot_json(await introspect_catalog(conn))
    finally:
        await conn.close()

    # Assert
    assert first == second


async def test_system_schemas_are_excluded(catalog_schema: str) -> None:
    # Arrange
    import asyncpg

    conn = await asyncpg.connect(catalog_schema)

    # Act
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()

    # Assert
    assert not any(
        table_id.startswith("pg_catalog.") or table_id.startswith("information_schema.")
        for table_id in catalog.tables
    )

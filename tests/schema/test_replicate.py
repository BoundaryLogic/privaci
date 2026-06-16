"""Tests for schema replication orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.graph import build_load_plan
from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    ForeignKeyInfo,
    TableInfo,
    table_id,
)
from privaci.config.models import Config, TableConfig
from privaci.errors import ConfigError, PreflightError
from privaci.schema.replicate import replicate_schema


def _catalog(*tables: TableInfo) -> CatalogResult:
    table_map = {table.identifier: table for table in tables}
    plan = build_load_plan(table_map)
    return CatalogResult(tables=table_map, load_plan=plan)


@pytest.fixture
def target_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.execute = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_replicate_schema_emits_ltree_extension_when_needed(
    target_conn: AsyncMock,
) -> None:
    # Arrange
    geo = TableInfo(
        "public",
        "geo_locations",
        (
            ColumnInfo("id", "bigint", True),
            ColumnInfo("region_path", "ltree", False),
        ),
    )
    catalog = _catalog(geo)
    config = Config(version="1.0")

    # Act
    await replicate_schema(target_conn, catalog, config)

    # Assert
    executed = " ".join(call.args[0] for call in target_conn.execute.await_args_list)
    assert "CREATE EXTENSION IF NOT EXISTS ltree" in executed


@pytest.mark.asyncio
async def test_replicate_schema_emits_ddl_in_load_order(
    target_conn: AsyncMock,
) -> None:
    # Arrange
    orgs = TableInfo("public", "orgs", (ColumnInfo("id", "integer", True),))
    users = TableInfo(
        "public",
        "users",
        (
            ColumnInfo("id", "integer", True),
            ColumnInfo("org_id", "integer", True),
        ),
        foreign_keys=(
            ForeignKeyInfo(
                name="users_org_fk",
                source_columns=("org_id",),
                referenced_schema="public",
                referenced_table="orgs",
                referenced_columns=("id",),
                on_delete="NO ACTION",
                on_update="NO ACTION",
                deferrable=True,
                initially_deferred=False,
            ),
        ),
    )
    catalog = _catalog(orgs, users)
    config = Config(version="1.0")

    # Act
    await replicate_schema(target_conn, catalog, config)

    # Assert
    executed = " ".join(call.args[0] for call in target_conn.execute.await_args_list)
    assert "CREATE SCHEMA" in executed
    assert "CREATE TABLE" in executed
    assert "FOREIGN KEY" in executed


@pytest.mark.asyncio
async def test_replicate_schema_skips_excluded_tables(
    target_conn: AsyncMock,
) -> None:
    # Arrange
    audit = TableInfo("audit", "events", (ColumnInfo("id", "integer", True),))
    catalog = _catalog(audit)
    config = Config(
        version="1.0",
        tables={table_id("audit", "events"): TableConfig(strategy="exclude")},
    )

    # Act
    await replicate_schema(target_conn, catalog, config)

    # Assert
    executed = " ".join(call.args[0] for call in target_conn.execute.await_args_list)
    assert "CREATE TABLE" not in executed


@pytest.mark.asyncio
async def test_replicate_schema_rejects_exclude_with_not_null_fk(
    target_conn: AsyncMock,
) -> None:
    # Arrange
    orgs = TableInfo("public", "orgs", (ColumnInfo("id", "integer", True),))
    users = TableInfo(
        "public",
        "users",
        (
            ColumnInfo("id", "integer", True),
            ColumnInfo("org_id", "integer", True),
        ),
        foreign_keys=(
            ForeignKeyInfo(
                name="users_org_fk",
                source_columns=("org_id",),
                referenced_schema="public",
                referenced_table="orgs",
                referenced_columns=("id",),
                on_delete="NO ACTION",
                on_update="NO ACTION",
                deferrable=True,
                initially_deferred=False,
            ),
        ),
    )
    catalog = _catalog(orgs, users)
    config = Config(
        version="1.0",
        tables={table_id("public", "orgs"): TableConfig(strategy="exclude")},
    )

    # Act / Assert
    with pytest.raises(ConfigError, match="NOT NULL FKs"):
        await replicate_schema(target_conn, catalog, config)


@pytest.mark.asyncio
async def test_replicate_schema_wraps_ddl_errors(
    target_conn: AsyncMock,
) -> None:
    # Arrange
    import asyncpg

    table = TableInfo("public", "users", (ColumnInfo("id", "integer", True),))
    catalog = _catalog(table)
    config = Config(version="1.0")
    target_conn.execute.side_effect = asyncpg.PostgresError("boom")

    # Act / Assert
    with pytest.raises(PreflightError, match="DDL execution failed"):
        await replicate_schema(target_conn, catalog, config)

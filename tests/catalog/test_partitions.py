"""Tests for native partitioning catalog metadata."""

from __future__ import annotations

import pytest

from privaci.catalog.models import TableInfo
from privaci.catalog.partitions import (
    config_table_id,
    should_skip_fk_edge,
    validate_no_subpartitioning,
)
from privaci.errors import CatalogError
from privaci.schema.ddl import emit_create_partition_child, emit_create_table

pytestmark_integration = pytest.mark.integration


def test_emit_create_table_appends_partition_by_clause() -> None:
    # Arrange
    table = TableInfo(
        schema_name="public",
        table_name="events",
        columns=(),
        is_partitioned=True,
        partition_key_def="RANGE (event_at)",
    )

    # Act
    ddl = emit_create_table(table)

    # Assert
    assert "PARTITION BY RANGE (event_at)" in ddl


def test_emit_create_partition_child_includes_bound() -> None:
    # Arrange
    parent = TableInfo(schema_name="public", table_name="events", columns=())
    child = TableInfo(
        schema_name="public",
        table_name="events_2024_01",
        columns=(),
        parent_partition="public.events",
        partition_bound="FOR VALUES FROM ('2024-01-01') TO ('2024-02-01')",
    )

    # Act
    ddl = emit_create_partition_child(child, parent)

    # Assert
    assert "PARTITION OF" in ddl
    assert "FOR VALUES FROM" in ddl


def test_validate_no_subpartitioning_raises() -> None:
    # Arrange
    tables = {
        "public.events_2024_01": TableInfo(
            schema_name="public",
            table_name="events_2024_01",
            columns=(),
            parent_partition="public.events",
            is_partitioned=True,
        )
    }

    # Act / Assert
    with pytest.raises(CatalogError, match="Sub-partitioned"):
        validate_no_subpartitioning(tables)


def test_config_table_id_prefers_parent_for_children() -> None:
    # Arrange
    child = TableInfo(
        schema_name="public",
        table_name="events_2024_01",
        columns=(),
        parent_partition="public.events",
    )

    # Assert
    assert config_table_id(child) == "public.events"
    assert should_skip_fk_edge(child) is True


@pytest.mark.asyncio
@pytestmark_integration
async def test_introspect_finds_partitioned_parents(
    source_dsn: str, postgres_available: None
) -> None:
    # Arrange
    from pathlib import Path

    import asyncpg

    from privaci.catalog import introspect_catalog
    from tests.integration.conftest import _apply_sql_dir

    sql_dir = Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "demo-corp"
    await _apply_sql_dir(source_dsn, sql_dir)

    conn = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()

    # Assert
    parent = catalog.tables["public.raw_events"]
    assert parent.is_partitioned is True
    assert parent.partition_strategy == "RANGE"
    assert len(parent.partition_children) == 24
    child = catalog.tables["public.raw_events_2024_01"]
    assert child.parent_partition == "public.raw_events"
    assert child.partition_bound is not None

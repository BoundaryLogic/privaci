"""Tests for snapshot persistence helper."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import (
    CatalogResult,
    LoadLayer,
    LoadPlan,
    TableInfo,
    table_id,
)
from privaci.catalog.snapshot import persist_source_schema_snapshot
from privaci.errors import StateError


@pytest.mark.asyncio
async def test_persist_source_schema_snapshot_writes_jsonb() -> None:
    # Arrange
    conn = AsyncMock()
    run_id = uuid.uuid4()
    catalog = CatalogResult(
        tables={table_id("public", "users"): TableInfo("public", "users", ())},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=("public.users",)),)),
    )

    # Act
    await persist_source_schema_snapshot(conn, run_id, catalog)

    # Assert
    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    assert args[1] == run_id


@pytest.mark.asyncio
async def test_persist_source_schema_snapshot_maps_db_errors() -> None:
    # Arrange
    import asyncpg

    conn = AsyncMock()
    conn.execute.side_effect = asyncpg.PostgresError("missing relation")
    catalog = CatalogResult(
        tables={},
        load_plan=LoadPlan(layers=()),
    )

    # Act & Assert
    with pytest.raises(StateError, match="source_schema_snapshot"):
        await persist_source_schema_snapshot(conn, uuid.uuid4(), catalog)

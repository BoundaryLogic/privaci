"""Tests for resume-time schema snapshot validation."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.catalog.snapshot import canonical_snapshot_json
from privaci.errors import PreflightError
from privaci.state.schema_snapshot import validate_resume_schema_snapshot


def _catalog(*tables: TableInfo) -> CatalogResult:
    table_map = {table.identifier: table for table in tables}
    return CatalogResult(
        tables=table_map,
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=tuple(table_map)),)),
    )


@pytest.mark.asyncio
async def test_validate_resume_schema_snapshot_accepts_matching_catalog() -> None:
    # Arrange
    users = TableInfo("public", "users", (ColumnInfo("id", "integer", True),))
    catalog = _catalog(users)
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "source_schema_snapshot": json.loads(canonical_snapshot_json(catalog)),
        }
    )

    # Act / Assert
    await validate_resume_schema_snapshot(conn, uuid.uuid4(), catalog)


@pytest.mark.asyncio
async def test_validate_resume_schema_snapshot_ignores_estimated_rows_drift() -> None:
    # Arrange — reltuples can move between run start and resume preflight.
    sparse = TableInfo(
        "public",
        "users",
        (ColumnInfo("id", "integer", True),),
        estimated_rows=-1.0,
    )
    dense = TableInfo(
        "public",
        "users",
        (ColumnInfo("id", "integer", True),),
        estimated_rows=10_000.0,
    )
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "source_schema_snapshot": json.loads(
                canonical_snapshot_json(_catalog(sparse))
            ),
        }
    )

    # Act / Assert
    await validate_resume_schema_snapshot(conn, uuid.uuid4(), _catalog(dense))


@pytest.mark.asyncio
async def test_validate_resume_schema_snapshot_rejects_drift() -> None:
    # Arrange
    users = TableInfo("public", "users", (ColumnInfo("id", "integer", True),))
    drifted = _catalog(
        TableInfo(
            "public",
            "users",
            (
                ColumnInfo("id", "integer", True),
                ColumnInfo("email", "text", False),
            ),
        )
    )
    conn = AsyncMock()
    stored_snapshot = json.loads(canonical_snapshot_json(_catalog(users)))
    conn.fetchrow = AsyncMock(
        return_value={"source_schema_snapshot": stored_snapshot},
    )

    # Act / Assert
    with pytest.raises(PreflightError, match="schema changed"):
        await validate_resume_schema_snapshot(conn, uuid.uuid4(), drifted)


@pytest.mark.asyncio
async def test_validate_resume_schema_snapshot_fails_when_missing_replicate() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"source_schema_snapshot": None})
    catalog = _catalog(TableInfo("public", "users", ()))

    # Act / Assert
    with pytest.raises(PreflightError, match="schema snapshot"):
        await validate_resume_schema_snapshot(
            conn, uuid.uuid4(), catalog, schema_mode="replicate"
        )


@pytest.mark.asyncio
async def test_validate_resume_schema_snapshot_skips_when_missing_assume() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"source_schema_snapshot": None})
    catalog = _catalog(TableInfo("public", "users", ()))

    # Act / Assert — assume_existing may resume without a snapshot
    await validate_resume_schema_snapshot(
        conn, uuid.uuid4(), catalog, schema_mode="assume_existing"
    )

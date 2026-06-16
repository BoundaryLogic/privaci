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
from privaci.catalog.snapshot import (
    canonical_snapshot_json,
    validate_resume_schema_snapshot,
)
from privaci.errors import PreflightError


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
async def test_validate_resume_schema_snapshot_skips_when_missing() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"source_schema_snapshot": None})
    catalog = _catalog(TableInfo("public", "users", ()))

    # Act / Assert
    await validate_resume_schema_snapshot(conn, uuid.uuid4(), catalog)

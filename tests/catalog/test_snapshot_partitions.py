"""Unit tests for partition snapshot diff helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import CatalogResult, LoadPlan, TableInfo
from privaci.catalog.snapshot import (
    find_new_partition_children,
    load_latest_schema_snapshot,
)


def _child(name: str, parent: str) -> TableInfo:
    schema, _, table_name = parent.partition(".")
    return TableInfo(
        schema_name=schema,
        table_name=name,
        columns=(),
        parent_partition=parent,
    )


def test_find_new_partition_children_returns_only_unknown_children() -> None:
    # Arrange
    catalog = CatalogResult(
        tables={
            "public.events": TableInfo(
                schema_name="public",
                table_name="events",
                columns=(),
                is_partitioned=True,
                partition_children=("public.events_2026_01",),
            ),
            "public.events_2025_12": _child("events_2025_12", "public.events"),
            "public.events_2026_01": _child("events_2026_01", "public.events"),
        },
        load_plan=LoadPlan(layers=()),
    )
    previous = {
        "tables": {
            "public.events": {},
            "public.events_2025_12": {},
        }
    }

    # Act
    new_children = find_new_partition_children(previous, catalog)

    # Assert
    assert [child.identifier for child in new_children] == ["public.events_2026_01"]


def test_find_new_partition_children_without_previous_snapshot() -> None:
    # Arrange
    catalog = CatalogResult(
        tables={
            "public.events_2026_01": _child("events_2026_01", "public.events"),
        },
        load_plan=LoadPlan(layers=()),
    )

    # Act / Assert
    assert find_new_partition_children(None, catalog) == ()


@pytest.mark.asyncio
async def test_load_latest_schema_snapshot_parses_jsonb_row() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "source_schema_snapshot": {"tables": {"public.t": {}}}
    }

    # Act
    snapshot = await load_latest_schema_snapshot(
        conn,
        source_db_hash="deadbeef",
        exclude_run_id=None,
    )

    # Assert
    assert snapshot == {"tables": {"public.t": {}}}

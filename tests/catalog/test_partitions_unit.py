"""Unit tests for partition metadata attachment."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import TableInfo, table_id
from privaci.catalog.partitions import attach_partition_metadata


class _FakeRecord(dict[str, Any]):
    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(key)


@pytest.mark.asyncio
async def test_attach_partition_metadata_enriches_parent_and_children() -> None:
    # Arrange
    conn = AsyncMock()
    parent_id = table_id("public", "events")
    child_id = table_id("public", "events_2026_01")
    tables = {
        parent_id: TableInfo(schema_name="public", table_name="events", columns=()),
        child_id: TableInfo(
            schema_name="public",
            table_name="events_2026_01",
            columns=(),
        ),
    }
    conn.fetch.side_effect = [
        [
            _FakeRecord(
                schema_name="public",
                parent_table="events",
                partition_strategy="r",
                partition_key_def="RANGE (event_at)",
            )
        ],
        [
            _FakeRecord(
                schema_name="public",
                parent_table="events",
                child_table="events_2026_01",
                partition_bound="FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')",
                is_sub_partitioned=False,
            )
        ],
    ]

    # Act
    warnings = await attach_partition_metadata(conn, tables)

    # Assert
    assert warnings == ()
    parent = tables[parent_id]
    assert parent.is_partitioned is True
    assert parent.partition_strategy == "RANGE"
    assert parent.partition_children == (child_id,)
    child = tables[child_id]
    assert child.parent_partition == parent_id
    assert child.partition_bound is not None

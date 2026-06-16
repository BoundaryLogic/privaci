"""Tests for per-table empty/truncate strategy helpers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.schema.strategies import (
    finalize_empty_strategy_table,
    truncate_target_table,
)


@pytest.fixture
def users_table() -> TableInfo:
    return TableInfo(
        schema_name="public",
        table_name="audit_logs",
        columns=(ColumnInfo(name="id", data_type="integer", not_null=True),),
        primary_key=("id",),
    )


@pytest.mark.asyncio
async def test_truncate_target_table_executes_truncate(users_table: TableInfo) -> None:
    # Arrange
    conn = AsyncMock()

    # Act
    await truncate_target_table(conn, users_table)

    # Assert
    conn.execute.assert_awaited_once_with('TRUNCATE "public"."audit_logs"')


@pytest.mark.asyncio
async def test_finalize_empty_strategy_table_marks_done_without_truncate(
    users_table: TableInfo,
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    conn = AsyncMock()
    write_checkpoint = mocker.patch(
        "privaci.schema.strategies.write_checkpoint",
        new_callable=AsyncMock,
    )
    mark_done = mocker.patch(
        "privaci.schema.strategies.mark_table_done",
        new_callable=AsyncMock,
    )
    run_id = uuid.uuid4()

    # Act
    rows = await finalize_empty_strategy_table(
        conn,
        users_table,
        run_id,
        strategy="empty",
    )

    # Assert
    assert rows == 0
    conn.execute.assert_not_awaited()
    write_checkpoint.assert_awaited_once()
    mark_done.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_empty_strategy_table_truncates_for_truncate_strategy(
    users_table: TableInfo,
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    conn = AsyncMock()
    mocker.patch("privaci.schema.strategies.write_checkpoint", new_callable=AsyncMock)
    mocker.patch("privaci.schema.strategies.mark_table_done", new_callable=AsyncMock)

    # Act
    await finalize_empty_strategy_table(
        conn,
        users_table,
        uuid.uuid4(),
        strategy="truncate",
    )

    # Assert
    conn.execute.assert_awaited_once_with('TRUNCATE "public"."audit_logs"')

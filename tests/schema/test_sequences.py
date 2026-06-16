"""Unit tests for identity/serial sequence synchronization."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.schema.sequences import sequence_columns, sync_table_sequences


def test_sequence_columns_returns_only_backed_columns() -> None:
    # Arrange
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(
                name="id",
                data_type="bigint",
                not_null=True,
                is_identity=True,
                identity_generation="ALWAYS",
                sequence_name="public.users_id_seq",
            ),
            ColumnInfo(name="email", data_type="text", not_null=True),
        ),
    )

    # Act
    columns = sequence_columns(table)

    # Assert
    assert [column.name for column in columns] == ["id"]


@pytest.mark.asyncio
async def test_sync_table_sequences_sets_max_value() -> None:
    # Arrange
    conn = AsyncMock()
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(
                name="id",
                data_type="bigint",
                not_null=True,
                is_identity=True,
                identity_generation="ALWAYS",
                sequence_name="public.users_id_seq",
            ),
        ),
    )

    # Act
    await sync_table_sequences(conn, table, {"id": 42})

    # Assert
    conn.execute.assert_awaited_once_with(
        "SELECT setval($1::regclass, $2::bigint, true)",
        "public.users_id_seq",
        42,
    )


@pytest.mark.asyncio
async def test_sync_table_sequences_defaults_empty_table_to_one() -> None:
    # Arrange
    conn = AsyncMock()
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(
                name="id",
                data_type="bigint",
                not_null=True,
                uses_serial=True,
                sequence_name="public.users_id_seq",
            ),
        ),
    )

    # Act
    await sync_table_sequences(conn, table, {"id": None})

    # Assert
    conn.execute.assert_awaited_once_with(
        "SELECT setval($1::regclass, 1, false)",
        "public.users_id_seq",
    )

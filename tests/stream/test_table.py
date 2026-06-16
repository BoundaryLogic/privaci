"""Tests for table streaming with mocked asyncpg."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.config.actions import FakeAction
from privaci.config.models import TableConfig
from privaci.mask.engine import MaskingEngine
from privaci.stream.table import stream_table
from tests.fixtures.constants import TEST_SALT


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> bool:
        return False


def _patch_write_checkpoint(mocker: pytest.MockFixture) -> AsyncMock:
    """Patch checkpoint writes in both the seed and batch-write modules."""
    mock = AsyncMock()
    mocker.patch("privaci.stream.table.write_checkpoint", mock)
    mocker.patch("privaci.stream.batch_write.write_checkpoint", mock)
    return mock


def _users_table() -> TableInfo:
    return TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="email", data_type="text", not_null=True),
        ),
        primary_key=("id",),
    )


@pytest.fixture
def source_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {"id": 1, "email": "a@b.com"},
                {"id": 2, "email": "c@d.com"},
            ],
            [],
        ]
    )
    return conn


@pytest.fixture
def target_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_FakeTransaction())
    conn.copy_records_to_table = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_stream_table_masks_and_checkpoints_batches(
    source_conn: AsyncMock,
    target_conn: AsyncMock,
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    table = _users_table()
    table_cfg = TableConfig(
        columns={"email": FakeAction(action="fake", provider="email")},
    )
    engine = MaskingEngine(TEST_SALT, table.identifier, table, table_cfg)
    run_id = uuid.uuid4()
    write_checkpoint = _patch_write_checkpoint(mocker)
    mark_done = mocker.patch(
        "privaci.stream.table.mark_table_done",
        new_callable=AsyncMock,
    )

    # Act
    total = await stream_table(
        source_conn,
        target_conn,
        table,
        engine,
        run_id=run_id,
        batch_size=100,
        table_config=table_cfg,
    )

    # Assert
    assert total == 2
    target_conn.copy_records_to_table.assert_awaited_once()
    assert write_checkpoint.await_count == 2
    mark_done.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_table_empty_masked_table_seeds_checkpoint(
    target_conn: AsyncMock,
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    table = _users_table()
    table_cfg = TableConfig(
        columns={"email": FakeAction(action="fake", provider="email")},
    )
    source_conn = AsyncMock()
    source_conn.fetch = AsyncMock(return_value=[])
    engine = MaskingEngine(TEST_SALT, table.identifier, table, table_cfg)
    write_checkpoint = _patch_write_checkpoint(mocker)
    mark_done = mocker.patch(
        "privaci.stream.table.mark_table_done",
        new_callable=AsyncMock,
    )

    # Act
    total = await stream_table(
        source_conn,
        target_conn,
        table,
        engine,
        run_id=uuid.uuid4(),
        batch_size=100,
        table_config=table_cfg,
    )

    # Assert
    assert total == 0
    write_checkpoint.assert_awaited_once()
    mark_done.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_table_outer_transaction_skips_nested_txn(
    source_conn: AsyncMock,
    target_conn: AsyncMock,
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    table = _users_table()
    table_cfg = TableConfig(
        columns={"email": FakeAction(action="fake", provider="email")},
    )
    engine = MaskingEngine(TEST_SALT, table.identifier, table, table_cfg)
    mocker.patch("privaci.stream.table.write_checkpoint", new_callable=AsyncMock)
    mocker.patch("privaci.stream.table.mark_table_done", new_callable=AsyncMock)

    # Act
    await stream_table(
        source_conn,
        target_conn,
        table,
        engine,
        run_id=uuid.uuid4(),
        batch_size=100,
        outer_transaction=True,
        table_config=table_cfg,
    )

    # Assert
    target_conn.transaction.assert_not_called()


@pytest.mark.asyncio
async def test_stream_table_emits_binary_fallback_audit_for_ltree(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    table = TableInfo(
        schema_name="public",
        table_name="geo_locations",
        columns=(
            ColumnInfo(name="id", data_type="bigint", not_null=True),
            ColumnInfo(name="region_path", data_type="ltree", not_null=False),
        ),
        primary_key=("id",),
    )
    source_conn = AsyncMock()
    source_conn.fetch = AsyncMock(side_effect=[[{"id": 1, "region_path": "a.b"}], []])
    target_conn = AsyncMock()
    target_conn.transaction = MagicMock(return_value=_FakeTransaction())
    target_conn.executemany = AsyncMock()
    engine = MaskingEngine(TEST_SALT, table.identifier, table, TableConfig())
    audit = AsyncMock()
    audit.enabled = True
    mocker.patch("privaci.stream.table.write_checkpoint", new_callable=AsyncMock)
    mocker.patch("privaci.stream.table.mark_table_done", new_callable=AsyncMock)
    write_audit = mocker.patch(
        "privaci.stream.table._write_binary_fallback_audit",
        new_callable=AsyncMock,
    )

    # Act
    await stream_table(
        source_conn,
        target_conn,
        table,
        engine,
        run_id=uuid.uuid4(),
        batch_size=100,
        audit=audit,
    )

    # Assert
    write_audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_table_uses_text_insert_for_ltree_columns(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    table = TableInfo(
        schema_name="public",
        table_name="geo_locations",
        columns=(
            ColumnInfo(name="id", data_type="bigint", not_null=True),
            ColumnInfo(name="name", data_type="text", not_null=True),
            ColumnInfo(name="region_path", data_type="ltree", not_null=False),
        ),
        primary_key=("id",),
    )
    source_conn = AsyncMock()
    source_conn.fetch = AsyncMock(
        side_effect=[[{"id": 1, "name": "R1", "region_path": "us.east.1"}], []]
    )
    target_conn = AsyncMock()
    target_conn.transaction = MagicMock(return_value=_FakeTransaction())
    target_conn.copy_records_to_table = AsyncMock()
    target_conn.executemany = AsyncMock()
    engine = MaskingEngine(TEST_SALT, table.identifier, table, TableConfig())
    mocker.patch("privaci.stream.table.write_checkpoint", new_callable=AsyncMock)
    mocker.patch("privaci.stream.table.mark_table_done", new_callable=AsyncMock)

    # Act
    await stream_table(
        source_conn,
        target_conn,
        table,
        engine,
        run_id=uuid.uuid4(),
        batch_size=100,
    )

    # Assert
    target_conn.executemany.assert_awaited_once()
    target_conn.copy_records_to_table.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_table_overrides_generated_always_identity(
    mocker: pytest.MockFixture,
) -> None:
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
        primary_key=("id",),
    )
    source_conn = AsyncMock()
    source_conn.fetch = AsyncMock(side_effect=[[{"id": 1, "email": "a@b.com"}], []])
    target_conn = AsyncMock()
    target_conn.transaction = MagicMock(return_value=_FakeTransaction())
    target_conn.copy_records_to_table = AsyncMock()
    target_conn.executemany = AsyncMock()
    engine = MaskingEngine(TEST_SALT, table.identifier, table, TableConfig())
    mocker.patch("privaci.stream.table.write_checkpoint", new_callable=AsyncMock)
    mocker.patch("privaci.stream.table.mark_table_done", new_callable=AsyncMock)
    mocker.patch("privaci.stream.table.sync_table_sequences", new_callable=AsyncMock)

    # Act
    await stream_table(
        source_conn,
        target_conn,
        table,
        engine,
        run_id=uuid.uuid4(),
        batch_size=100,
    )

    # Assert
    target_conn.executemany.assert_awaited_once()
    insert_sql = target_conn.executemany.await_args.args[0]
    assert "OVERRIDING SYSTEM VALUE" in insert_sql
    target_conn.copy_records_to_table.assert_not_awaited()

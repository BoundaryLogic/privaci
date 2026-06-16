"""Unit tests for per-table checkpoint writes."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import asyncpg
import pytest

from privaci.errors import StateError
from privaci.state.checkpoints import mark_table_done, write_checkpoint
from privaci.state.models import CheckpointStatus


async def test_write_checkpoint_passes_batch_delta(
    fake_conn: AsyncMock,
) -> None:
    # Arrange
    run_id = uuid.uuid4()

    # Act
    await write_checkpoint(
        fake_conn,
        run_id,
        "public",
        "users",
        last_pk_value="4242",
        rows_in_batch=10_000,
    )

    # Assert
    args = fake_conn.execute.await_args.args  # args[0] is the SQL string
    assert args[1] == run_id
    assert args[2] == "public"
    assert args[3] == "users"
    assert args[4] == CheckpointStatus.IN_PROGRESS.value
    assert args[5] == "4242"
    assert args[6] == 10_000


async def test_write_checkpoint_allows_table_level_null_pk(
    fake_conn: AsyncMock,
) -> None:
    # Act
    await write_checkpoint(
        fake_conn,
        uuid.uuid4(),
        "public",
        "events",
        last_pk_value=None,
        rows_in_batch=500,
    )

    # Assert
    args = fake_conn.execute.await_args.args  # args[0] is the SQL string
    assert args[5] is None


async def test_write_checkpoint_maps_db_error(fake_conn: AsyncMock) -> None:
    # Arrange
    fake_conn.execute.side_effect = asyncpg.PostgresError("boom")

    # Act / Assert
    with pytest.raises(StateError, match="checkpoint row could not be written"):
        await write_checkpoint(
            fake_conn,
            uuid.uuid4(),
            "public",
            "users",
            last_pk_value="1",
            rows_in_batch=1,
        )


async def test_mark_table_done_sets_done_status(fake_conn: AsyncMock) -> None:
    # Act
    await mark_table_done(fake_conn, uuid.uuid4(), "public", "users")

    # Assert
    args = fake_conn.execute.await_args.args  # args[0] is the SQL string
    assert args[4] == CheckpointStatus.DONE.value


async def test_mark_table_done_raises_when_no_row_updated(fake_conn: AsyncMock) -> None:
    # Arrange
    fake_conn.execute = AsyncMock(return_value="UPDATE 0")

    # Act / Assert
    with pytest.raises(StateError, match="No checkpoint row matched"):
        await mark_table_done(fake_conn, uuid.uuid4(), "public", "users")


async def test_mark_table_done_maps_db_error(fake_conn: AsyncMock) -> None:
    # Arrange
    fake_conn.execute.side_effect = asyncpg.PostgresError("boom")

    # Act / Assert
    with pytest.raises(StateError, match="checkpoint row could not be updated"):
        await mark_table_done(fake_conn, uuid.uuid4(), "public", "users")

"""Unit tests for run-lifecycle writes."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import asyncpg
import pytest

from privaci.errors import StateError
from privaci.state.models import RunIdentity, RunStatus
from privaci.state.runs import finish_run, start_run


def _identity() -> RunIdentity:
    return RunIdentity(
        config_hash="c" * 64,
        salt_fingerprint="s" * 16,
        source_db_hash="d" * 64,
    )


async def test_start_run_inserts_in_progress_and_returns_uuid7(
    fake_conn: AsyncMock,
) -> None:
    # Act
    run_id = await start_run(fake_conn, _identity())

    # Assert
    assert run_id.version == 7
    fake_conn.execute.assert_awaited_once()
    args = fake_conn.execute.await_args.args  # args[0] is the SQL string
    assert args[1] == run_id
    assert args[2] == RunStatus.IN_PROGRESS.value
    assert args[4] == "c" * 64


async def test_start_run_maps_db_error(fake_conn: AsyncMock) -> None:
    # Arrange
    fake_conn.execute.side_effect = asyncpg.PostgresError("boom")

    # Act / Assert
    with pytest.raises(StateError, match="run row could not be inserted"):
        await start_run(fake_conn, _identity())


async def test_finish_run_sets_terminal_status(fake_conn: AsyncMock) -> None:
    # Arrange
    run_id = uuid.uuid4()

    # Act
    await finish_run(fake_conn, run_id, RunStatus.SUCCEEDED, summary={"rows": 10})

    # Assert
    args = fake_conn.execute.await_args.args  # args[0] is the SQL string
    assert args[1] == run_id
    assert args[2] == RunStatus.SUCCEEDED.value
    assert '"rows"' in args[3]


async def test_finish_run_rejects_non_terminal_status(
    fake_conn: AsyncMock,
) -> None:
    # Act / Assert
    with pytest.raises(StateError, match="terminal status is required"):
        await finish_run(fake_conn, uuid.uuid4(), RunStatus.IN_PROGRESS)
    fake_conn.execute.assert_not_awaited()


async def test_finish_run_allows_null_summary(fake_conn: AsyncMock) -> None:
    # Act
    await finish_run(fake_conn, uuid.uuid4(), RunStatus.INTERRUPTED)

    # Assert
    args = fake_conn.execute.await_args.args  # args[0] is the SQL string
    assert args[3] is None


async def test_finish_run_maps_db_error(fake_conn: AsyncMock) -> None:
    # Arrange
    fake_conn.execute.side_effect = asyncpg.PostgresError("boom")

    # Act / Assert
    with pytest.raises(StateError, match="run row could not be updated"):
        await finish_run(fake_conn, uuid.uuid4(), RunStatus.FAILED)

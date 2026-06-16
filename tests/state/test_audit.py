"""Unit tests for the audit-log writer and its opt-out switch."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import asyncpg
import pytest

from privaci.errors import StateError
from privaci.state.audit import AuditWriter
from privaci.state.models import AuditLevel, EventType


async def test_disabled_writer_is_a_noop(fake_conn: AsyncMock) -> None:
    # Arrange
    writer = AuditWriter(uuid.uuid4(), enabled=False)

    # Act
    await writer.write(fake_conn, EventType.COLUMN_MASKED)

    # Assert
    fake_conn.execute.assert_not_awaited()


async def test_enabled_writer_inserts_event(fake_conn: AsyncMock) -> None:
    # Arrange
    run_id = uuid.uuid4()
    writer = AuditWriter(run_id, enabled=True)

    # Act
    await writer.write(
        fake_conn,
        EventType.COLUMN_MASKED,
        table_name="users",
        column_name="email",
        payload={"action": "fake", "rows_affected": 100},
    )

    # Assert
    args = fake_conn.execute.await_args.args  # args[0] is the SQL string
    assert args[2] == run_id
    assert args[3] == AuditLevel.INFO.value
    assert args[4] == EventType.COLUMN_MASKED.value
    assert args[6] == "users"
    assert args[7] == "email"
    assert json.loads(args[8]) == {"action": "fake", "rows_affected": 100}


async def test_writer_defaults_empty_payload(fake_conn: AsyncMock) -> None:
    # Arrange
    writer = AuditWriter(uuid.uuid4(), enabled=True)

    # Act
    await writer.write(fake_conn, EventType.CYCLE_BREAK)

    # Assert
    args = fake_conn.execute.await_args.args  # args[0] is the SQL string
    assert json.loads(args[8]) == {}


async def test_writer_maps_db_error(fake_conn: AsyncMock) -> None:
    # Arrange
    fake_conn.execute.side_effect = asyncpg.PostgresError("boom")
    writer = AuditWriter(uuid.uuid4(), enabled=True)

    # Act / Assert
    with pytest.raises(StateError, match="audit row could not be written"):
        await writer.write(fake_conn, EventType.COLUMN_MASKED)


def test_writer_repr_shows_enabled_state() -> None:
    # Arrange
    writer = AuditWriter(uuid.uuid4(), enabled=True)

    # Act / Assert
    assert "enabled=True" in repr(writer)

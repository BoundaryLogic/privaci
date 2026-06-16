"""Unit tests for idempotent state-schema creation and version gating."""

from __future__ import annotations

from unittest.mock import AsyncMock

import asyncpg
import pytest

from privaci.errors import StateError
from privaci.state.ddl import DDL_STATEMENTS, STATE_SCHEMA_VERSION
from privaci.state.schema import ensure_state_schema


async def test_ensure_state_schema_runs_all_ddl(fake_conn: AsyncMock) -> None:
    # Arrange
    fake_conn.fetchval.return_value = STATE_SCHEMA_VERSION

    # Act
    await ensure_state_schema(fake_conn)

    # Assert — every DDL statement plus the version insert executed.
    assert fake_conn.execute.await_count == len(DDL_STATEMENTS) + 1


async def test_ensure_state_schema_is_idempotent_on_existing(
    fake_conn: AsyncMock,
) -> None:
    # Arrange — schema already at the current version.
    fake_conn.fetchval.return_value = STATE_SCHEMA_VERSION

    # Act
    await ensure_state_schema(fake_conn)
    await ensure_state_schema(fake_conn)

    # Assert — no error; version read each time.
    assert fake_conn.fetchval.await_count == 2


async def test_ensure_state_schema_rejects_future_version(
    fake_conn: AsyncMock,
) -> None:
    # Arrange
    fake_conn.fetchval.return_value = STATE_SCHEMA_VERSION + 1

    # Act / Assert
    with pytest.raises(StateError, match="newer engine") as exc_info:
        await ensure_state_schema(fake_conn)
    assert exc_info.value.exit_code == 2


async def test_ensure_state_schema_maps_privilege_error(
    fake_conn: AsyncMock,
) -> None:
    # Arrange
    fake_conn.execute.side_effect = asyncpg.InsufficientPrivilegeError(
        "permission denied"
    )

    # Act / Assert
    with pytest.raises(StateError, match="CREATE") as exc_info:
        await ensure_state_schema(fake_conn)
    assert exc_info.value.exit_code == 2


async def test_ensure_state_schema_maps_generic_db_error(
    fake_conn: AsyncMock,
) -> None:
    # Arrange
    fake_conn.execute.side_effect = asyncpg.PostgresError("boom")

    # Act / Assert
    with pytest.raises(StateError, match="state schema could not be created"):
        await ensure_state_schema(fake_conn)

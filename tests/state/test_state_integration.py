"""Integration tests for the ``_privaci`` state schema against real Postgres.

Run with: ``pytest -m integration`` while ``compose.dev.yml`` is up.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest

from privaci.state import (
    AuditWriter,
    CheckpointStatus,
    EventType,
    RunIdentity,
    RunStatus,
    ensure_state_schema,
    finish_run,
    mark_table_done,
    start_run,
    write_checkpoint,
)
from privaci.state.ddl import STATE_SCHEMA_VERSION

pytestmark = pytest.mark.integration


def _identity() -> RunIdentity:
    return RunIdentity(
        config_hash="c" * 64,
        salt_fingerprint="s" * 16,
        source_db_hash="d" * 64,
    )


@pytest.fixture
async def state_conn(
    target_dsn: str, postgres_available: None
) -> AsyncIterator[asyncpg.Connection]:
    """Connect to target, reset ``_privaci``, yield, then clean up."""
    conn = await asyncpg.connect(target_dsn)
    try:
        await conn.execute("DROP SCHEMA IF EXISTS _privaci CASCADE")
        yield conn
    finally:
        await conn.execute("DROP SCHEMA IF EXISTS _privaci CASCADE")
        await conn.close()


async def test_ensure_state_schema_creates_tables(
    state_conn: asyncpg.Connection,
) -> None:
    # Act
    await ensure_state_schema(state_conn)

    # Assert
    tables = await state_conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = '_privaci'"
    )
    names = {row["table_name"] for row in tables}
    assert {"runs", "table_checkpoints", "audit_log"} <= names


async def test_ensure_state_schema_is_idempotent(
    state_conn: asyncpg.Connection,
) -> None:
    # Act — two calls must not error and must keep a single version row.
    await ensure_state_schema(state_conn)
    await ensure_state_schema(state_conn)

    # Assert
    version = await state_conn.fetchval(
        "SELECT schema_version FROM _privaci.schema_metadata"
    )
    assert version == STATE_SCHEMA_VERSION


async def test_run_lifecycle_insert_then_update(
    state_conn: asyncpg.Connection,
) -> None:
    # Arrange
    await ensure_state_schema(state_conn)

    # Act
    run_id = await start_run(state_conn, _identity())
    status_started = await state_conn.fetchval(
        "SELECT status FROM _privaci.runs WHERE run_id = $1", run_id
    )
    await finish_run(state_conn, run_id, RunStatus.SUCCEEDED, summary={"tables": 3})
    row = await state_conn.fetchrow(
        "SELECT status, ended_at, summary FROM _privaci.runs " "WHERE run_id = $1",
        run_id,
    )

    # Assert
    assert status_started == RunStatus.IN_PROGRESS.value
    assert row["status"] == RunStatus.SUCCEEDED.value
    assert row["ended_at"] is not None
    assert row["summary"] == '{"tables": 3}'


async def test_checkpoint_accumulates_rows(
    state_conn: asyncpg.Connection,
) -> None:
    # Arrange
    await ensure_state_schema(state_conn)
    run_id = await start_run(state_conn, _identity())

    # Act — two batches against the same table accumulate rows_processed.
    await write_checkpoint(
        state_conn,
        run_id,
        "public",
        "users",
        last_pk_value="100",
        rows_in_batch=100,
    )
    await write_checkpoint(
        state_conn,
        run_id,
        "public",
        "users",
        last_pk_value="250",
        rows_in_batch=150,
    )
    await mark_table_done(state_conn, run_id, "public", "users")
    row = await state_conn.fetchrow(
        "SELECT status, last_pk_value, rows_processed "
        "FROM _privaci.table_checkpoints "
        "WHERE run_id = $1 AND schema_name = 'public' AND table_name = 'users'",
        run_id,
    )

    # Assert
    assert row["rows_processed"] == 250
    assert row["last_pk_value"] == "250"
    assert row["status"] == CheckpointStatus.DONE.value


async def test_audit_writer_inserts_and_opt_out_skips(
    state_conn: asyncpg.Connection,
) -> None:
    # Arrange
    await ensure_state_schema(state_conn)
    run_id = await start_run(state_conn, _identity())

    # Act
    enabled = AuditWriter(run_id, enabled=True)
    await enabled.write(
        state_conn,
        EventType.COLUMN_MASKED,
        table_name="users",
        column_name="email",
        payload={"action": "fake", "rows_affected": 5},
    )
    disabled = AuditWriter(run_id, enabled=False)
    await disabled.write(state_conn, EventType.COLUMN_MASKED)

    count = await state_conn.fetchval(
        "SELECT count(*) FROM _privaci.audit_log WHERE run_id = $1", run_id
    )

    # Assert — only the enabled write persisted.
    assert count == 1


async def test_future_schema_version_is_rejected(
    state_conn: asyncpg.Connection,
) -> None:
    # Arrange — simulate a newer engine having initialized the schema.
    await ensure_state_schema(state_conn)
    await state_conn.execute(
        "UPDATE _privaci.schema_metadata SET schema_version = $1",
        STATE_SCHEMA_VERSION + 1,
    )

    # Act / Assert
    with pytest.raises(Exception, match="newer engine"):
        await ensure_state_schema(state_conn)

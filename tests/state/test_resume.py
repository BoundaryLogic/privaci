"""Tests for resume gate helpers."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from privaci.errors import PreflightError, StateError
from privaci.state.models import CheckpointStatus, RunIdentity
from privaci.state.resume import (
    ensure_table_resumable,
    parse_checkpoint_cursor,
    reopen_resumable_run,
    require_resumable_run,
    resolve_resumable_run,
)


class _FakeTransaction:
    async def __aenter__(self) -> _FakeTransaction:
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False


class _FakeConnection:
    """Minimal asyncpg-shaped stub for resume-gate unit tests."""

    def __init__(
        self,
        *,
        find_row: dict[str, Any] | None,
        latest_row: dict[str, Any] | None = None,
        checkpoint_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self._find_row = find_row
        self._latest_row = latest_row
        self._checkpoint_rows = checkpoint_rows or []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        if "config_hash = $2" in sql:
            return self._find_row
        return self._latest_row

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        return self._checkpoint_rows

    async def execute(self, sql: str, *args: Any) -> None:
        self.executed.append((sql, args))

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()


_IDENTITY = RunIdentity(
    config_hash="cfg", salt_fingerprint="salt", source_db_hash="src"
)


@pytest.mark.asyncio
async def test_require_resumable_run_rejects_when_no_run_exists() -> None:
    # Arrange
    conn = _FakeConnection(find_row=None, latest_row=None)

    # Act / Assert
    with pytest.raises(PreflightError, match="No incomplete run was found"):
        await require_resumable_run(conn, _IDENTITY)  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("latest_row", "expected"),
    [
        (
            {
                "config_hash": "other",
                "source_db_hash": "src",
                "salt_fingerprint": "salt",
            },
            "config changed",
        ),
        (
            {
                "config_hash": "cfg",
                "source_db_hash": "other",
                "salt_fingerprint": "salt",
            },
            "source database identity changed",
        ),
        (
            {
                "config_hash": "cfg",
                "source_db_hash": "src",
                "salt_fingerprint": "other",
            },
            "anonymization salt changed",
        ),
    ],
)
async def test_require_resumable_run_reports_distinct_drift(
    latest_row: dict[str, Any], expected: str
) -> None:
    # Arrange
    conn = _FakeConnection(find_row=None, latest_row=latest_row)

    # Act / Assert
    with pytest.raises(PreflightError, match=expected):
        await require_resumable_run(conn, _IDENTITY)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_require_resumable_run_reopens_and_returns_checkpoints() -> None:
    # Arrange
    run_id = uuid.uuid4()
    conn = _FakeConnection(
        find_row={"run_id": run_id},
        checkpoint_rows=[
            {
                "schema_name": "public",
                "table_name": "users",
                "status": CheckpointStatus.IN_PROGRESS.value,
                "last_pk_value": "10",
                "rows_processed": 10,
            }
        ],
    )

    # Act
    resolved_id, checkpoints = await require_resumable_run(conn, _IDENTITY)  # type: ignore[arg-type]

    # Assert
    assert resolved_id == run_id
    assert checkpoints["public.users"].last_pk_value == "10"
    assert conn.executed, "expected the run to be re-opened"
    reopen_sql, reopen_args = conn.executed[0]
    assert "ended_at = NULL" in reopen_sql
    assert reopen_args[0] == run_id
    assert reopen_args[1] == "in_progress"


@pytest.mark.asyncio
async def test_resolve_resumable_run_does_not_reopen() -> None:
    # Arrange
    run_id = uuid.uuid4()
    conn = _FakeConnection(find_row={"run_id": run_id})

    # Act
    resolved_id = await resolve_resumable_run(conn, _IDENTITY)  # type: ignore[arg-type]

    # Assert
    assert resolved_id == run_id
    assert conn.executed == [], "resolve must not mutate the run row"


@pytest.mark.asyncio
async def test_resolve_resumable_run_rejects_when_no_run_exists() -> None:
    # Arrange
    conn = _FakeConnection(find_row=None, latest_row=None)

    # Act / Assert
    with pytest.raises(PreflightError, match="No incomplete run was found"):
        await resolve_resumable_run(conn, _IDENTITY)  # type: ignore[arg-type]
    assert conn.executed == []


@pytest.mark.asyncio
async def test_reopen_resumable_run_reopens_and_loads_checkpoints() -> None:
    # Arrange
    run_id = uuid.uuid4()
    conn = _FakeConnection(
        find_row={"run_id": run_id},
        checkpoint_rows=[
            {
                "schema_name": "public",
                "table_name": "users",
                "status": CheckpointStatus.IN_PROGRESS.value,
                "last_pk_value": "10",
                "rows_processed": 10,
            }
        ],
    )

    # Act
    checkpoints = await reopen_resumable_run(conn, run_id)  # type: ignore[arg-type]

    # Assert
    assert checkpoints["public.users"].last_pk_value == "10"
    reopen_sql, reopen_args = conn.executed[0]
    assert "ended_at = NULL" in reopen_sql
    assert reopen_args[0] == run_id
    assert reopen_args[1] == "in_progress"


def test_parse_checkpoint_cursor_coerces_integer() -> None:
    # Act & Assert
    assert parse_checkpoint_cursor("42", data_type="integer") == 42
    assert parse_checkpoint_cursor("1.5", data_type="numeric") == Decimal("1.5")


def test_parse_checkpoint_cursor_coerces_uuid_boolean_and_timestamp() -> None:
    # Arrange
    import uuid
    from datetime import datetime

    sample_uuid = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

    # Act & Assert
    assert (
        parse_checkpoint_cursor(
            str(sample_uuid),
            data_type="uuid",
        )
        == sample_uuid
    )
    assert parse_checkpoint_cursor("true", data_type="boolean") is True
    assert parse_checkpoint_cursor(
        "2020-06-01T12:30:00",
        data_type="timestamp without time zone",
    ) == datetime.fromisoformat("2020-06-01T12:30:00")


def test_ensure_table_resumable_rejects_partial_no_pk() -> None:
    # Arrange
    from privaci.state.resume import TableCheckpoint

    checkpoint = TableCheckpoint(
        schema_name="public",
        table_name="events",
        status=CheckpointStatus.IN_PROGRESS,
        last_pk_value=None,
        rows_processed=5,
    )

    # Act / Assert
    with pytest.raises(StateError, match="single-column primary key"):
        ensure_table_resumable((), checkpoint)

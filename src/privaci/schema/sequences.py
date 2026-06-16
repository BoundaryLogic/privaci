"""Post-stream sequence synchronization for identity and serial columns."""

from __future__ import annotations

import logging

import asyncpg

from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.errors import PreflightError

logger = logging.getLogger(__name__)


def sequence_columns(table: TableInfo) -> tuple[ColumnInfo, ...]:
    """Return columns backed by a Postgres sequence."""
    return tuple(column for column in table.columns if column.sequence_name)


async def sync_table_sequences(
    conn: asyncpg.Connection,
    table: TableInfo,
    max_values: dict[str, int | None],
) -> None:
    """Advance identity/serial sequences to the highest streamed value."""
    for column in sequence_columns(table):
        await _set_sequence_value(conn, table, column, max_values.get(column.name))


async def _set_sequence_value(
    conn: asyncpg.Connection,
    table: TableInfo,
    column: ColumnInfo,
    max_value: int | None,
) -> None:
    sequence_name = column.sequence_name
    if sequence_name is None:
        return
    await _execute_setval(conn, table, sequence_name, max_value)
    _log_sequence_sync(table, column, sequence_name, max_value)


async def _execute_setval(
    conn: asyncpg.Connection,
    table: TableInfo,
    sequence_name: str,
    max_value: int | None,
) -> None:
    try:
        if max_value is None:
            await conn.execute(
                "SELECT setval($1::regclass, 1, false)",
                sequence_name,
            )
        else:
            await conn.execute(
                "SELECT setval($1::regclass, $2::bigint, true)",
                sequence_name,
                max_value,
            )
    except asyncpg.PostgresError as exc:
        raise PreflightError(
            "Synchronizing identity sequence on the target database",
            cause=(
                f"setval failed for {sequence_name} on {table.identifier}."
                f" ({type(exc).__name__})"
            ),
            remediation=(
                "Verify the target table and its backing sequence exist, then retry."
            ),
        ) from exc


def _log_sequence_sync(
    table: TableInfo,
    column: ColumnInfo,
    sequence_name: str,
    max_value: int | None,
) -> None:
    logger.info(
        "Synchronized sequence %s for %s.%s (max=%s)",
        sequence_name,
        table.identifier,
        column.name,
        max_value,
        extra={
            "event": "sequence.sync",
            "table": table.identifier,
            "column": column.name,
            "sequence": sequence_name,
            "max_value": max_value,
        },
    )

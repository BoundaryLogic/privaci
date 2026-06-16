"""Per-table strategy helpers for schema replication and streaming."""

from __future__ import annotations

import logging
import uuid

import asyncpg

from privaci.catalog.models import TableInfo
from privaci.state.checkpoints import mark_table_done, write_checkpoint
from privaci.state.models import CheckpointStatus

logger = logging.getLogger(__name__)


async def truncate_target_table(conn: asyncpg.Connection, table: TableInfo) -> None:
    """Remove all rows from an existing target table."""
    qual = table.sql_ref
    # SECURITY: qual is rendered via quote_pg_identifier, which escapes embedded
    # quotes and rejects control chars, so catalog identifiers cannot inject SQL.
    await conn.execute(f"TRUNCATE {qual}")  # noqa: S608


async def finalize_empty_strategy_table(
    conn: asyncpg.Connection,
    table: TableInfo,
    run_id: uuid.UUID,
    *,
    strategy: str,
) -> int:
    """Mark an ``empty`` or ``truncate`` table complete without streaming rows."""
    if strategy == "truncate":
        await truncate_target_table(conn, table)
    await write_checkpoint(
        conn,
        run_id,
        table.schema_name,
        table.table_name,
        last_pk_value=None,
        rows_in_batch=0,
        status=CheckpointStatus.DONE,
    )
    await mark_table_done(conn, run_id, table.schema_name, table.table_name)
    logger.info(
        "Finalized %s with strategy=%s (0 rows streamed)",
        table.identifier,
        strategy,
        extra={
            "event": "table.empty_strategy",
            "table": table.identifier,
            "strategy": strategy,
        },
    )
    return 0

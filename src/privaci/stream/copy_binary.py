"""COPY-binary passthrough streaming for tables with no masking."""

from __future__ import annotations

import io
import time
import uuid
from typing import Any

import asyncpg

from privaci.catalog.models import TableInfo
from privaci.config.actions import PassthroughAction
from privaci.config.models import TableConfig
from privaci.observability import Event, emit
from privaci.state.checkpoints import mark_table_done, write_checkpoint
from privaci.stream.coerce import table_needs_text_fallback
from privaci.stream.retry import with_source_retry


def can_binary_copy_passthrough(
    table: TableInfo,
    table_cfg: TableConfig,
    *,
    last_pk_value: Any | None,
    row_filter: str | None = None,
) -> bool:
    """Return whether a whole-table COPY-binary path is safe for this table."""
    if row_filter is not None:
        return False
    if last_pk_value is not None:
        return False
    column_types = {column.name: column.data_type for column in table.columns}
    if table_needs_text_fallback(column_types):
        return False
    if _requires_overriding_system_value(table):
        return False
    if not table_cfg.columns:
        return True
    return all(
        isinstance(action, PassthroughAction) for action in table_cfg.columns.values()
    )


async def binary_copy_passthrough_table(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    table: TableInfo,
    run_id: uuid.UUID,
    *,
    outer_transaction: bool = False,
) -> int:
    """Stream one table via COPY BINARY without row-level masking."""
    started_at = time.monotonic()
    row_count = await _copy_passthrough_payload(
        source, target, table, run_id, outer_transaction
    )
    emit(
        Event.TABLE_END,
        schema_name=table.schema_name,
        table_name=table.table_name,
        rows_processed=row_count,
        duration_ms=round((time.monotonic() - started_at) * 1000, 3),
        status="done",
    )
    return row_count


async def _copy_passthrough_payload(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    table: TableInfo,
    run_id: uuid.UUID,
    outer_transaction: bool,
) -> int:
    estimate = int(table.estimated_rows) if table.estimated_rows >= 0 else None
    emit(
        Event.TABLE_START,
        schema_name=table.schema_name,
        table_name=table.table_name,
        estimated_rows=estimate,
    )
    qual = table.sql_ref
    count_row = await with_source_retry(
        lambda: source.fetchval(f"SELECT COUNT(*) FROM {qual}")  # noqa: S608
    )
    row_count = int(count_row or 0)
    payload = await with_source_retry(lambda: _copy_out_table(source, table))
    if outer_transaction:
        await _load_binary_payload(target, table, run_id, payload, row_count)
    else:
        async with target.transaction():
            await _load_binary_payload(target, table, run_id, payload, row_count)
    return row_count


async def _load_binary_payload(
    target: asyncpg.Connection,
    table: TableInfo,
    run_id: uuid.UUID,
    payload: bytes,
    row_count: int,
) -> None:
    await target.copy_to_table(
        table.table_name,
        schema_name=table.schema_name,
        source=io.BytesIO(payload),
        format="binary",
    )
    await write_checkpoint(
        target,
        run_id,
        table.schema_name,
        table.table_name,
        last_pk_value=None,
        rows_in_batch=row_count,
    )
    await mark_table_done(target, run_id, table.schema_name, table.table_name)


async def _copy_out_table(conn: asyncpg.Connection, table: TableInfo) -> bytes:
    buffer = io.BytesIO()
    await conn.copy_from_table(
        table.table_name,
        schema_name=table.schema_name,
        output=buffer,
        format="binary",
    )
    return buffer.getvalue()


def _requires_overriding_system_value(table: TableInfo) -> bool:
    return any(
        column.is_identity and column.identity_generation == "ALWAYS"
        for column in table.columns
    )

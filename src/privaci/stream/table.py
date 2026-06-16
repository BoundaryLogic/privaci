"""Batch streaming for one table from source to target."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

import asyncpg

from privaci.catalog.models import TableInfo
from privaci.config.models import TableConfig
from privaci.mask.engine import MaskingEngine
from privaci.observability import Event, ProgressThrottle, emit
from privaci.schema.sequences import sync_table_sequences
from privaci.state.audit import AuditWriter
from privaci.state.checkpoints import mark_table_done, write_checkpoint
from privaci.state.models import EventType
from privaci.stream.batch_write import write_masked_batch
from privaci.stream.coerce import table_needs_text_fallback
from privaci.stream.copy_binary import (
    binary_copy_passthrough_table,
    can_binary_copy_passthrough,
)
from privaci.stream.fetch import next_stream_batch
from privaci.stream.models import (
    StreamContext,
    checkpoint_cursor,
    initial_max_values,
    requires_overriding_system_value,
    single_pk_column,
    update_max_values,
)

logger = logging.getLogger(__name__)


async def stream_table(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    table: TableInfo,
    engine: MaskingEngine,
    *,
    run_id: uuid.UUID,
    batch_size: int,
    last_pk_value: Any | None = None,
    outer_transaction: bool = False,
    table_config: TableConfig | None = None,
    audit: AuditWriter | None = None,
) -> int:
    effective_cfg = table_config or TableConfig()
    if can_binary_copy_passthrough(table, effective_cfg, last_pk_value=last_pk_value):
        return await binary_copy_passthrough_table(
            source,
            target,
            table,
            run_id,
            outer_transaction=outer_transaction,
        )

    ctx = await _prepare_stream_context(target, table, audit)
    await _seed_stream_checkpoint(target, table, run_id, last_pk_value)
    total = await _stream_masked_batches(
        source,
        target,
        table,
        engine,
        run_id,
        batch_size,
        last_pk_value,
        outer_transaction,
        ctx,
    )
    await _finalize_table_stream(
        target, table, run_id, ctx, total, outer_transaction=outer_transaction
    )
    return total


async def _seed_stream_checkpoint(
    target: asyncpg.Connection,
    table: TableInfo,
    run_id: uuid.UUID,
    last_pk_value: Any | None,
) -> None:
    """Ensure a checkpoint row exists before streaming (including 0-row tables)."""
    await write_checkpoint(
        target,
        run_id,
        table.schema_name,
        table.table_name,
        last_pk_value=checkpoint_cursor(last_pk_value),
        rows_in_batch=0,
    )


async def _prepare_stream_context(
    target: asyncpg.Connection,
    table: TableInfo,
    audit: AuditWriter | None,
) -> StreamContext:
    column_types = {column.name: column.data_type for column in table.columns}
    use_text_fallback = table_needs_text_fallback(column_types)
    if use_text_fallback:
        await _write_binary_fallback_audit(target, audit, table, column_types)
        logger.info(
            "Using text-mode INSERT for %s (unsupported binary COPY column type)",
            table.identifier,
            extra={"event": "table.text_fallback", "table": table.identifier},
        )
    estimate = int(table.estimated_rows) if table.estimated_rows >= 0 else None
    emit(
        Event.TABLE_START,
        schema_name=table.schema_name,
        table_name=table.table_name,
        estimated_rows=estimate,
    )
    return StreamContext(
        columns=[column.name for column in table.columns],
        column_types=column_types,
        qual=table.sql_ref,
        use_text_fallback=use_text_fallback,
        override_identity=requires_overriding_system_value(table),
        pk_column=single_pk_column(table),
        max_values=initial_max_values(table),
        progress=ProgressThrottle(
            table.schema_name,
            table.table_name,
            estimated_rows=estimate,
        ),
        table_started_at=time.monotonic(),
    )


async def _stream_masked_batches(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    table: TableInfo,
    engine: MaskingEngine,
    run_id: uuid.UUID,
    batch_size: int,
    last_pk_value: Any | None,
    outer_transaction: bool,
    ctx: StreamContext,
) -> int:
    total = 0
    cursor = last_pk_value
    offset = 0
    pending_fetch: asyncio.Task[list[asyncpg.Record]] | None = None

    while True:
        rows, pending_fetch = await next_stream_batch(
            source, pending_fetch, ctx, cursor, batch_size, offset
        )
        if not rows:
            break
        if outer_transaction:
            await write_masked_batch(target, table, engine, run_id, ctx, rows)
        else:
            async with target.transaction():
                await write_masked_batch(target, table, engine, run_id, ctx, rows)
        update_max_values(ctx.max_values, rows)
        total += len(rows)
        ctx.progress.maybe_emit(total)
        if ctx.pk_column is None:
            if len(rows) < batch_size:
                break
            offset += len(rows)
    return total


async def _finalize_table_stream(
    target: asyncpg.Connection,
    table: TableInfo,
    run_id: uuid.UUID,
    ctx: StreamContext,
    total: int,
    *,
    outer_transaction: bool,
) -> None:
    if outer_transaction:
        await mark_table_done(target, run_id, table.schema_name, table.table_name)
        await sync_table_sequences(target, table, ctx.max_values)
    else:
        async with target.transaction():
            await mark_table_done(target, run_id, table.schema_name, table.table_name)
            await sync_table_sequences(target, table, ctx.max_values)
    emit(
        Event.TABLE_END,
        schema_name=table.schema_name,
        table_name=table.table_name,
        rows_processed=total,
        duration_ms=round((time.monotonic() - ctx.table_started_at) * 1000, 3),
        status="done",
    )


async def _write_binary_fallback_audit(
    conn: asyncpg.Connection,
    audit: AuditWriter | None,
    table: TableInfo,
    column_types: dict[str, str],
) -> None:
    if audit is None or not audit.enabled:
        return
    fallback_types = sorted(
        {
            column_types[column]
            for column in column_types
            if table_needs_text_fallback({column: column_types[column]})
        }
    )
    await audit.write(
        conn,
        EventType.BINARY_FALLBACK,
        schema_name=table.schema_name,
        table_name=table.table_name,
        payload={"types": fallback_types},
    )

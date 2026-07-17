"""COPY-binary passthrough streaming for tables with no masking."""

from __future__ import annotations

import asyncio
import time
import uuid

import asyncpg

from privaci.catalog.identifiers import quote_pg_identifier
from privaci.catalog.models import TableInfo
from privaci.observability import Event, emit
from privaci.schema.sequences import sequence_columns, sync_table_sequences
from privaci.state.checkpoints import mark_table_done, write_checkpoint
from privaci.stream.copy_pipe import CopyChunkPipe
from privaci.stream.retry import with_source_retry


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
    if outer_transaction:
        await _pipe_binary_passthrough(source, target, table, run_id, row_count)
    else:
        async with target.transaction():
            await _pipe_binary_passthrough(source, target, table, run_id, row_count)
    return row_count


async def _pipe_binary_passthrough(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    table: TableInfo,
    run_id: uuid.UUID,
    row_count: int,
) -> None:
    """Stream COPY OUT on source directly into COPY IN on target."""

    async def run_pipe() -> None:
        pipe = CopyChunkPipe()

        async def copy_out() -> None:
            try:
                await source.copy_from_table(
                    table.table_name,
                    schema_name=table.schema_name,
                    output=pipe.write,
                    format="binary",
                )
            finally:
                await pipe.close()

        async def copy_in() -> None:
            await target.copy_to_table(
                table.table_name,
                schema_name=table.schema_name,
                source=pipe,
                format="binary",
            )

        await asyncio.gather(copy_out(), copy_in())

    await with_source_retry(run_pipe)
    await write_checkpoint(
        target,
        run_id,
        table.schema_name,
        table.table_name,
        last_pk_value=None,
        rows_in_batch=row_count,
    )
    await mark_table_done(target, run_id, table.schema_name, table.table_name)
    await _sync_sequences_after_binary_copy(target, table)


async def _sync_sequences_after_binary_copy(
    target: asyncpg.Connection,
    table: TableInfo,
) -> None:
    """Advance identity/serial sequences to match values just copied."""
    max_values = await _sequence_max_values(target, table)
    await sync_table_sequences(target, table, max_values)


async def _sequence_max_values(
    target: asyncpg.Connection,
    table: TableInfo,
) -> dict[str, int | None]:
    max_values: dict[str, int | None] = {}
    for column in sequence_columns(table):
        col = quote_pg_identifier(column.name)
        # SECURITY: col and sql_ref are quote_pg_identifier-rendered.
        value = await target.fetchval(
            f"SELECT MAX({col}) FROM {table.sql_ref}"  # noqa: S608
        )
        max_values[column.name] = int(value) if value is not None else None
    return max_values

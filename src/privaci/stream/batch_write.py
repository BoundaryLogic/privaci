"""Masked batch writes and checkpoint advancement."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg

from privaci.catalog.identifiers import quote_pg_identifier
from privaci.catalog.models import TableInfo
from privaci.mask.engine import MaskingEngine
from privaci.state.checkpoints import write_checkpoint
from privaci.stream.coerce import coerce_value
from privaci.stream.models import StreamContext, checkpoint_cursor


async def write_masked_batch(
    target: asyncpg.Connection,
    table: TableInfo,
    engine: MaskingEngine,
    run_id: uuid.UUID,
    ctx: StreamContext,
    rows: list[asyncpg.Record],
) -> None:
    """Mask, load, and checkpoint one fetched batch."""
    masked_rows = [engine.mask_row(dict(row)) for row in rows]
    records = as_tuples(masked_rows, ctx.columns, ctx.column_types, table)
    if ctx.use_text_fallback or ctx.override_identity:
        await insert_records(
            target,
            ctx.qual,
            ctx.columns,
            records,
            overriding_system_value=ctx.override_identity,
        )
    else:
        await target.copy_records_to_table(
            table.table_name,
            schema_name=table.schema_name,
            records=records,
            columns=ctx.columns,
        )
    last_row = dict(rows[-1])
    pk_value = last_row.get(ctx.pk_column) if ctx.pk_column else None
    await write_checkpoint(
        target,
        run_id,
        table.schema_name,
        table.table_name,
        last_pk_value=checkpoint_cursor(pk_value),
        rows_in_batch=len(rows),
    )


async def insert_records(
    target: asyncpg.Connection,
    qual: str,
    columns: list[str],
    records: list[tuple[Any, ...]],
    *,
    overriding_system_value: bool = False,
) -> None:
    """Load a batch via parameterized INSERT (text protocol) for exotic types."""
    col_list = ", ".join(quote_pg_identifier(name) for name in columns)
    placeholders = ", ".join(f"${idx}" for idx in range(1, len(columns) + 1))
    override = " OVERRIDING SYSTEM VALUE" if overriding_system_value else ""
    # SECURITY: qual and column names are rendered via quote_pg_identifier, which
    # escapes embedded quotes and rejects control chars, so untrusted catalog
    # identifiers cannot inject SQL.
    sql = f"INSERT INTO {qual} ({col_list}){override} VALUES ({placeholders})"  # noqa: S608
    await target.executemany(sql, records)


def as_tuples(
    rows: list[dict[str, Any]],
    columns: list[str],
    column_types: dict[str, str],
    table: TableInfo,
) -> list[tuple[Any, ...]]:
    return [
        tuple(
            coerce_value(
                row.get(column),
                column_types[column],
                column_path=f"{table.identifier}.{column}",
            )
            for column in columns
        )
        for row in rows
    ]

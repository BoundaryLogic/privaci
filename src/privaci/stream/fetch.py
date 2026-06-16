"""Keyset and ctid batch fetching for table streaming."""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from privaci.catalog.identifiers import quote_pg_identifier
from privaci.errors import RunInterruptedError
from privaci.runtime.signals import interrupt_requested
from privaci.stream.models import StreamContext
from privaci.stream.retry import with_source_retry


def raise_if_interrupted() -> None:
    """Raise when the operator requested a graceful shutdown."""
    if not interrupt_requested():
        return
    raise RunInterruptedError(
        "Streaming masked rows",
        cause="Interrupted by signal (SIGINT/SIGTERM).",
        remediation="Resume with `privaci resume` after fixing the issue.",
    )


async def next_stream_batch(
    source: asyncpg.Connection,
    pending_fetch: asyncio.Task[list[asyncpg.Record]] | None,
    ctx: StreamContext,
    cursor: Any | None,
    batch_size: int,
    offset: int,
) -> tuple[list[asyncpg.Record], asyncio.Task[list[asyncpg.Record]] | None]:
    """Await the current prefetch and schedule the next source batch."""
    raise_if_interrupted()
    if pending_fetch is None:
        pending_fetch = asyncio.create_task(
            fetch_batch_with_retry(
                source, ctx.qual, ctx.pk_column, cursor, batch_size, offset=offset
            )
        )
    rows = await pending_fetch
    if not rows:
        return rows, None
    next_fetch = asyncio.create_task(
        fetch_batch_with_retry(
            source,
            ctx.qual,
            ctx.pk_column,
            next_cursor(rows, ctx.pk_column, cursor),
            batch_size,
            offset=offset + len(rows) if ctx.pk_column is None else offset,
        )
    )
    return rows, next_fetch


async def fetch_batch_with_retry(
    source: asyncpg.Connection,
    qual: str,
    pk_column: str | None,
    cursor: Any | None,
    batch_size: int,
    *,
    offset: int = 0,
) -> list[asyncpg.Record]:
    return await with_source_retry(
        lambda: fetch_batch(
            source,
            qual,
            pk_column,
            cursor,
            batch_size,
            offset=offset,
        )
    )


async def fetch_batch(
    source: asyncpg.Connection,
    qual: str,
    pk_column: str | None,
    cursor: Any | None,
    batch_size: int,
    *,
    offset: int = 0,
) -> list[asyncpg.Record]:
    # SECURITY: qual and pk_column are rendered via quote_pg_identifier (escapes
    # quotes, rejects control chars), so untrusted catalog identifiers are safe.
    if pk_column is None:
        query = f"SELECT * FROM {qual} ORDER BY ctid LIMIT $1 OFFSET $2"  # noqa: S608
        return list(await source.fetch(query, batch_size, offset))
    col = quote_pg_identifier(pk_column)
    if cursor is None:
        query = f"SELECT * FROM {qual} ORDER BY {col} LIMIT $1"  # noqa: S608
        return list(await source.fetch(query, batch_size))
    query = (
        f"SELECT * FROM {qual} WHERE {col} > $1 ORDER BY {col} LIMIT $2"  # noqa: S608
    )
    return list(await source.fetch(query, cursor, batch_size))


def next_cursor(
    rows: list[asyncpg.Record],
    pk_column: str | None,
    current_cursor: Any | None,
) -> Any | None:
    if pk_column is None:
        return current_cursor
    last_row = dict(rows[-1])
    return last_row.get(pk_column)

"""COPY-binary round-trip spike between source and target Postgres."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from time import perf_counter

import asyncpg

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS spike_copy_roundtrip (
    id integer PRIMARY KEY,
    label text NOT NULL,
    amount numeric(12, 2),
    active boolean NOT NULL DEFAULT true,
    payload jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
)
"""


@dataclass(frozen=True, slots=True)
class CopyBinarySpikeResult:
    """Metrics from a COPY-binary source→target round-trip."""

    source_rows: int
    target_rows: int
    payload_bytes: int
    elapsed_seconds: float
    rows_match: bool

    @property
    def passed(self) -> bool:
        """True when row counts match and payload was non-empty."""
        return self.rows_match and self.payload_bytes > 0


async def run_copy_binary_spike(
    source_dsn: str,
    target_dsn: str,
) -> CopyBinarySpikeResult:
    """Stream a table via COPY BINARY from source and load into target.

    Args:
        source_dsn: Postgres URL for the seeded source database.
        target_dsn: Postgres URL for the empty target database.

    Returns:
        Timing and row-count metrics for documentation in ``docs/spikes/``.
    """
    started = perf_counter()
    source = await asyncpg.connect(source_dsn)
    target = await asyncpg.connect(target_dsn)
    try:
        source_rows = await _count_rows(source)
        payload = await _copy_out(source)
        await _prepare_target(target)
        await _copy_in(target, payload)
        target_rows = await _count_rows(target)
    finally:
        await source.close()
        await target.close()

    elapsed = perf_counter() - started
    rows_match = source_rows == target_rows
    result = CopyBinarySpikeResult(
        source_rows=source_rows,
        target_rows=target_rows,
        payload_bytes=len(payload),
        elapsed_seconds=elapsed,
        rows_match=rows_match,
    )
    logger.info("COPY-binary spike finished", extra={"result": result})
    return result


async def _count_rows(conn: asyncpg.Connection) -> int:
    value = await conn.fetchval("SELECT COUNT(*) FROM spike_copy_roundtrip")
    return int(value or 0)


async def _copy_out(conn: asyncpg.Connection) -> bytes:
    buffer = io.BytesIO()
    await conn.copy_from_table(
        "spike_copy_roundtrip",
        output=buffer,
        format="binary",
    )
    return buffer.getvalue()


async def _prepare_target(conn: asyncpg.Connection) -> None:
    await conn.execute(_DDL)
    await conn.execute("TRUNCATE spike_copy_roundtrip")


async def _copy_in(conn: asyncpg.Connection, payload: bytes) -> None:
    await conn.copy_to_table(
        "spike_copy_roundtrip",
        source=io.BytesIO(payload),
        format="binary",
    )

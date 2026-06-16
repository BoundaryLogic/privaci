"""Cyclic FK load spike using SET CONSTRAINTS ALL DEFERRED."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CyclicFkSpikeResult:
    """Outcome of inserting mutually referencing rows under deferred constraints."""

    a_rows: int
    b_rows: int
    committed: bool

    @property
    def passed(self) -> bool:
        """True when both tables contain the expected rows after commit."""
        return self.committed and self.a_rows == 1 and self.b_rows == 1


async def run_cyclic_fk_spike(dsn: str) -> CyclicFkSpikeResult:
    """Insert cyclic FK rows inside a deferred-constraint transaction.

    Args:
        dsn: Postgres URL (source DB with ``spike_cycle_*`` tables seeded).

    Returns:
        Row counts and whether the transaction committed successfully.
    """
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("TRUNCATE spike_cycle_a, spike_cycle_b CASCADE")
        committed = await _load_cycle(conn)
        a_rows = await conn.fetchval("SELECT COUNT(*) FROM spike_cycle_a")
        b_rows = await conn.fetchval("SELECT COUNT(*) FROM spike_cycle_b")
    finally:
        await conn.close()

    result = CyclicFkSpikeResult(
        a_rows=int(a_rows or 0),
        b_rows=int(b_rows or 0),
        committed=committed,
    )
    logger.info("Cyclic FK spike finished", extra={"result": result})
    return result


async def _load_cycle(conn: asyncpg.Connection) -> bool:
    try:
        async with conn.transaction():
            await conn.execute("SET CONSTRAINTS ALL DEFERRED")
            await conn.execute("INSERT INTO spike_cycle_a (id, b_id) VALUES (1, 1)")
            await conn.execute("INSERT INTO spike_cycle_b (id, a_id) VALUES (1, 1)")
    except asyncpg.PostgresError:
        return False
    return True

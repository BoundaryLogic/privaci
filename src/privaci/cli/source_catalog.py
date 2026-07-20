"""Source-only catalog introspection shared by init, plan, and catalog CLI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

import asyncpg

from privaci.catalog import CatalogResult, introspect_catalog
from privaci.errors import CatalogError

T = TypeVar("T")


async def with_source_connection(
    dsn: str,
    work: Callable[[asyncpg.Connection], Awaitable[T]],
) -> T:
    """Open a source connection, run ``work``, and always close.

    Args:
        dsn: PostgreSQL connection string for the source role.
        work: Async callback that receives the open connection.

    Raises:
        CatalogError: When the database is unreachable.
    """
    try:
        conn = await asyncpg.connect(dsn)
    except (OSError, asyncpg.PostgresError) as exc:
        raise CatalogError(
            "Connecting to the source database",
            cause="The source database is not reachable.",
            remediation="Verify SOURCE_DB_URL and that the database is running.",
        ) from exc
    try:
        return await work(conn)
    finally:
        await conn.close()


async def introspect_source_catalog(dsn: str) -> CatalogResult:
    """Connect to the source database and introspect schema metadata.

    Args:
        dsn: PostgreSQL connection string for the source role.

    Raises:
        CatalogError: When the database is unreachable or introspection fails.
    """
    return await with_source_connection(dsn, introspect_catalog)

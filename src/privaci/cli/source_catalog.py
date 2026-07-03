"""Source-only catalog introspection shared by init and plan."""

from __future__ import annotations

import asyncpg

from privaci.catalog import CatalogResult, introspect_catalog
from privaci.errors import CatalogError


async def introspect_source_catalog(dsn: str) -> CatalogResult:
    """Connect to the source database and introspect schema metadata.

    Args:
        dsn: PostgreSQL connection string for the source role.

    Raises:
        CatalogError: When the database is unreachable or introspection fails.
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
        return await introspect_catalog(conn)
    finally:
        await conn.close()

"""Shared Postgres reset helpers for integration tests."""

from __future__ import annotations

import asyncpg

from privaci.catalog.identifiers import quote_pg_identifier

_SYSTEM_SCHEMAS = frozenset({"pg_catalog", "information_schema", "pg_toast"})


async def ensure_public_schema(conn: asyncpg.Connection) -> None:
    """Recreate the default ``public`` schema after a full user-schema wipe."""
    await conn.execute("CREATE SCHEMA IF NOT EXISTS public")
    await conn.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
    await conn.execute("GRANT ALL ON SCHEMA public TO postgres")


async def drop_user_schemas(conn: asyncpg.Connection) -> None:
    """Drop every non-system schema on a database."""
    rows = await conn.fetch("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND schema_name NOT LIKE 'pg_%'
        """)
    for row in rows:
        quoted_schema = quote_pg_identifier(row["schema_name"])
        await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")


async def reset_database(dsn: str) -> None:
    """Drop user schemas and restore bootstrap ``public`` for follow-on SQL."""
    conn = await asyncpg.connect(dsn)
    try:
        await drop_user_schemas(conn)
        await ensure_public_schema(conn)
    finally:
        await conn.close()

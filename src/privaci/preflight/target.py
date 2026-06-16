"""Target-database collision checks and ``on_existing_data`` handling."""

from __future__ import annotations

import asyncpg

from privaci.catalog.identifiers import quote_pg_identifier
from privaci.catalog.models import CatalogResult
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.schema.replicate import tables_in_load_order


async def count_user_tables(conn: asyncpg.Connection) -> int:
    """Return the number of user tables on the target outside ``_privaci``."""
    return await _count_user_tables(conn)


async def ensure_target_ready(
    conn: asyncpg.Connection,
    config: Config,
    catalog: CatalogResult,
) -> None:
    """Apply ``on_existing_data`` policy before any masking writes.

    Args:
        conn: Target-database connection.
        config: Validated mask-rules config.
        catalog: Introspected source catalog.

    Raises:
        PreflightError: When ``fail`` is configured and user tables exist.
    """
    user_tables = await count_user_tables(conn)
    policy = config.on_existing_data
    if policy == "fail":
        if user_tables > 0:
            raise PreflightError(
                "Checking target database is empty",
                cause=(
                    f"Target contains {user_tables} user table(s) outside "
                    "_privaci and on_existing_data is fail."
                ),
                remediation=(
                    "Use an empty target database, or set on_existing_data to "
                    "truncate or drop_create in mask-rules.yaml."
                ),
            )
        return
    if policy == "drop_create":
        await _drop_user_schemas(conn)
        return
    if policy == "truncate":
        await _truncate_in_scope_tables(conn, catalog, config)
        return
    msg = f"unsupported on_existing_data policy: {policy!r}"
    raise PreflightError("Applying on_existing_data policy", cause=msg)


async def _count_user_tables(conn: asyncpg.Connection) -> int:
    value = await conn.fetchval("""
        SELECT count(*)::int
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
          AND table_schema NOT LIKE 'pg\\_%'
          AND table_type = 'BASE TABLE'
          AND table_schema <> '_privaci'
        """)
    return int(value or 0)


async def _drop_user_schemas(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
          AND schema_name NOT LIKE 'pg\\_%'
        """)
    for row in rows:
        schema = quote_pg_identifier(row["schema_name"])
        # SECURITY: schema is rendered via quote_pg_identifier (escapes quotes,
        # rejects control chars), so a hostile target catalog cannot inject SQL.
        await conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")  # noqa: S608


async def _truncate_in_scope_tables(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> None:
    for table in tables_in_load_order(catalog):
        table_cfg = config.tables.get(table.identifier)
        if table_cfg is not None and table_cfg.strategy == "exclude":
            continue
        qual = table.sql_ref
        exists = await conn.fetchval("SELECT to_regclass($1)", qual)
        if exists is None:
            continue
        # SECURITY: qual is rendered via quote_pg_identifier (escapes quotes,
        # rejects control chars), so catalog identifiers cannot inject SQL.
        await conn.execute(f"TRUNCATE TABLE {qual} CASCADE")  # noqa: S608

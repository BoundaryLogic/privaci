"""Target-database collision checks and ``on_existing_data`` handling."""

from __future__ import annotations

import asyncpg

from privaci.catalog.identifiers import quote_pg_identifier
from privaci.catalog.models import CatalogResult, TableInfo
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.schema.replicate import tables_in_load_order
from privaci.schema.table_policy import is_excluded_table


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
        PreflightError: When ``fail`` is configured and the target collides.
    """
    policy = config.on_existing_data
    await validate_target_policy(conn, config, catalog)
    if policy == "fail":
        return
    if policy == "drop_create":
        await _drop_user_schemas(conn)
        return
    if policy == "truncate":
        await _truncate_in_scope_tables(conn, catalog, config)
        return
    msg = f"unsupported on_existing_data policy: {policy!r}"
    raise PreflightError("Applying on_existing_data policy", cause=msg)


async def validate_target_policy(
    conn: asyncpg.Connection,
    config: Config,
    catalog: CatalogResult,
) -> None:
    """Validate target collision policy without mutating the target."""
    policy = config.on_existing_data
    if policy in {"truncate", "drop_create"}:
        return
    if policy != "fail":
        msg = f"unsupported on_existing_data policy: {policy!r}"
        raise PreflightError("Applying on_existing_data policy", cause=msg)
    if config.schema_mode == "assume_existing":
        await _refuse_populated_in_scope_tables(conn, catalog, config)
        return
    await _refuse_existing_user_tables(conn, config)


async def collision_warning_for_dry_run(
    conn: asyncpg.Connection,
    config: Config,
    catalog: CatalogResult,
) -> str | None:
    """Return a dry-run warning when a real run would fail on collision policy."""
    if config.on_existing_data != "fail":
        return None
    if config.schema_mode == "assume_existing":
        populated = await _first_populated_in_scope_table(conn, catalog, config)
        if populated is None:
            return None
        return (
            f"Target table {populated} has existing rows; a real run will fail "
            "with on_existing_data: fail unless rows are removed or the policy "
            "is set to truncate."
        )
    user_tables = await _count_user_tables(conn)
    if user_tables <= 0:
        return None
    return (
        f"Target has {user_tables} user table(s) outside _privaci; "
        "a real run will fail with on_existing_data: fail unless the "
        "target is emptied or the policy is changed."
    )


def _target_collision_remediation(config: Config) -> str:
    if config.schema_mode == "assume_existing":
        return "Set on_existing_data: truncate for the prebuilt target schema."
    return (
        "Use an empty target database, or set on_existing_data to "
        "truncate or drop_create in mask-rules.yaml."
    )


async def _refuse_existing_user_tables(
    conn: asyncpg.Connection,
    config: Config,
) -> None:
    user_tables = await _count_user_tables(conn)
    if user_tables <= 0:
        return
    raise PreflightError(
        "Checking target database is empty",
        cause=(
            f"Target contains {user_tables} user table(s) outside "
            "_privaci and on_existing_data is fail."
        ),
        remediation=_target_collision_remediation(config),
    )


async def _refuse_populated_in_scope_tables(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> None:
    populated = await _first_populated_in_scope_table(conn, catalog, config)
    if populated is None:
        return
    raise PreflightError(
        "Checking target tables are empty",
        cause=(
            f"Target table {populated} has existing rows and "
            "on_existing_data is fail. Loads copy source primary-key "
            "values explicitly; populated targets require "
            "on_existing_data: truncate "
            "(identity/SERIAL columns do not change this)."
        ),
        remediation=_target_collision_remediation(config),
    )


async def _first_populated_in_scope_table(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> str | None:
    for table in tables_in_load_order(catalog):
        if is_excluded_table(table, config):
            continue
        if await _table_has_rows(conn, table):
            return table.identifier
    return None


async def _table_has_rows(conn: asyncpg.Connection, table: TableInfo) -> bool:
    qual = table.sql_ref
    exists = await conn.fetchval("SELECT to_regclass($1)", qual)
    if exists is None:
        return False
    # SECURITY: qual is rendered via quote_pg_identifier (escapes quotes,
    # rejects control chars), so catalog identifiers cannot inject SQL.
    has_rows = await conn.fetchval(
        f"SELECT EXISTS (SELECT 1 FROM {qual} LIMIT 1)"  # noqa: S608
    )
    return bool(has_rows)


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
          AND schema_name <> '_privaci'
        """)
    for row in rows:
        schema = quote_pg_identifier(row["schema_name"])
        # SECURITY: schema is rendered via quote_pg_identifier (escapes quotes,
        # rejects control chars), so a hostile target catalog cannot inject SQL.
        await conn.execute(  # nosemgrep
            f"DROP SCHEMA IF EXISTS {schema} CASCADE"
        )  # noqa: S608


async def _truncate_in_scope_tables(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> None:
    for table in tables_in_load_order(catalog):
        if is_excluded_table(table, config):
            continue
        qual = table.sql_ref
        exists = await conn.fetchval("SELECT to_regclass($1)", qual)
        if exists is None:
            continue
        # SECURITY: qual is rendered via quote_pg_identifier (escapes quotes,
        # rejects control chars), so catalog identifiers cannot inject SQL.
        await conn.execute(f"TRUNCATE TABLE {qual} CASCADE")  # nosemgrep  # noqa: S608

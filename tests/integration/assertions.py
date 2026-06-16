"""Composable assertion helpers for Demo Corp end-to-end tests.

Each helper takes an ``asyncpg`` connection so integration tests read the same
way regardless of which scenario they exercise. None of these helpers log or
return raw PII values.
"""

from __future__ import annotations

from typing import Any

import asyncpg


async def count_rows(conn: asyncpg.Connection, qualified_table: str) -> int:
    """Return the row count for a schema-qualified table."""
    schema, _, table = qualified_table.partition(".")
    # SECURITY: identifiers come from the test catalog, never user input.
    value = await conn.fetchval(
        f'SELECT count(*)::int FROM "{schema}"."{table}"'  # noqa: S608
    )
    return int(value or 0)


async def fetch_column_values(
    conn: asyncpg.Connection,
    qualified_table: str,
    column: str,
    *,
    limit: int = 100,
) -> list[Any]:
    """Return up to ``limit`` values from one column."""
    schema, _, table = qualified_table.partition(".")
    rows = await conn.fetch(
        f'SELECT "{column}" AS v FROM "{schema}"."{table}" '  # noqa: S608
        f'WHERE "{column}" IS NOT NULL LIMIT {int(limit)}'
    )
    return [row["v"] for row in rows]


async def value_present(
    conn: asyncpg.Connection,
    qualified_table: str,
    column: str,
    value: Any,
) -> bool:
    """Return whether ``value`` appears in a column (for leakage checks)."""
    schema, _, table = qualified_table.partition(".")
    found = await conn.fetchval(
        f'SELECT EXISTS(SELECT 1 FROM "{schema}"."{table}" '  # noqa: S608
        f'WHERE "{column}" = $1)',
        value,
    )
    return bool(found)


async def assert_no_pii_present(
    conn: asyncpg.Connection,
    qualified_table: str,
    column: str,
    forbidden: list[Any],
) -> None:
    """Raise AssertionError if any forbidden source value survived masking."""
    for value in forbidden:
        if await value_present(conn, qualified_table, column, value):
            msg = f"Original value leaked into {qualified_table}.{column}"
            raise AssertionError(msg)


async def all_fks_valid(conn: asyncpg.Connection) -> bool:
    """Return True when no foreign key has orphaned child rows.

    Walks every FK constraint in user schemas and checks for child rows whose
    referenced parent row is missing.
    """
    constraints = await conn.fetch("""
        SELECT
            con.conname,
            child_ns.nspname AS child_schema,
            child.relname AS child_table,
            parent_ns.nspname AS parent_schema,
            parent.relname AS parent_table,
            con.conkey,
            con.confkey
        FROM pg_constraint con
        JOIN pg_class child ON child.oid = con.conrelid
        JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
        JOIN pg_class parent ON parent.oid = con.confrelid
        JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        WHERE con.contype = 'f'
          AND child_ns.nspname NOT IN ('pg_catalog', 'information_schema')
          AND child_ns.nspname <> '_privaci'
        """)
    for con in constraints:
        if not await _fk_constraint_valid(conn, con):
            return False
    return True


async def _fk_constraint_valid(
    conn: asyncpg.Connection,
    con: asyncpg.Record,
) -> bool:
    child_cols = await _column_names(
        conn, con["child_schema"], con["child_table"], con["conkey"]
    )
    parent_cols = await _column_names(
        conn, con["parent_schema"], con["parent_table"], con["confkey"]
    )
    child = f'"{con["child_schema"]}"."{con["child_table"]}"'
    parent = f'"{con["parent_schema"]}"."{con["parent_table"]}"'
    join_pred = " AND ".join(
        f'p."{pc}" = c."{cc}"' for cc, pc in zip(child_cols, parent_cols, strict=True)
    )
    not_null = " AND ".join(f'c."{cc}" IS NOT NULL' for cc in child_cols)
    # SECURITY: all identifiers derive from pg_catalog, never user input.
    orphans = await conn.fetchval(
        f"SELECT count(*)::int FROM {child} c "  # noqa: S608
        f"WHERE {not_null} AND NOT EXISTS "
        f"(SELECT 1 FROM {parent} p WHERE {join_pred})"
    )
    return int(orphans or 0) == 0


async def _column_names(
    conn: asyncpg.Connection,
    schema: str,
    table: str,
    attnums: list[int],
) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT a.attnum, a.attname
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = $1 AND c.relname = $2 AND a.attnum = ANY($3::int[])
        """,
        schema,
        table,
        attnums,
    )
    by_num = {row["attnum"]: row["attname"] for row in rows}
    return [by_num[num] for num in attnums]


async def audit_count(
    conn: asyncpg.Connection,
    *,
    event_type: str | None = None,
) -> int:
    """Count audit-log rows, optionally filtered by ``event_type``."""
    if event_type is None:
        value = await conn.fetchval("SELECT count(*)::int FROM _privaci.audit_log")
    else:
        value = await conn.fetchval(
            "SELECT count(*)::int FROM _privaci.audit_log WHERE event_type = $1",
            event_type,
        )
    return int(value or 0)


async def partition_count(conn: asyncpg.Connection, parent_qualified: str) -> int:
    """Return the number of partitions attached to a partitioned parent table."""
    schema, _, table = parent_qualified.partition(".")
    value = await conn.fetchval(
        """
        SELECT count(*)::int
        FROM pg_inherits inh
        JOIN pg_class parent ON parent.oid = inh.inhparent
        JOIN pg_namespace ns ON ns.oid = parent.relnamespace
        WHERE ns.nspname = $1 AND parent.relname = $2
        """,
        schema,
        table,
    )
    attached = int(value or 0)
    if attached > 0:
        return attached
    # Pre-§24 engines may replicate partition children as standalone tables.
    return await count_child_tables(conn, schema, f"{table}_")


async def count_child_tables(
    conn: asyncpg.Connection,
    schema: str,
    name_prefix: str,
) -> int:
    """Count base tables whose names start with ``name_prefix``."""
    value = await conn.fetchval(
        """
        SELECT count(*)::int
        FROM information_schema.tables
        WHERE table_schema = $1
          AND table_name LIKE $2
          AND table_type = 'BASE TABLE'
        """,
        schema,
        f"{name_prefix}%",
    )
    return int(value or 0)


async def count_partitioned_table_rows(
    conn: asyncpg.Connection,
    parent_qualified: str,
    *,
    child_prefix: str,
) -> int:
    """Count rows for a partitioned table, including detached child replicas."""
    if await table_exists(conn, parent_qualified):
        return await count_rows(conn, parent_qualified)
    schema, _, _ = parent_qualified.partition(".")
    rows = await conn.fetch(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = $1
          AND table_name LIKE $2
          AND table_type = 'BASE TABLE'
        """,
        schema,
        f"{child_prefix}%",
    )
    total = 0
    for row in rows:
        total += await count_rows(conn, f"{schema}.{row['table_name']}")
    return total


async def table_exists(conn: asyncpg.Connection, qualified_table: str) -> bool:
    """Return whether a table or view exists on the connection."""
    schema, _, table = qualified_table.partition(".")
    found = await conn.fetchval("SELECT to_regclass($1)", f'"{schema}"."{table}"')
    return found is not None

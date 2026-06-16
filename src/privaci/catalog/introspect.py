"""Read-only PostgreSQL catalog introspection via asyncpg."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import replace

import asyncpg

from privaci.catalog.detectors import (
    detect_implied_fks,
    detect_polymorphic_fks,
    mark_self_cycles,
)
from privaci.catalog.graph import build_load_plan
from privaci.catalog.identifiers import assert_safe_identifiers
from privaci.catalog.models import (
    CatalogResult,
    CatalogWarning,
    CheckConstraintInfo,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    SkippedObjectInfo,
    TableInfo,
    ViewInfo,
    table_id,
)
from privaci.catalog.partitions import attach_partition_metadata
from privaci.catalog.queries import (
    COLUMN_NAMES_SQL,
    COLUMN_STATS_SQL,
    COLUMNS_SQL,
    CONSTRAINTS_SQL,
    INDEXES_SQL,
    MATVIEWS_SQL,
    TABLES_SQL,
    VIEWS_SQL,
)
from privaci.catalog.skipped import fetch_skipped_objects
from privaci.errors import CatalogError

logger = logging.getLogger(__name__)

_PERMISSION_SQLSTATE = "42501"


async def introspect_catalog(
    conn: asyncpg.Connection,
    *,
    implied_fk_ignore: frozenset[str] = frozenset(),
) -> CatalogResult:
    """Introspect the source schema in a single read-only transaction.

    Args:
        conn: An open asyncpg connection to the source database.
        implied_fk_ignore: Source column paths (``schema.table.column``) whose
            implied foreign-key warnings should be silenced.

    Returns:
        A :class:`CatalogResult` with tables, load plan, and warnings.

    Raises:
        CatalogError: When catalog access fails (exit code 2).
    """
    try:
        tables, views, skipped_objects, partition_warnings = (
            await _introspect_in_transaction(conn)
        )
    except asyncpg.PostgresError as exc:
        raise _map_postgres_error(exc) from exc

    assert_safe_identifiers(tables)
    tables = mark_self_cycles(tables)
    warnings = _never_analyzed_warnings(tables)
    warnings += partition_warnings
    warnings += detect_polymorphic_fks(tables)
    warnings += detect_implied_fks(tables, ignore=implied_fk_ignore)
    load_plan = build_load_plan(tables)
    return CatalogResult(
        tables=tables,
        load_plan=load_plan,
        warnings=warnings,
        views=views,
        skipped_objects=skipped_objects,
    )


def _map_postgres_error(exc: asyncpg.PostgresError) -> CatalogError:
    """Translate Postgres errors into operator-facing catalog failures."""
    if exc.sqlstate == _PERMISSION_SQLSTATE:
        return CatalogError(
            "Introspecting source database catalogs",
            cause="Role lacks SELECT on pg_catalog system tables.",
            remediation=(
                "Grant CONNECT on the database and USAGE on schemas, or use a "
                "role with read access to pg_catalog."
            ),
        )
    return CatalogError(
        "Introspecting source database catalogs",
        cause="Catalog query failed.",
        remediation="Verify source connectivity and permissions, then retry.",
    )


async def _introspect_in_transaction(
    conn: asyncpg.Connection,
) -> tuple[
    dict[str, TableInfo],
    tuple[ViewInfo, ...],
    tuple[SkippedObjectInfo, ...],
    tuple[CatalogWarning, ...],
]:
    """Run catalog queries inside one read-only transaction."""
    async with conn.transaction(readonly=True):
        tables = await _fetch_tables(conn)
        column_lookup = await _fetch_column_lookup(conn)
        stats = await _fetch_column_stats(conn)
        await _attach_columns(conn, tables, column_lookup, stats)
        await _attach_constraints(conn, tables, column_lookup)
        await _attach_indexes(conn, tables, column_lookup)
        partition_warnings = await attach_partition_metadata(conn, tables)
        views = await _fetch_views(conn)
        skipped_objects = await fetch_skipped_objects(conn)
    return tables, views, skipped_objects, partition_warnings


async def _fetch_tables(conn: asyncpg.Connection) -> dict[str, TableInfo]:
    rows = await conn.fetch(TABLES_SQL)
    return {
        table_id(row["schema_name"], row["table_name"]): TableInfo(
            schema_name=row["schema_name"],
            table_name=row["table_name"],
            columns=(),
            estimated_rows=float(row["estimated_rows"]),
        )
        for row in rows
    }


async def _fetch_column_lookup(
    conn: asyncpg.Connection,
) -> dict[tuple[str, str], dict[int, str]]:
    lookup: dict[tuple[str, str], dict[int, str]] = defaultdict(dict)
    for row in await conn.fetch(COLUMN_NAMES_SQL):
        key = (row["schema_name"], row["table_name"])
        lookup[key][int(row["attnum"])] = row["column_name"]
    return lookup


async def _fetch_column_stats(
    conn: asyncpg.Connection,
) -> dict[tuple[str, str, str], float]:
    """Return ``(schema, table, column)`` → ``avg_width`` from ``pg_stats``."""
    stats: dict[tuple[str, str, str], float] = {}
    for row in await conn.fetch(COLUMN_STATS_SQL):
        key = (row["schema_name"], row["table_name"], row["column_name"])
        stats[key] = float(row["avg_width"])
    return stats


async def _attach_columns(
    conn: asyncpg.Connection,
    tables: dict[str, TableInfo],
    column_lookup: dict[tuple[str, str], dict[int, str]],
    stats: dict[tuple[str, str, str], float],
) -> None:
    grouped: dict[str, list[ColumnInfo]] = defaultdict(list)
    for row in await conn.fetch(COLUMNS_SQL):
        identifier = table_id(row["schema_name"], row["table_name"])
        identity = _identity_code(row["identity"])
        stat_key = (row["schema_name"], row["table_name"], row["column_name"])
        sequence_name = row["sequence_name"]
        is_identity = identity in {"a", "d"}
        grouped[identifier].append(
            ColumnInfo(
                name=row["column_name"],
                data_type=row["data_type"],
                not_null=bool(row["not_null"]),
                default_expression=row["default_expression"],
                is_identity=is_identity,
                identity_generation=_identity_label(identity),
                uses_serial=bool(sequence_name) and not is_identity,
                sequence_name=sequence_name,
                avg_width=stats.get(stat_key),
            )
        )
    for identifier, columns in grouped.items():
        if identifier in tables:
            tables[identifier] = _replace_columns(tables[identifier], tuple(columns))


def _identity_code(raw: bytes | str | None) -> str:
    """Normalize ``pg_attribute.attidentity`` to a single-character string."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode()
    return str(raw)


def _identity_label(code: str) -> str | None:
    if code == "a":
        return "ALWAYS"
    if code == "d":
        return "BY DEFAULT"
    return None


def _replace_columns(table: TableInfo, columns: tuple[ColumnInfo, ...]) -> TableInfo:
    return replace(table, columns=columns)


async def _attach_constraints(
    conn: asyncpg.Connection,
    tables: dict[str, TableInfo],
    column_lookup: dict[tuple[str, str], dict[int, str]],
) -> None:
    for row in await conn.fetch(CONSTRAINTS_SQL):
        identifier = table_id(row["schema_name"], row["table_name"])
        table = tables.get(identifier)
        if table is None:
            continue
        tables[identifier] = _apply_constraint_row(table, row, column_lookup)


def _apply_constraint_row(
    table: TableInfo,
    row: asyncpg.Record,
    column_lookup: dict[tuple[str, str], dict[int, str]],
) -> TableInfo:
    kind = _constraint_type_code(row["constraint_type"])
    key = (table.schema_name, table.table_name)
    cols = _attnums_to_names(column_lookup.get(key, {}), row["source_attnums"])
    if kind == "p":
        return _with_primary_key(table, cols)
    if kind == "u":
        return _with_unique(table, cols)
    if kind == "f":
        return _with_foreign_key(table, row, column_lookup, cols)
    if kind == "c":
        return _with_check(table, row["constraint_name"], row["definition"])
    return table


def _constraint_type_code(raw: bytes | str) -> str:
    if isinstance(raw, bytes):
        return raw.decode()
    return str(raw)


def _attnums_to_names(
    attnum_map: dict[int, str], attnums: list[int] | None
) -> tuple[str, ...]:
    if not attnums:
        return ()
    return tuple(attnum_map[int(num)] for num in attnums)


def _with_primary_key(table: TableInfo, columns: tuple[str, ...]) -> TableInfo:
    return replace(table, primary_key=columns)


def _with_unique(table: TableInfo, columns: tuple[str, ...]) -> TableInfo:
    return replace(table, unique_constraints=table.unique_constraints + (columns,))


def _with_check(table: TableInfo, name: str, definition: str) -> TableInfo:
    check = CheckConstraintInfo(name=name, definition=definition)
    return replace(table, check_constraints=table.check_constraints + (check,))


def _with_foreign_key(
    table: TableInfo,
    row: asyncpg.Record,
    column_lookup: dict[tuple[str, str], dict[int, str]],
    source_columns: tuple[str, ...],
) -> TableInfo:
    ref_key = (row["referenced_schema"], row["referenced_table"])
    ref_columns = _attnums_to_names(
        column_lookup.get(ref_key, {}), row["referenced_attnums"]
    )
    fk = ForeignKeyInfo(
        name=row["constraint_name"],
        source_columns=source_columns,
        referenced_schema=row["referenced_schema"],
        referenced_table=row["referenced_table"],
        referenced_columns=ref_columns,
        on_delete=_fk_action(row["definition"], "ON DELETE"),
        on_update=_fk_action(row["definition"], "ON UPDATE"),
        deferrable=bool(row["deferrable"]),
        initially_deferred=bool(row["initially_deferred"]),
    )
    return replace(table, foreign_keys=table.foreign_keys + (fk,))


def _fk_action(definition: str, keyword: str) -> str:
    """Extract ON DELETE / ON UPDATE action from a constraint definition."""
    upper = definition.upper()
    marker = keyword.upper()
    if marker not in upper:
        return "NO ACTION"
    tail = upper.split(marker, maxsplit=1)[1].strip()
    for action in ("CASCADE", "SET NULL", "SET DEFAULT", "RESTRICT", "NO ACTION"):
        if tail.startswith(action):
            return action
    return "NO ACTION"


async def _attach_indexes(
    conn: asyncpg.Connection,
    tables: dict[str, TableInfo],
    column_lookup: dict[tuple[str, str], dict[int, str]],
) -> None:
    for row in await conn.fetch(INDEXES_SQL):
        identifier = table_id(row["schema_name"], row["table_name"])
        table = tables.get(identifier)
        if table is None:
            continue
        key = (table.schema_name, table.table_name)
        columns = _attnums_to_names(column_lookup.get(key, {}), row["index_attnums"])
        index = IndexInfo(
            name=row["index_name"],
            is_unique=bool(row["is_unique"]),
            definition=row["definition"],
            columns=columns,
        )
        tables[identifier] = replace(table, indexes=table.indexes + (index,))


async def _fetch_views(conn: asyncpg.Connection) -> tuple[ViewInfo, ...]:
    """Return plain and materialized views in user schemas."""
    views: list[ViewInfo] = []
    for row in await conn.fetch(VIEWS_SQL):
        views.append(
            ViewInfo(
                schema_name=row["schema_name"],
                view_name=row["view_name"],
                kind="view",
            )
        )
    for row in await conn.fetch(MATVIEWS_SQL):
        views.append(
            ViewInfo(
                schema_name=row["schema_name"],
                view_name=row["view_name"],
                kind="materialized_view",
            )
        )
    return tuple(sorted(views, key=lambda view: view.identifier))


def _never_analyzed_warnings(
    tables: dict[str, TableInfo],
) -> tuple[CatalogWarning, ...]:
    warnings: list[CatalogWarning] = []
    for info in tables.values():
        if info.estimated_rows < 0:
            warnings.append(
                CatalogWarning(
                    code="never_analyzed",
                    message=(
                        f"Table {info.identifier} has never been analyzed; "
                        "run ANALYZE for better batch sizing."
                    ),
                    table_id=info.identifier,
                )
            )
    return tuple(warnings)

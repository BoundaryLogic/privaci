"""Apply schema replication DDL to the target database."""

from __future__ import annotations

import logging

import asyncpg

from privaci.catalog.models import CatalogResult, TableInfo
from privaci.catalog.partitions import config_table_id, is_partition_child
from privaci.config.models import Config, TableConfig
from privaci.errors import ConfigError, PreflightError
from privaci.schema.ddl import (
    emit_create_partition_child,
    emit_create_schema,
    emit_create_sequence,
    emit_create_table,
    emit_foreign_key,
    emit_unique_indexes,
)
from privaci.schema.extensions import emit_create_extension, required_extensions
from privaci.schema.sequences import sequence_columns

logger = logging.getLogger(__name__)

_STRATEGY_EXCLUDE = "exclude"


async def replicate_schema(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> None:
    """Clone in-scope source DDL into the target.

    Creates schemas and tables (honoring per-table strategy), then unique
    indexes and foreign keys. Does not stream rows.

    Raises:
        ConfigError: When ``exclude`` leaves a dangling NOT NULL FK.
        PreflightError: When DDL application fails.
    """
    validate_exclude_fks(catalog, config)
    tables = tables_in_load_order(catalog)
    await _create_schemas_and_tables(conn, catalog, config, tables)
    await _create_partition_children(conn, catalog, config, tables)
    await _create_foreign_keys(conn, catalog, config, tables)


async def _create_schemas_and_tables(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    tables: list[TableInfo],
) -> None:
    schemas = {t.schema_name for t in catalog.tables.values()}
    for schema_name in sorted(schemas):
        await _execute(conn, emit_create_schema(schema_name))
    for extension_name in required_extensions(catalog):
        await _execute(conn, emit_create_extension(extension_name))
    created_sequences: set[str] = set()
    for table in tables:
        if is_partition_child(table):
            continue
        if _resolve_strategy(table, config) == _STRATEGY_EXCLUDE:
            continue
        for column in sequence_columns(table):
            if column.uses_serial and column.sequence_name:
                if column.sequence_name not in created_sequences:
                    await _execute(conn, emit_create_sequence(column.sequence_name))
                    created_sequences.add(column.sequence_name)
        await _execute(conn, emit_create_table(table))
        for stmt in emit_unique_indexes(
            table, replicate_all=config.replicate_all_indexes
        ):
            await _execute(conn, stmt)


async def _create_partition_children(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    tables: list[TableInfo],
) -> None:
    for table in tables:
        if not is_partition_child(table):
            continue
        parent = catalog.tables.get(table.parent_partition or "")
        if parent is None:
            continue
        if _resolve_strategy(parent, config) == _STRATEGY_EXCLUDE:
            continue
        await _execute(conn, emit_create_partition_child(table, parent))


async def _create_foreign_keys(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    tables: list[TableInfo],
) -> None:
    for table in tables:
        if is_partition_child(table):
            continue
        if _resolve_strategy(table, config) == _STRATEGY_EXCLUDE:
            continue
        for fk in table.foreign_keys:
            await _execute(conn, emit_foreign_key(table, fk))


def _resolve_strategy(table: TableInfo, config: Config) -> str:
    table_cfg = config.tables.get(config_table_id(table))
    if table_cfg is None:
        return "transform"
    return table_cfg.strategy


def tables_in_load_order(catalog: CatalogResult) -> list[TableInfo]:
    ordered: list[TableInfo] = []
    seen: set[str] = set()
    for layer in catalog.load_plan.layers:
        for table_id in layer.table_ids:
            if table_id in seen:
                continue
            seen.add(table_id)
            ordered.append(catalog.tables[table_id])
    return ordered


def validate_exclude_fks(catalog: CatalogResult, config: Config) -> None:
    offenders = _collect_exclude_fk_offenders(catalog, config)
    if not offenders:
        return
    raise ConfigError(
        "Validating exclude strategy",
        cause="Excluded table is referenced by NOT NULL FKs: "
        + ", ".join(sorted(offenders)),
        remediation="Use strategy: empty, or set null_orphan_fks: true.",
    )


def _collect_exclude_fk_offenders(
    catalog: CatalogResult,
    config: Config,
) -> list[str]:
    offenders: list[str] = []
    for table in catalog.tables.values():
        cfg = config.tables.get(table.identifier)
        if cfg is None or cfg.strategy != _STRATEGY_EXCLUDE:
            continue
        offenders.extend(
            _offenders_for_excluded_table(catalog, config, table.identifier)
        )
    return offenders


def _offenders_for_excluded_table(
    catalog: CatalogResult,
    config: Config,
    excluded_id: str,
) -> list[str]:
    offenders: list[str] = []
    for other in catalog.tables.values():
        other_cfg = config.tables.get(other.identifier) or TableConfig()
        if other_cfg.strategy == _STRATEGY_EXCLUDE or other_cfg.null_orphan_fks:
            continue
        for fk in other.foreign_keys:
            if fk.referenced_id != excluded_id:
                continue
            for col_name in fk.source_columns:
                column = other.column_by_name(col_name)
                if column is not None and column.not_null:
                    offenders.append(f"{other.identifier}.{col_name}")
    return offenders


async def _execute(conn: asyncpg.Connection, sql: str) -> None:
    try:
        await conn.execute(sql)
    except asyncpg.PostgresError as exc:
        raise PreflightError(
            "Replicating schema to the target database",
            cause=f"DDL execution failed on the target ({type(exc).__name__}: {exc}).",
            remediation="Verify target permissions, required extensions, and retry.",
        ) from exc

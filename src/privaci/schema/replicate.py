"""Apply schema replication DDL to the target database."""

from __future__ import annotations

import logging

import asyncpg

from privaci.catalog.models import (
    CatalogResult,
    ForeignKeyInfo,
    FunctionInfo,
    TableInfo,
)
from privaci.catalog.partitions import config_table_id, is_partition_child
from privaci.config.models import Config, TableConfig
from privaci.errors import ConfigError
from privaci.schema.ddl import (
    emit_create_partition_child,
    emit_create_schema,
    emit_create_sequence,
    emit_create_table,
    emit_foreign_key,
    emit_unique_indexes,
    foreign_key_exists,
)
from privaci.schema.execute import execute_ddl
from privaci.schema.extensions import emit_create_extension, required_extensions
from privaci.schema.function_hoist import functions_required_for_pre_data
from privaci.schema.objects import ReplicatedObject, replicate_function_defs
from privaci.schema.orphan_fks import assert_orphan_nulling_allowed
from privaci.schema.sequences import sequence_columns
from privaci.schema.table_policy import is_excluded_table

logger = logging.getLogger(__name__)

_STRATEGY_EXCLUDE = "exclude"


async def replicate_schema(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> tuple[ReplicatedObject, ...]:
    """Apply **pre-data** DDL: structure required before row inserts.

    Order: schemas (tables ∪ hoisted functions) → extensions → DEFAULT/CHECK
    functions → tables/UNIQUE/FKs. Does not stream rows or create
    views/triggers/non-unique indexes.

    Raises:
        ConfigError: When ``exclude`` leaves a dangling NOT NULL FK.
        PreflightError: When DDL application fails.
    """
    validate_exclude_fks(catalog, config)
    tables = tables_in_load_order(catalog)
    pre_fns = functions_required_for_pre_data(catalog, config)
    await _create_pre_data_schemas(conn, catalog, pre_fns)
    for extension_name in required_extensions(catalog):
        await execute_ddl(conn, emit_create_extension(extension_name))
    created = await replicate_function_defs(conn, pre_fns, ddl_phase="pre-data")
    await _create_tables_and_unique_indexes(conn, config, tables)
    await _create_partition_children(conn, catalog, config, tables)
    await _create_foreign_keys(conn, catalog, config, tables)
    return tuple(created)


async def _create_pre_data_schemas(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    pre_fns: tuple[FunctionInfo, ...],
) -> None:
    schemas = {t.schema_name for t in catalog.tables.values()}
    schemas.update(fn.schema_name for fn in pre_fns)
    for schema_name in sorted(schemas):
        await execute_ddl(conn, emit_create_schema(schema_name))


async def _create_tables_and_unique_indexes(
    conn: asyncpg.Connection,
    config: Config,
    tables: list[TableInfo],
) -> None:
    created_sequences: set[str] = set()
    for table in tables:
        if is_partition_child(table):
            continue
        if _resolve_strategy(table, config) == _STRATEGY_EXCLUDE:
            continue
        for column in sequence_columns(table):
            if column.uses_serial and column.sequence_name:
                if column.sequence_name not in created_sequences:
                    await execute_ddl(conn, emit_create_sequence(column.sequence_name))
                    created_sequences.add(column.sequence_name)
        await execute_ddl(conn, emit_create_table(table))
        for stmt in emit_unique_indexes(table):
            await execute_ddl(conn, stmt)


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
        await execute_ddl(conn, emit_create_partition_child(table, parent))


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
            if _fk_references_excluded_or_missing(fk, catalog, config):
                logger.debug(
                    "Skipping FK %s on %s (referent excluded or not created)",
                    fk.name,
                    table.identifier,
                )
                continue
            if await foreign_key_exists(conn, table, fk.name):
                logger.debug(
                    "Skipping existing foreign key %s on %s",
                    fk.name,
                    table.identifier,
                )
                continue
            await execute_ddl(conn, emit_foreign_key(table, fk))


def _fk_references_excluded_or_missing(
    fk: ForeignKeyInfo,
    catalog: CatalogResult,
    config: Config,
) -> bool:
    """Return True when the FK parent is excluded or absent from the catalog."""
    referenced = catalog.tables.get(fk.referenced_id)
    if referenced is None:
        return True
    return _resolve_strategy(referenced, config) == _STRATEGY_EXCLUDE


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
    assert_orphan_nulling_allowed(catalog, config)
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
        if not is_excluded_table(table, config):
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
        if is_excluded_table(other, config):
            continue
        other_cfg = config.tables.get(config_table_id(other)) or TableConfig()
        # null_orphan_fks tables are validated by assert_orphan_nulling_allowed
        if other_cfg.null_orphan_fks:
            continue
        for fk in other.foreign_keys:
            if fk.referenced_id != excluded_id:
                continue
            for col_name in fk.source_columns:
                column = other.column_by_name(col_name)
                if column is not None and column.not_null:
                    offenders.append(f"{other.identifier}.{col_name}")
    return offenders

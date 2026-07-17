"""Assume-existing target schema validation (name + type compatibility)."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from privaci.catalog.models import CatalogResult, TableInfo
from privaci.catalog.partitions import config_table_id, is_partition_child
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.observability import Event, emit
from privaci.schema.replicate import tables_in_load_order

_TARGET_COLUMNS_SQL = """
SELECT
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = $1
  AND c.relname = $2
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attnum
"""

_TARGET_CATALOG_COLUMNS_SQL = """
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_catalog.pg_attribute a
  ON a.attrelid = c.oid
 AND a.attnum > 0
 AND NOT a.attisdropped
WHERE c.relkind IN ('r', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
  AND n.nspname NOT LIKE 'pg\\_%' ESCAPE '\\'
ORDER BY n.nspname, c.relname, a.attnum
"""

TargetColumns = dict[str, list[tuple[str, str]]]


@dataclass(frozen=True, slots=True)
class ColumnMismatch:
    """One incompatible or missing column on the target."""

    table_id: str
    column_name: str
    source_type: str | None
    target_type: str | None
    reason: str

    def __repr__(self) -> str:
        return (
            f"ColumnMismatch({self.table_id}.{self.column_name!r}, "
            f"reason={self.reason!r})"
        )


@dataclass(frozen=True, slots=True)
class AssumeExistingValidation:
    """Result of validating a prebuilt target against the source catalog."""

    tables_checked: int
    mismatches: tuple[ColumnMismatch, ...]

    @property
    def is_ok(self) -> bool:
        """Return True when every in-scope table passed name+type checks."""
        return not self.mismatches

    def __repr__(self) -> str:
        return (
            f"AssumeExistingValidation(tables={self.tables_checked}, "
            f"mismatches={len(self.mismatches)})"
        )


async def fetch_target_columns(
    conn: asyncpg.Connection,
    schema_name: str,
    table_name: str,
) -> list[tuple[str, str]]:
    """Return target columns as ``(name, format_type)`` in physical order."""
    rows = await conn.fetch(_TARGET_COLUMNS_SQL, schema_name, table_name)
    return [(str(row["column_name"]), str(row["data_type"])) for row in rows]


async def fetch_target_catalog_columns(
    conn: asyncpg.Connection,
) -> TargetColumns:
    """Return all target table columns in one catalog query."""
    rows = await conn.fetch(_TARGET_CATALOG_COLUMNS_SQL)
    result: TargetColumns = {}
    for row in rows:
        identifier = f"{row['schema_name']}.{row['table_name']}"
        columns = result.setdefault(identifier, [])
        if row["column_name"] is not None:
            columns.append((str(row["column_name"]), str(row["data_type"])))
    return result


def types_compatible(source_type: str, target_type: str) -> bool:
    """Return whether normalized ``format_type`` strings are compatible."""
    return _normalize_type(source_type) == _normalize_type(target_type)


def binary_copy_columns_match(
    source: TableInfo,
    target_columns: list[tuple[str, str]],
) -> bool:
    """Return True when target columns match source names, types, and order."""
    source_cols = [(column.name, column.data_type) for column in source.columns]
    if len(source_cols) != len(target_columns):
        return False
    return all(
        name == target_name and types_compatible(source_type, target_type)
        for (name, source_type), (target_name, target_type) in zip(
            source_cols, target_columns, strict=True
        )
    )


async def validate_assume_existing(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> AssumeExistingValidation:
    """Validate in-scope tables exist on target with compatible column types.

    Compatibility is name + type (order-independent). Extra target columns are
    allowed.
    """
    target_catalog = await fetch_target_catalog_columns(conn)
    mismatches: list[ColumnMismatch] = []
    tables_checked = 0
    for table in tables_in_load_order(catalog):
        if is_partition_child(table):
            continue
        if _strategy(table, config) == "exclude":
            continue
        tables_checked += 1
        mismatches.extend(_validate_table(table, target_catalog))
    return AssumeExistingValidation(
        tables_checked=tables_checked,
        mismatches=tuple(mismatches),
    )


def raise_validation_failed(validation: AssumeExistingValidation) -> None:
    """Raise :class:`PreflightError` summarizing validation mismatches."""
    if validation.is_ok:
        return
    details = "; ".join(_mismatch_detail(item) for item in validation.mismatches)
    emit(
        Event.PREFLIGHT_FAIL,
        checks=[
            {
                "name": "assume_existing",
                "status": "fail",
                "detail": details,
            }
        ],
    )
    raise PreflightError(
        "Validating assume_existing target schema",
        cause=details,
        remediation=(
            "Align the prebuilt target schema with the source (name and type), "
            "or use schema_mode: replicate for greenfield targets."
        ),
    )


def validation_failed_payload(
    validation: AssumeExistingValidation,
    *,
    passthrough_copy: str,
) -> dict[str, object]:
    """Build a PII-free audit payload for ``schema.validation_failed``."""
    return {
        "passthrough_copy": passthrough_copy,
        "tables_checked": validation.tables_checked,
        "mismatches": [
            {
                "table": item.table_id,
                "column": item.column_name,
                "source_type": item.source_type,
                "target_type": item.target_type,
                "reason": item.reason,
            }
            for item in validation.mismatches
        ],
    }


def validation_ok_payload(
    validation: AssumeExistingValidation,
    *,
    passthrough_copy: str,
) -> dict[str, object]:
    """Build a PII-free audit payload for ``schema.validated``."""
    return {
        "passthrough_copy": passthrough_copy,
        "tables_checked": validation.tables_checked,
    }


def _validate_table(
    table: TableInfo,
    target_catalog: TargetColumns,
) -> list[ColumnMismatch]:
    target_cols = target_catalog.get(table.identifier)
    if target_cols is None:
        return [
            ColumnMismatch(
                table_id=table.identifier,
                column_name="*",
                source_type=None,
                target_type=None,
                reason="missing_table",
            )
        ]
    by_name = {name: data_type for name, data_type in target_cols}
    mismatches: list[ColumnMismatch] = []
    for column in table.columns:
        target_type = by_name.get(column.name)
        if target_type is None:
            mismatches.append(
                ColumnMismatch(
                    table_id=table.identifier,
                    column_name=column.name,
                    source_type=column.data_type,
                    target_type=None,
                    reason="missing_column",
                )
            )
            continue
        if not types_compatible(column.data_type, target_type):
            mismatches.append(
                ColumnMismatch(
                    table_id=table.identifier,
                    column_name=column.name,
                    source_type=column.data_type,
                    target_type=target_type,
                    reason="type_mismatch",
                )
            )
    return mismatches


def _mismatch_detail(item: ColumnMismatch) -> str:
    if item.reason == "missing_table":
        return f"missing table {item.table_id}"
    if item.reason == "missing_column":
        return f"missing column {item.table_id}.{item.column_name}"
    return (
        f"type mismatch {item.table_id}.{item.column_name}: "
        f"source={item.source_type} target={item.target_type}"
    )


def _strategy(table: TableInfo, config: Config) -> str:
    table_cfg = config.tables.get(config_table_id(table))
    if table_cfg is None:
        return "transform"
    return table_cfg.strategy


def _normalize_type(data_type: str) -> str:
    return " ".join(data_type.strip().lower().split())

"""Catalog pattern detectors for relationships Postgres cannot model."""

from __future__ import annotations

import re
from collections import defaultdict

from privaci.catalog.models import CatalogWarning, ColumnInfo, TableInfo

_TYPE_SUFFIX = "_type"
_ID_SUFFIX = "_id"
_POLYMORPHIC_PREFIXES = ("commentable_", "subject_", "target_", "owner_")
_TEXT_TYPES = frozenset({"text", "character varying", "varchar"})
_INTEGER_TYPES = frozenset(
    {"integer", "bigint", "smallint", "uuid", "character varying", "varchar"}
)

# Column-name suffixes that conventionally point at a UNIQUE column elsewhere.
# Longest first so a column matches the most specific suffix exactly once.
_IMPLIED_FK_SUFFIXES = ("user_id", "username", "email", "mrn")


def mark_self_cycles(tables: dict[str, TableInfo]) -> dict[str, TableInfo]:
    """Flag tables that contain a self-referential foreign key."""
    from dataclasses import replace

    updated: dict[str, TableInfo] = {}
    for identifier, info in tables.items():
        has_self = any(fk.referenced_id == identifier for fk in info.foreign_keys)
        updated[identifier] = replace(info, self_cycle=has_self)
    return updated


def detect_polymorphic_fks(
    tables: dict[str, TableInfo],
) -> tuple[CatalogWarning, ...]:
    """Detect Rails-style polymorphic column pairs without catalog FKs."""
    warnings: list[CatalogWarning] = []
    for info in tables.values():
        warnings.extend(_table_polymorphic_warnings(info))
    return tuple(warnings)


def _table_polymorphic_warnings(table: TableInfo) -> list[CatalogWarning]:
    warnings: list[CatalogWarning] = []
    columns = {column.name: column for column in table.columns}
    catalog_fk_columns = {
        name for fk in table.foreign_keys for name in fk.source_columns
    }

    for prefix in _prefix_candidates(columns):
        type_col = f"{prefix}{_TYPE_SUFFIX}"
        id_col = f"{prefix}{_ID_SUFFIX}"
        if type_col not in columns or id_col not in columns:
            continue
        if type_col in catalog_fk_columns or id_col in catalog_fk_columns:
            continue
        if not _is_polymorphic_pair(columns[type_col], columns[id_col]):
            continue
        warnings.append(
            CatalogWarning(
                code="polymorphic_fk_warning",
                message=(
                    f"Table {table.identifier} has polymorphic columns "
                    f"{type_col}/{id_col} without a catalog foreign key; "
                    "referential integrity cannot be preserved automatically."
                ),
                table_id=table.identifier,
            )
        )
    return warnings


def _prefix_candidates(columns: dict[str, ColumnInfo]) -> set[str]:
    prefixes: set[str] = set()
    for name in columns:
        if name.endswith(_TYPE_SUFFIX):
            prefixes.add(name[: -len(_TYPE_SUFFIX)])
        for marker in _POLYMORPHIC_PREFIXES:
            if name.startswith(marker):
                prefixes.add(marker.rstrip("_"))
    return prefixes


def _is_polymorphic_pair(type_col: ColumnInfo, id_col: ColumnInfo) -> bool:
    type_base = _base_type(type_col.data_type)
    id_base = _base_type(id_col.data_type)
    return type_base in _TEXT_TYPES and id_base in _INTEGER_TYPES


def _base_type(data_type: str) -> str:
    return re.sub(r"\(.*\)$", "", data_type.strip().lower())


def detect_implied_fks(
    tables: dict[str, TableInfo],
    *,
    ignore: frozenset[str] = frozenset(),
) -> tuple[CatalogWarning, ...]:
    """Detect soft (implied) foreign keys from column-name conventions.

    Flags columns like ``<x>_email`` / ``<x>_mrn`` whose suffix matches a
    single-column UNIQUE column on another table, where no catalog foreign key
    exists. Each detected reference suggests a ``seed_alias`` so the masked
    values stay consistent with the referenced column.

    Args:
        tables: Introspected tables keyed by schema-qualified id.
        ignore: Source column paths (``schema.table.column``) to silence.

    Returns:
        One :class:`CatalogWarning` per detected implied foreign key.
    """
    targets = _unique_columns_by_name(tables)
    warnings: list[CatalogWarning] = []
    for table in tables.values():
        fk_columns = {name for fk in table.foreign_keys for name in fk.source_columns}
        for column in table.columns:
            warning = _implied_fk_warning(table, column, fk_columns, targets, ignore)
            if warning is not None:
                warnings.append(warning)
    return tuple(warnings)


def _implied_fk_warning(
    table: TableInfo,
    column: ColumnInfo,
    fk_columns: set[str],
    targets: dict[str, list[tuple[str, str]]],
    ignore: frozenset[str],
) -> CatalogWarning | None:
    suffix = _matched_suffix(column.name)
    if suffix is None or column.name in fk_columns:
        return None
    source_path = f"{table.identifier}.{column.name}"
    if source_path in ignore:
        return None
    candidates = [
        (tid, col)
        for tid, col in targets.get(suffix, ())
        if not (tid == table.identifier and col == column.name)
    ]
    if not candidates:
        return None
    target_id, target_col = _best_target(
        column.name, suffix, candidates, table.schema_name
    )
    target_path = f"{target_id}.{target_col}"
    return CatalogWarning(
        code="implied_fk_warning",
        message=(
            f"Table {table.identifier} column {column.name} looks like a soft "
            f"reference to {target_path} (UNIQUE) but no catalog foreign key "
            f"exists. Add 'seed_alias: {target_path}' on {source_path} to keep "
            "masked values consistent across both columns."
        ),
        table_id=table.identifier,
    )


def _matched_suffix(column_name: str) -> str | None:
    for suffix in _IMPLIED_FK_SUFFIXES:
        marker = f"_{suffix}"
        if column_name.endswith(marker) and len(column_name) > len(marker):
            return suffix
    return None


def _unique_columns_by_name(
    tables: dict[str, TableInfo],
) -> dict[str, list[tuple[str, str]]]:
    """Map a column name to the table/column pairs where it is single-UNIQUE."""
    by_name: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for table in tables.values():
        for column_name in _single_unique_columns(table):
            by_name[column_name].append((table.identifier, column_name))
    return by_name


def _single_unique_columns(table: TableInfo) -> set[str]:
    """Return columns guaranteed unique by a single-column PK, constraint, or index."""
    unique: set[str] = set()
    if len(table.primary_key) == 1:
        unique.add(table.primary_key[0])
    for constraint in table.unique_constraints:
        if len(constraint) == 1:
            unique.add(constraint[0])
    for index in table.indexes:
        if index.is_unique and len(index.columns) == 1:
            unique.add(index.columns[0])
    return unique


def _best_target(
    source_column: str,
    suffix: str,
    candidates: list[tuple[str, str]],
    source_schema: str,
) -> tuple[str, str]:
    """Pick the most likely target, preferring a table-name hint in the prefix."""
    prefix_parts = set(source_column[: -(len(suffix) + 1)].split("_"))

    def rank(candidate: tuple[str, str]) -> tuple[int, int, str]:
        target_id, _ = candidate
        name_hint = bool(_table_name_tokens(target_id) & prefix_parts)
        same_schema = target_id.split(".", 1)[0] == source_schema
        return (0 if name_hint else 1, 0 if same_schema else 1, target_id)

    return min(candidates, key=rank)


def _table_name_tokens(table_identifier: str) -> set[str]:
    name = table_identifier.split(".", 1)[1]
    tokens = {name}
    if name.endswith("s") and not name.endswith("ss"):
        tokens.add(name[:-1])
    return tokens

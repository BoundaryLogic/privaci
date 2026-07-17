"""Resolve FK columns that must be nulled when parents are excluded."""

from __future__ import annotations

from privaci.catalog.models import CatalogResult, TableInfo
from privaci.catalog.partitions import config_table_id
from privaci.config.models import Config
from privaci.errors import ConfigError
from privaci.schema.table_policy import is_excluded_table


def orphan_fk_columns_to_null(
    table: TableInfo,
    catalog: CatalogResult,
    config: Config,
) -> frozenset[str]:
    """Return nullable FK columns on ``table`` that reference excluded parents.

    When the child table itself is excluded, or ``null_orphan_fks`` is unset,
    returns empty. Callers must force the batch/cell path when this set is
    non-empty. NOT NULL orphan FKs are rejected by
    :func:`assert_orphan_nulling_allowed` before streaming.
    """
    if is_excluded_table(table, config):
        return frozenset()
    child_cfg = config.tables.get(config_table_id(table))
    if child_cfg is None or not child_cfg.null_orphan_fks:
        return frozenset()
    columns: set[str] = set()
    for fk in table.foreign_keys:
        if not _references_excluded_parent(fk.referenced_id, catalog, config):
            continue
        for col_name in fk.source_columns:
            column = table.column_by_name(col_name)
            if column is not None and not column.not_null:
                columns.add(col_name)
    return frozenset(columns)


def table_requires_orphan_nulling(
    table: TableInfo,
    catalog: CatalogResult,
    config: Config,
) -> bool:
    """Return True when streaming must null orphan FK columns for ``table``."""
    return bool(orphan_fk_columns_to_null(table, catalog, config))


def assert_orphan_nulling_allowed(catalog: CatalogResult, config: Config) -> None:
    """Fail when ``null_orphan_fks`` cannot null a NOT NULL FK to an excluded parent.

    Raises:
        ConfigError: When the flag is set but at least one referencing column is
            NOT NULL (nulling is impossible).
    """
    offenders = _not_null_orphan_offenders(catalog, config)
    if not offenders:
        return
    raise ConfigError(
        "Validating null_orphan_fks",
        cause=(
            "null_orphan_fks is set but these NOT NULL FK columns reference "
            "excluded parents: " + ", ".join(sorted(offenders))
        ),
        remediation=(
            "Make the FK columns nullable, remove null_orphan_fks, or use "
            "strategy: empty on the parent instead of exclude."
        ),
    )


def _not_null_orphan_offenders(
    catalog: CatalogResult,
    config: Config,
) -> list[str]:
    offenders: list[str] = []
    for table in catalog.tables.values():
        if is_excluded_table(table, config):
            continue
        child_cfg = config.tables.get(config_table_id(table))
        if child_cfg is None or not child_cfg.null_orphan_fks:
            continue
        for fk in table.foreign_keys:
            if not _references_excluded_parent(fk.referenced_id, catalog, config):
                continue
            for col_name in fk.source_columns:
                column = table.column_by_name(col_name)
                if column is not None and column.not_null:
                    offenders.append(f"{table.identifier}.{col_name}")
    return offenders


def _references_excluded_parent(
    referenced_id: str,
    catalog: CatalogResult,
    config: Config,
) -> bool:
    parent = catalog.tables.get(referenced_id)
    if parent is not None:
        return is_excluded_table(parent, config)
    parent_cfg = config.tables.get(referenced_id)
    return parent_cfg is not None and parent_cfg.strategy == "exclude"

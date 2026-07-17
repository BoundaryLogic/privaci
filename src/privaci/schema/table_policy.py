"""Canonical table load-strategy helpers shared across schema and preflight."""

from __future__ import annotations

from privaci.catalog.models import TableInfo
from privaci.catalog.partitions import config_table_id
from privaci.config.models import Config


def table_strategy(table: TableInfo, config: Config) -> str:
    """Return the configured load strategy for ``table``."""
    table_cfg = config.tables.get(config_table_id(table))
    if table_cfg is None:
        return "transform"
    return table_cfg.strategy


def excluded_table_ids(config: Config) -> frozenset[str]:
    """Return schema-qualified table ids configured with ``strategy: exclude``."""
    return frozenset(
        table_id
        for table_id, table_cfg in config.tables.items()
        if table_cfg.strategy == "exclude"
    )


def is_excluded_table(table: TableInfo, config: Config) -> bool:
    """Return True when ``table`` uses the exclude strategy."""
    return table_strategy(table, config) == "exclude"

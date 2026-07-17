"""Unit tests for canonical table policy helpers."""

from __future__ import annotations

from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.config.models import Config, TableConfig
from privaci.schema.table_policy import (
    excluded_table_ids,
    is_excluded_table,
    table_strategy,
)


def test_table_strategy_defaults_to_transform() -> None:
    table = TableInfo("public", "users", (ColumnInfo("id", "integer", True),))
    config = Config(version="1.0")

    assert table_strategy(table, config) == "transform"


def test_excluded_table_ids_and_predicate() -> None:
    table = TableInfo("public", "users", (ColumnInfo("id", "integer", True),))
    config = Config(
        version="1.0",
        tables={"public.users": TableConfig(strategy="exclude")},
    )

    assert excluded_table_ids(config) == frozenset({"public.users"})
    assert is_excluded_table(table, config) is True

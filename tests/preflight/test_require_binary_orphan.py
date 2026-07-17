"""Unit tests for require_binary vs orphan-null preflight."""

from __future__ import annotations

import pytest

from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    ForeignKeyInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.models import Config, TableConfig
from privaci.errors import PreflightError
from privaci.preflight.passthrough_copy import (
    assert_require_binary_allows_orphan_nulling,
)


def _catalog() -> CatalogResult:
    parent = TableInfo(
        schema_name="public",
        table_name="parents",
        columns=(ColumnInfo(name="id", data_type="integer", not_null=True),),
        primary_key=("id",),
    )
    child = TableInfo(
        schema_name="public",
        table_name="children",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="parent_id", data_type="integer", not_null=False),
        ),
        primary_key=("id",),
        foreign_keys=(
            ForeignKeyInfo(
                name="children_parent_fk",
                source_columns=("parent_id",),
                referenced_schema="public",
                referenced_table="parents",
                referenced_columns=("id",),
                on_delete="NO ACTION",
                on_update="NO ACTION",
                deferrable=False,
                initially_deferred=False,
            ),
        ),
    )
    return CatalogResult(
        tables={"public.parents": parent, "public.children": child},
        load_plan=LoadPlan(
            layers=(LoadLayer(table_ids=("public.parents", "public.children")),)
        ),
    )


def test_require_binary_rejects_orphan_nulling() -> None:
    catalog = _catalog()
    config = Config(
        version="1.0",
        passthrough_copy="require_binary",
        tables={
            "public.parents": TableConfig(strategy="exclude"),
            "public.children": TableConfig(null_orphan_fks=True),
        },
    )

    with pytest.raises(PreflightError, match="null_orphan_fks"):
        assert_require_binary_allows_orphan_nulling(catalog, config)


def test_require_binary_ok_without_orphan_nulling() -> None:
    catalog = _catalog()
    config = Config(version="1.0", passthrough_copy="require_binary")

    assert_require_binary_allows_orphan_nulling(catalog, config)

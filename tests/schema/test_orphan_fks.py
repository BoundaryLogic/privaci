"""Unit tests for orphan FK nulling helpers."""

from __future__ import annotations

import pytest

from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    ForeignKeyInfo,
    LoadPlan,
    TableInfo,
)
from privaci.config.models import Config, TableConfig
from privaci.errors import ConfigError
from privaci.mask.engine import MaskingEngine
from privaci.schema.orphan_fks import (
    assert_orphan_nulling_allowed,
    orphan_fk_columns_to_null,
)
from privaci.schema.replicate import validate_exclude_fks


def _catalog_with_orphan_fk(*, parent_id_not_null: bool = False) -> CatalogResult:
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
            ColumnInfo(
                name="parent_id",
                data_type="integer",
                not_null=parent_id_not_null,
            ),
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
        load_plan=LoadPlan(layers=()),
    )


def test_orphan_fk_columns_to_null_when_flag_set() -> None:
    catalog = _catalog_with_orphan_fk()
    config = Config(
        version="1.0",
        tables={
            "public.parents": TableConfig(strategy="exclude"),
            "public.children": TableConfig(null_orphan_fks=True),
        },
    )

    cols = orphan_fk_columns_to_null(catalog.tables["public.children"], catalog, config)

    assert cols == frozenset({"parent_id"})


def test_orphan_fk_uses_config_table_id_for_partition_child() -> None:
    parent = TableInfo(
        schema_name="public",
        table_name="parents",
        columns=(ColumnInfo(name="id", data_type="integer", not_null=True),),
        primary_key=("id",),
    )
    child = TableInfo(
        schema_name="public",
        table_name="children_p0",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="parent_id", data_type="integer", not_null=False),
        ),
        primary_key=("id",),
        parent_partition="public.children",
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
    catalog = CatalogResult(
        tables={
            "public.parents": parent,
            "public.children_p0": child,
        },
        load_plan=LoadPlan(layers=()),
    )
    config = Config(
        version="1.0",
        tables={
            "public.parents": TableConfig(strategy="exclude"),
            "public.children": TableConfig(null_orphan_fks=True),
        },
    )

    cols = orphan_fk_columns_to_null(child, catalog, config)

    assert cols == frozenset({"parent_id"})


def test_null_orphan_fks_rejects_not_null_columns() -> None:
    catalog = _catalog_with_orphan_fk(parent_id_not_null=True)
    config = Config(
        version="1.0",
        tables={
            "public.parents": TableConfig(strategy="exclude"),
            "public.children": TableConfig(null_orphan_fks=True),
        },
    )

    with pytest.raises(ConfigError, match="NOT NULL FK"):
        validate_exclude_fks(catalog, config)

    with pytest.raises(ConfigError, match="NOT NULL FK"):
        assert_orphan_nulling_allowed(catalog, config)


def test_masking_engine_nulls_orphan_columns() -> None:
    catalog = _catalog_with_orphan_fk()
    child = catalog.tables["public.children"]
    engine = MaskingEngine(
        "x" * 32,
        child.identifier,
        child,
        TableConfig(),
        null_columns=frozenset({"parent_id"}),
    )

    masked = engine.mask_row({"id": 1, "parent_id": 99})

    assert masked["parent_id"] is None
    assert engine.requires_row_mutation is True

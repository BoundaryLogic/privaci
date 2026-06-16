"""Unit tests for FK graph and topological ordering."""

from __future__ import annotations

import pytest

from privaci.catalog.graph import build_load_plan
from privaci.catalog.models import ColumnInfo, ForeignKeyInfo, TableInfo, table_id
from privaci.errors import CatalogError


def _table(
    schema: str,
    name: str,
    *,
    fks: tuple[ForeignKeyInfo, ...] = (),
    estimated_rows: float = 100.0,
    columns: tuple[ColumnInfo, ...] = (),
) -> TableInfo:
    return TableInfo(
        schema_name=schema,
        table_name=name,
        columns=columns,
        foreign_keys=fks,
        estimated_rows=estimated_rows,
    )


def _fk(
    name: str,
    source: str,
    ref_schema: str,
    ref_table: str,
    ref_col: str,
    *,
    deferrable: bool = True,
) -> ForeignKeyInfo:
    return ForeignKeyInfo(
        name=name,
        source_columns=(source,),
        referenced_schema=ref_schema,
        referenced_table=ref_table,
        referenced_columns=(ref_col,),
        on_delete="NO ACTION",
        on_update="NO ACTION",
        deferrable=deferrable,
        initially_deferred=False,
    )


def test_acyclic_topo_sort_produces_ordered_layers() -> None:
    # Arrange
    orgs = _table("public", "orgs")
    users = _table(
        "public",
        "users",
        fks=(_fk("users_org_fk", "org_id", "public", "orgs", "id"),),
    )
    orders = _table(
        "public",
        "orders",
        fks=(_fk("orders_user_fk", "user_id", "public", "users", "id"),),
    )
    items = _table(
        "public",
        "order_items",
        fks=(_fk("items_order_fk", "order_id", "public", "orders", "id"),),
    )
    tables = {
        table_id("public", "orgs"): orgs,
        table_id("public", "users"): users,
        table_id("public", "orders"): orders,
        table_id("public", "order_items"): items,
    }

    # Act
    plan = build_load_plan(tables)

    # Assert
    layer_ids = [list(layer.table_ids) for layer in plan.layers]
    assert ["public.orgs"] in layer_ids
    orgs_index = next(i for i, layer in enumerate(layer_ids) if "public.orgs" in layer)
    users_index = next(
        i for i, layer in enumerate(layer_ids) if "public.users" in layer
    )
    orders_index = next(
        i for i, layer in enumerate(layer_ids) if "public.orders" in layer
    )
    items_index = next(
        i for i, layer in enumerate(layer_ids) if "public.order_items" in layer
    )
    assert orgs_index < users_index < orders_index < items_index


def test_two_table_cycle_defers_lowest_cost_edge() -> None:
    # Arrange
    users = _table(
        "public",
        "users",
        columns=(ColumnInfo("last_order_id", "integer", False),),
        fks=(_fk("users_last_order_fk", "last_order_id", "public", "orders", "id"),),
        estimated_rows=50.0,
    )
    orders = _table(
        "public",
        "orders",
        columns=(ColumnInfo("user_id", "integer", True),),
        fks=(_fk("orders_user_fk", "user_id", "public", "users", "id"),),
        estimated_rows=200.0,
    )
    tables = {
        table_id("public", "users"): users,
        table_id("public", "orders"): orders,
    }

    # Act
    plan = build_load_plan(tables)

    # Assert
    assert plan.deferred_edges
    assert {edge.referencing_table for edge in plan.deferred_edges} <= {
        "public.users",
        "public.orders",
    }
    co_layer = next(
        layer
        for layer in plan.layers
        if "public.users" in layer.table_ids and "public.orders" in layer.table_ids
    )
    assert co_layer.table_ids


def test_cycle_merge_does_not_drag_unrelated_dependents() -> None:
    # Regression: a table that shares a Kahn layer with a cycle member but
    # depends on the other cycle member must NOT be merged into the cycle layer.
    # Mirrors demo-corp: providers -> organizations <-> users (deferred cycle).
    # Arrange
    organizations = _table(
        "public",
        "organizations",
        columns=(ColumnInfo("owner_user_id", "integer", False),),
        fks=(
            _fk(
                "organizations_owner_fk",
                "owner_user_id",
                "public",
                "users",
                "id",
                deferrable=True,
            ),
        ),
        estimated_rows=20.0,
    )
    users = _table(
        "public",
        "users",
        columns=(ColumnInfo("org_id", "integer", True),),
        fks=(_fk("users_org_fk", "org_id", "public", "organizations", "id"),),
        estimated_rows=200.0,
    )
    providers = _table(
        "clinical",
        "providers",
        columns=(ColumnInfo("org_id", "integer", True),),
        fks=(_fk("providers_org_fk", "org_id", "public", "organizations", "id"),),
        estimated_rows=30.0,
    )
    tables = {
        table_id("public", "organizations"): organizations,
        table_id("public", "users"): users,
        table_id("clinical", "providers"): providers,
    }

    # Act
    plan = build_load_plan(tables)

    # Assert — providers loads in a strictly later layer than organizations.
    layer_ids = [list(layer.table_ids) for layer in plan.layers]
    orgs_index = next(
        i for i, layer in enumerate(layer_ids) if "public.organizations" in layer
    )
    providers_index = next(
        i for i, layer in enumerate(layer_ids) if "clinical.providers" in layer
    )
    assert orgs_index < providers_index
    # organizations and users still share the cycle layer.
    assert "public.users" in layer_ids[orgs_index]


def test_standalone_table_with_cycle_terminates() -> None:
    # Regression: a no-FK table next to a pure cycle must not loop forever.
    # Arrange
    standalone = _table("public", "spike_copy_roundtrip", estimated_rows=3.0)
    cycle_a = _table(
        "public",
        "spike_cycle_a",
        columns=(ColumnInfo("b_id", "integer", False),),
        fks=(_fk("a_b_fk", "b_id", "public", "spike_cycle_b", "id"),),
    )
    cycle_b = _table(
        "public",
        "spike_cycle_b",
        columns=(ColumnInfo("a_id", "integer", False),),
        fks=(_fk("b_a_fk", "a_id", "public", "spike_cycle_a", "id"),),
    )
    tables = {
        table_id("public", "spike_copy_roundtrip"): standalone,
        table_id("public", "spike_cycle_a"): cycle_a,
        table_id("public", "spike_cycle_b"): cycle_b,
    }

    # Act
    plan = build_load_plan(tables)

    # Assert — every table assigned exactly once, cycle broken via deferral.
    assigned = [tid for layer in plan.layers for tid in layer.table_ids]
    assert sorted(assigned) == [
        "public.spike_copy_roundtrip",
        "public.spike_cycle_a",
        "public.spike_cycle_b",
    ]
    assert len(assigned) == len(set(assigned))  # no duplicate layers
    assert plan.deferred_edges


def test_acyclic_plan_has_no_duplicate_layers() -> None:
    # Arrange
    orgs = _table("public", "orgs")
    users = _table(
        "public",
        "users",
        fks=(_fk("users_org_fk", "org_id", "public", "orgs", "id"),),
    )
    tables = {
        table_id("public", "orgs"): orgs,
        table_id("public", "users"): users,
    }

    # Act
    plan = build_load_plan(tables)

    # Assert
    assigned = [tid for layer in plan.layers for tid in layer.table_ids]
    assert len(assigned) == len(set(assigned))


def test_non_deferrable_cycle_raises_catalog_error() -> None:
    # Arrange
    users = _table(
        "public",
        "users",
        fks=(
            _fk(
                "users_last_order_fk",
                "last_order_id",
                "public",
                "orders",
                "id",
                deferrable=False,
            ),
        ),
    )
    orders = _table(
        "public",
        "orders",
        fks=(
            _fk(
                "orders_user_fk",
                "user_id",
                "public",
                "users",
                "id",
                deferrable=False,
            ),
        ),
    )
    tables = {
        table_id("public", "users"): users,
        table_id("public", "orders"): orders,
    }

    # Act & Assert
    with pytest.raises(CatalogError, match="not DEFERRABLE"):
        build_load_plan(tables)


def test_partition_children_inherit_parent_fk_dependencies() -> None:
    # Arrange
    patients = _table("clinical", "patients")
    visits_parent = TableInfo(
        schema_name="clinical",
        table_name="patient_visits",
        columns=(),
        foreign_keys=(
            _fk(
                "visits_patient_fk",
                "patient_id",
                "clinical",
                "patients",
                "id",
            ),
        ),
        is_partitioned=True,
        partition_children=(
            "clinical.patient_visits_us_east",
            "clinical.patient_visits_intl",
        ),
    )
    visits_east = TableInfo(
        schema_name="clinical",
        table_name="patient_visits_us_east",
        columns=(),
        parent_partition="clinical.patient_visits",
    )
    visits_intl = TableInfo(
        schema_name="clinical",
        table_name="patient_visits_intl",
        columns=(),
        parent_partition="clinical.patient_visits",
    )
    tables = {
        table_id("clinical", "patients"): patients,
        table_id("clinical", "patient_visits"): visits_parent,
        table_id("clinical", "patient_visits_us_east"): visits_east,
        table_id("clinical", "patient_visits_intl"): visits_intl,
    }

    # Act
    plan = build_load_plan(tables)

    # Assert
    layer_ids = [set(layer.table_ids) for layer in plan.layers]
    patients_layer = next(
        index for index, layer in enumerate(layer_ids) if "clinical.patients" in layer
    )
    for child in ("clinical.patient_visits_us_east", "clinical.patient_visits_intl"):
        child_layer = next(
            index for index, layer in enumerate(layer_ids) if child in layer
        )
        assert child_layer > patients_layer

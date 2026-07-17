"""Unit tests for function/view dependency ordering helpers."""

from __future__ import annotations

from privaci.catalog.audit_skipped import iter_skipped_object_audits
from privaci.catalog.models import (
    CatalogResult,
    FunctionInfo,
    LoadPlan,
    ViewInfo,
)
from privaci.catalog.routines import functions_in_dependency_order
from privaci.catalog.views_meta import plain_views_in_dependency_order
from privaci.config.models import Config, TableConfig
from privaci.schema.elevated import (
    disposition_for_function,
    disposition_for_view,
)


def test_functions_in_dependency_order_puts_callee_first() -> None:
    callee = FunctionInfo(
        schema_name="public",
        function_name="base_fn",
        identity_args="",
        create_sql=(
            "CREATE FUNCTION public.base_fn() RETURNS int "
            "AS $$ SELECT 1 $$ LANGUAGE sql"
        ),
        language="sql",
        is_elevated=False,
    )
    caller = FunctionInfo(
        schema_name="public",
        function_name="wrap_fn",
        identity_args="",
        create_sql=(
            "CREATE FUNCTION public.wrap_fn() RETURNS int "
            "AS $$ SELECT public.base_fn() $$ LANGUAGE sql"
        ),
        language="sql",
        is_elevated=False,
        depends_on_functions=("public.base_fn",),
    )

    ordered = functions_in_dependency_order((caller, callee))

    assert [fn.identifier for fn in ordered] == ["public.base_fn", "public.wrap_fn"]


def test_plain_views_in_dependency_order_puts_base_first() -> None:
    base = ViewInfo(
        schema_name="public",
        view_name="base_v",
        kind="view",
        definition="SELECT 1",
        is_elevated=False,
    )
    child = ViewInfo(
        schema_name="public",
        view_name="child_v",
        kind="view",
        definition="SELECT * FROM public.base_v",
        is_elevated=False,
        depends_on=("public.base_v",),
    )

    ordered = plain_views_in_dependency_order((child, base))

    assert [view.identifier for view in ordered] == [
        "public.base_v",
        "public.child_v",
    ]


def test_iter_skipped_respects_elevated_skip_disposition() -> None:
    catalog = CatalogResult(
        tables={},
        load_plan=LoadPlan(layers=()),
        views=(
            ViewInfo(
                schema_name="public",
                view_name="ok_v",
                kind="view",
                definition="SELECT 1",
                is_elevated=False,
            ),
            ViewInfo(
                schema_name="public",
                view_name="elev_v",
                kind="view",
                definition="SELECT 1",
                is_elevated=True,
            ),
            ViewInfo(
                schema_name="public",
                view_name="mv",
                kind="materialized_view",
                definition="SELECT 1",
            ),
        ),
    )
    config = Config(
        version="1.0",
        elevated_objects={"public.elev_v": "skip"},
    )

    entries = list(iter_skipped_object_audits(catalog, config))

    assert ("public", "ok_v", {"kind": "view"}) not in entries
    assert (
        "public",
        "elev_v",
        {"kind": "view", "reason": "elevated_object_skipped"},
    ) in entries
    assert ("public", "mv", {"kind": "materialized_view"}) in entries


def test_iter_skipped_marks_views_with_excluded_dependencies() -> None:
    catalog = CatalogResult(
        tables={},
        load_plan=LoadPlan(layers=()),
        views=(
            ViewInfo(
                schema_name="public",
                view_name="revenue_v",
                kind="view",
                definition="SELECT 1",
                is_elevated=False,
                depends_on=("public.invoices",),
            ),
        ),
    )
    config = Config(
        version="1.0",
        tables={"public.invoices": TableConfig(strategy="exclude")},
    )

    entries = list(iter_skipped_object_audits(catalog, config))

    assert entries == [
        (
            "public",
            "revenue_v",
            {"kind": "view", "reason": "dependency_excluded"},
        )
    ]


def test_disposition_helpers_for_flags_and_elevated() -> None:
    view = ViewInfo(
        schema_name="public",
        view_name="v",
        kind="view",
        definition="SELECT 1",
        is_elevated=True,
    )
    function = FunctionInfo(
        schema_name="public",
        function_name="f",
        identity_args="",
        create_sql=("CREATE FUNCTION public.f() RETURNS void AS $$ $$ LANGUAGE sql"),
        language="sql",
        is_elevated=False,
    )
    config = Config(version="1.0", replicate_views=False, replicate_functions=True)

    assert disposition_for_view(view, config) == "skip"
    assert disposition_for_function(function, config) == "replicate"

"""Unit tests for elevated-object disposition helpers."""

from __future__ import annotations

import pytest

from privaci.catalog.models import (
    CatalogResult,
    FunctionInfo,
    LoadPlan,
    ViewInfo,
)
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.schema.elevated import (
    validate_elevated_dispositions,
    validate_function_excluded_deps,
)


def _config(**kwargs: object) -> Config:
    base = {
        "version": "1.0",
        "tables": {},
    }
    base.update(kwargs)
    return Config(**base)  # type: ignore[arg-type]


def _catalog(
    *,
    views: tuple[ViewInfo, ...] = (),
    functions: tuple[FunctionInfo, ...] = (),
) -> CatalogResult:
    return CatalogResult(
        tables={},
        load_plan=LoadPlan(layers=()),
        views=views,
        functions=functions,
    )


def test_unresolved_elevated_view_fails() -> None:
    catalog = _catalog(
        views=(
            ViewInfo(
                schema_name="clinical",
                view_name="admin_v",
                kind="view",
                definition="SELECT 1",
                is_elevated=True,
            ),
        )
    )

    with pytest.raises(PreflightError, match="clinical.admin_v"):
        validate_elevated_dispositions(catalog, _config())


def test_explicit_skip_disposition_passes() -> None:
    catalog = _catalog(
        views=(
            ViewInfo(
                schema_name="clinical",
                view_name="admin_v",
                kind="view",
                definition="SELECT 1",
                is_elevated=True,
            ),
        )
    )

    validate_elevated_dispositions(
        catalog,
        _config(elevated_objects={"clinical.admin_v": "skip"}),
    )


def test_function_excluded_table_dependency_fails() -> None:
    catalog = _catalog(
        functions=(
            FunctionInfo(
                schema_name="public",
                function_name="touch_users",
                identity_args="",
                create_sql=(
                    "CREATE FUNCTION public.touch_users() "
                    "RETURNS void AS $$ $$ LANGUAGE sql"
                ),
                language="sql",
                is_elevated=False,
                depends_on_tables=("public.users",),
            ),
        )
    )
    from privaci.config.models import TableConfig

    with pytest.raises(PreflightError, match="public.users"):
        validate_function_excluded_deps(
            catalog,
            _config(tables={"public.users": TableConfig(strategy="exclude")}),
        )

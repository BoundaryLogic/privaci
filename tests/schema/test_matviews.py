"""Unit tests for matview DDL helpers and refresh gating."""

from __future__ import annotations

import pytest

from privaci.catalog.models import CatalogResult, LoadPlan, ViewInfo
from privaci.catalog.views_meta import matviews_in_dependency_order, matviews_in_scope
from privaci.config.models import Config, TableConfig
from privaci.errors import PreflightError
from privaci.schema.objects import (
    ReplicatedObject,
    emit_create_matview,
    refresh_materialized_views,
    replicate_functions_and_views,
)


def test_matviews_in_dependency_order_puts_dependency_first() -> None:
    child = ViewInfo(
        schema_name="public",
        view_name="child_mv",
        kind="materialized_view",
        definition="SELECT 1",
        depends_on=("public.parent_mv",),
    )
    parent = ViewInfo(
        schema_name="public",
        view_name="parent_mv",
        kind="materialized_view",
        definition="SELECT 1",
    )
    plain = ViewInfo(
        schema_name="public",
        view_name="plain_v",
        kind="view",
        definition="SELECT 1",
    )

    ordered = matviews_in_dependency_order((child, parent, plain))

    assert [view.view_name for view in ordered] == ["parent_mv", "child_mv"]


def test_matviews_in_scope_skips_excluded_deps() -> None:
    views = (
        ViewInfo(
            schema_name="public",
            view_name="tickets_open_mv",
            kind="materialized_view",
            definition="SELECT 1",
            depends_on=("public.tickets",),
        ),
        ViewInfo(
            schema_name="public",
            view_name="ok_mv",
            kind="materialized_view",
            definition="SELECT 1",
            depends_on=("public.users",),
        ),
    )

    in_scope = matviews_in_scope(
        views,
        replicate=True,
        excluded_table_ids=frozenset({"public.tickets"}),
    )

    assert [view.view_name for view in in_scope] == ["ok_mv"]


def test_emit_create_matview_requires_definition() -> None:
    view = ViewInfo(
        schema_name="public",
        view_name="empty_mv",
        kind="materialized_view",
        definition=None,
    )

    with pytest.raises(PreflightError):
        emit_create_matview(view)


def test_replicated_object_definition_only_flag() -> None:
    obj = ReplicatedObject(
        schema_name="public",
        object_name="tickets_open_mv",
        kind="materialized_view",
        is_elevated=False,
        definition_only=True,
    )

    assert obj.definition_only is True


@pytest.mark.asyncio
async def test_refresh_materialized_views_noop_when_disabled(
    mocker: pytest.MockFixture,
) -> None:
    conn = mocker.AsyncMock()
    catalog = CatalogResult(
        tables={},
        load_plan=LoadPlan(layers=()),
        views=(
            ViewInfo(
                schema_name="public",
                view_name="tickets_open_mv",
                kind="materialized_view",
                definition="SELECT 1",
            ),
        ),
    )
    config = Config(version="1.0", replicate_materialized_views=True)

    refreshed = await refresh_materialized_views(conn, catalog, config)

    assert refreshed == ()
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_materialized_views_skips_excluded_deps(
    mocker: pytest.MockFixture,
) -> None:
    conn = mocker.AsyncMock()
    catalog = CatalogResult(
        tables={},
        load_plan=LoadPlan(layers=()),
        views=(
            ViewInfo(
                schema_name="public",
                view_name="tickets_open_mv",
                kind="materialized_view",
                definition="SELECT 1",
                depends_on=("public.tickets",),
            ),
            ViewInfo(
                schema_name="public",
                view_name="ok_mv",
                kind="materialized_view",
                definition="SELECT 1",
                depends_on=("public.users",),
            ),
        ),
    )
    config = Config(
        version="1.0",
        replicate_materialized_views=True,
        refresh_materialized_views=True,
        tables={"public.tickets": TableConfig(strategy="exclude")},
    )

    refreshed = await refresh_materialized_views(conn, catalog, config)

    assert refreshed == (("public", "ok_mv"),)
    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_replicate_matviews_drops_dependents_before_parents(
    mocker: pytest.MockFixture,
) -> None:
    conn = mocker.AsyncMock()
    catalog = CatalogResult(
        tables={},
        load_plan=LoadPlan(layers=()),
        views=(
            ViewInfo(
                schema_name="public",
                view_name="child_mv",
                kind="materialized_view",
                definition="SELECT 1",
                depends_on=("public.parent_mv",),
            ),
            ViewInfo(
                schema_name="public",
                view_name="parent_mv",
                kind="materialized_view",
                definition="SELECT 1",
            ),
        ),
    )
    config = Config(version="1.0", replicate_materialized_views=True)

    await replicate_functions_and_views(conn, catalog, config)

    drop_sql = [
        call.args[0]
        for call in conn.execute.await_args_list
        if "DROP MATERIALIZED VIEW" in call.args[0]
    ]
    assert "child_mv" in drop_sql[0]
    assert "parent_mv" in drop_sql[1]

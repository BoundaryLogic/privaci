"""View and materialized-view metadata for schema replication."""

from __future__ import annotations

from collections import defaultdict

import asyncpg

from privaci.catalog.models import ViewInfo, table_id
from privaci.catalog.queries import MATVIEWS_SQL, VIEW_DEPENDENCIES_SQL, VIEWS_SQL


async def fetch_views(conn: asyncpg.Connection) -> tuple[ViewInfo, ...]:
    """Return plain and materialized views with definitions and elevated markers."""
    deps = await _view_dependencies(conn)
    views: list[ViewInfo] = []
    for row in await conn.fetch(VIEWS_SQL):
        identifier = table_id(row["schema_name"], row["view_name"])
        views.append(
            ViewInfo(
                schema_name=row["schema_name"],
                view_name=row["view_name"],
                kind="view",
                definition=row["definition"],
                is_elevated=not bool(row["security_invoker"]),
                depends_on=tuple(sorted(deps.get(identifier, ()))),
            )
        )
    for row in await conn.fetch(MATVIEWS_SQL):
        identifier = table_id(row["schema_name"], row["view_name"])
        views.append(
            ViewInfo(
                schema_name=row["schema_name"],
                view_name=row["view_name"],
                kind="materialized_view",
                definition=row["definition"],
                is_elevated=False,
                depends_on=tuple(sorted(deps.get(identifier, ()))),
            )
        )
    return tuple(sorted(views, key=lambda item: (item.kind, item.identifier)))


async def _view_dependencies(conn: asyncpg.Connection) -> dict[str, set[str]]:
    deps: dict[str, set[str]] = defaultdict(set)
    for row in await conn.fetch(VIEW_DEPENDENCIES_SQL):
        view_id = table_id(row["view_schema"], row["view_name"])
        ref_id = table_id(row["ref_schema"], row["ref_name"])
        if view_id != ref_id:
            deps[view_id].add(ref_id)
    return deps


def plain_views_in_dependency_order(views: tuple[ViewInfo, ...]) -> list[ViewInfo]:
    """Return plain views ordered so referenced views appear first."""
    return _topo_order({view.identifier: view for view in views if view.kind == "view"})


def matviews_in_dependency_order(views: tuple[ViewInfo, ...]) -> list[ViewInfo]:
    """Return materialized views ordered so referenced matviews appear first."""
    return _topo_order(
        {view.identifier: view for view in views if view.kind == "materialized_view"}
    )


def matviews_in_scope(
    views: tuple[ViewInfo, ...],
    *,
    replicate: bool,
    excluded_table_ids: frozenset[str],
) -> list[ViewInfo]:
    """Return in-scope matviews in dependency order for create, refresh, or skip.

    Excludes matviews whose ``depends_on`` intersects ``excluded_table_ids``.
    When ``replicate`` is false, returns an empty list (caller handles skip audits).
    """
    if not replicate:
        return []
    return [
        view
        for view in matviews_in_dependency_order(views)
        if not excluded_table_ids.intersection(view.depends_on)
    ]


def _topo_order(nodes: dict[str, ViewInfo]) -> list[ViewInfo]:
    pending = set(nodes)
    ordered: list[ViewInfo] = []
    while pending:
        ready = [
            vid
            for vid in sorted(pending)
            if all(dep not in pending for dep in nodes[vid].depends_on if dep in nodes)
        ]
        if not ready:
            ordered.extend(nodes[vid] for vid in sorted(pending))
            break
        for vid in ready:
            pending.remove(vid)
            ordered.append(nodes[vid])
    return ordered

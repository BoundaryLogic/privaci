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
    plain = {view.identifier: view for view in views if view.kind == "view"}
    pending = set(plain)
    ordered: list[ViewInfo] = []
    while pending:
        ready = [
            vid
            for vid in sorted(pending)
            if all(dep not in pending for dep in plain[vid].depends_on if dep in plain)
        ]
        if not ready:
            ordered.extend(plain[vid] for vid in sorted(pending))
            break
        for vid in ready:
            pending.remove(vid)
            ordered.append(plain[vid])
    return ordered

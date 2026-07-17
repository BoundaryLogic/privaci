"""Replicate functions, plain views, and optional materialized-view shells."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from privaci.catalog.identifiers import qualify, quote_pg_identifier
from privaci.catalog.models import CatalogResult, FunctionInfo, ViewInfo
from privaci.catalog.routines import functions_in_dependency_order
from privaci.catalog.views_meta import (
    matviews_in_scope,
    plain_views_in_dependency_order,
)
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.schema.elevated import disposition_for_function, disposition_for_view
from privaci.schema.table_policy import excluded_table_ids


@dataclass(frozen=True, slots=True)
class ReplicatedObject:
    """One object successfully created during schema replication."""

    schema_name: str
    object_name: str
    kind: str
    is_elevated: bool
    depends_on: tuple[str, ...] = ()
    definition_only: bool = False

    def __repr__(self) -> str:
        return (
            f"ReplicatedObject({self.schema_name}.{self.object_name!r}, "
            f"kind={self.kind!r}, elevated={self.is_elevated}, "
            f"definition_only={self.definition_only})"
        )


async def replicate_functions_and_views(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> tuple[ReplicatedObject, ...]:
    """Create functions, plain views, then optional matview shells."""
    created: list[ReplicatedObject] = []
    created.extend(await _replicate_functions(conn, catalog, config))
    created.extend(await _replicate_views(conn, catalog, config))
    created.extend(await _replicate_matviews(conn, catalog, config))
    return tuple(created)


async def _replicate_functions(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> list[ReplicatedObject]:
    created: list[ReplicatedObject] = []
    for function in functions_in_dependency_order(catalog.functions):
        if disposition_for_function(function, config) != "replicate":
            continue
        await _execute(conn, function.create_sql)
        created.append(
            ReplicatedObject(
                schema_name=function.schema_name,
                object_name=_function_audit_name(function),
                kind="function",
                is_elevated=function.is_elevated,
                depends_on=function.depends_on_functions + function.depends_on_tables,
            )
        )
    return created


def _function_audit_name(function: FunctionInfo) -> str:
    if function.identity_args.strip():
        return f"{function.function_name}({function.identity_args})"
    return function.function_name


def _in_scope_matviews(catalog: CatalogResult, config: Config) -> list[ViewInfo]:
    """Matviews eligible for create/refresh under current config."""
    return matviews_in_scope(
        catalog.views,
        replicate=config.replicate_materialized_views,
        excluded_table_ids=excluded_table_ids(config),
    )


async def _replicate_views(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> list[ReplicatedObject]:
    created: list[ReplicatedObject] = []
    excluded = excluded_table_ids(config)
    for view in plain_views_in_dependency_order(catalog.views):
        if disposition_for_view(view, config) != "replicate":
            continue
        if excluded.intersection(view.depends_on):
            continue
        await _set_search_path(conn, view.schema_name)
        await _execute(conn, emit_create_view(view))
        created.append(
            ReplicatedObject(
                schema_name=view.schema_name,
                object_name=view.view_name,
                kind="view",
                is_elevated=view.is_elevated,
                depends_on=view.depends_on,
            )
        )
    return created


async def _replicate_matviews(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> list[ReplicatedObject]:
    in_scope = _in_scope_matviews(catalog, config)
    if not in_scope:
        return []
    # Drop dependents before parents so re-runs do not need CASCADE.
    for view in reversed(in_scope):
        qual = qualify(view.schema_name, view.view_name)
        await _execute(conn, f"DROP MATERIALIZED VIEW IF EXISTS {qual}")
    created: list[ReplicatedObject] = []
    for view in in_scope:
        await _set_search_path(conn, view.schema_name)
        await _execute(conn, emit_create_matview(view))
        created.append(
            ReplicatedObject(
                schema_name=view.schema_name,
                object_name=view.view_name,
                kind="materialized_view",
                is_elevated=False,
                depends_on=view.depends_on,
                definition_only=True,
            )
        )
    return created


async def refresh_materialized_views(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> tuple[tuple[str, str], ...]:
    """Refresh in-scope matview shells after masked base tables are loaded.

    Only runs in ``schema_mode: replicate`` when both matview flags are enabled.

    Returns:
        ``(schema_name, view_name)`` pairs refreshed, in dependency order.
    """
    if (
        config.schema_mode != "replicate"
        or not config.refresh_materialized_views
        or not config.replicate_materialized_views
    ):
        return ()
    refreshed: list[tuple[str, str]] = []
    for view in _in_scope_matviews(catalog, config):
        qual = qualify(view.schema_name, view.view_name)
        # SECURITY: schema/view names are quote_pg_identifier-escaped via qualify.
        await _execute(conn, f"REFRESH MATERIALIZED VIEW {qual}")
        refreshed.append((view.schema_name, view.view_name))
    return tuple(refreshed)


async def _set_search_path(conn: asyncpg.Connection, schema_name: str) -> None:
    schema = quote_pg_identifier(schema_name)
    # SECURITY: schema is quote_pg_identifier-escaped.
    await conn.execute(f"SET search_path TO {schema}, pg_catalog")  # noqa: S608


def emit_create_view(view: ViewInfo) -> str:
    """Emit ``CREATE OR REPLACE VIEW`` including invoker option when needed."""
    if view.definition is None:
        msg = f"view {view.identifier} has no definition for replication"
        raise PreflightError(
            "Replicating views to the target database",
            cause=msg,
            remediation="Re-introspect the source and retry.",
        )
    qual = qualify(view.schema_name, view.view_name)
    options = ""
    if not view.is_elevated:
        options = " WITH (security_invoker = true)"
    # SECURITY: schema/view names are quote_pg_identifier-escaped via qualify.
    return f"CREATE OR REPLACE VIEW {qual}{options} AS\n{view.definition}"


def emit_create_matview(view: ViewInfo) -> str:
    """Emit ``CREATE MATERIALIZED VIEW … WITH NO DATA`` from source definition."""
    if view.definition is None:
        msg = f"materialized view {view.identifier} has no definition for replication"
        raise PreflightError(
            "Replicating materialized views to the target database",
            cause=msg,
            remediation="Re-introspect the source and retry.",
        )
    qual = qualify(view.schema_name, view.view_name)
    definition = view.definition.strip().rstrip(";")
    # SECURITY: schema/view names are quote_pg_identifier-escaped via qualify.
    return f"CREATE MATERIALIZED VIEW {qual} AS\n{definition}\nWITH NO DATA"


async def _execute(conn: asyncpg.Connection, sql: str) -> None:
    try:
        await conn.execute(sql)
    except asyncpg.PostgresError as exc:
        raise PreflightError(
            "Replicating schema to the target database",
            cause=f"DDL execution failed on the target ({type(exc).__name__}: {exc}).",
            remediation="Verify target permissions, required extensions, and retry.",
        ) from exc

"""Helpers for emitting skipped-object audit events from catalog introspection."""

from __future__ import annotations

from collections.abc import Iterator

from privaci.catalog.models import CatalogResult, SkippedObjectInfo, ViewInfo
from privaci.catalog.views_meta import matviews_in_dependency_order, matviews_in_scope
from privaci.config.models import Config
from privaci.schema.elevated import disposition_for_function, disposition_for_view


def iter_skipped_object_audits(
    catalog: CatalogResult,
    config: Config | None = None,
) -> Iterator[tuple[str | None, str | None, dict[str, str]]]:
    """Yield ``(schema_name, table_name, payload)`` for intentionally skipped objects.

    When ``config`` is omitted, all views are treated as skipped (legacy unit
    helpers). With config, plain views/functions follow replication flags and
    elevated dispositions; materialized views are skipped unless
    ``replicate_materialized_views`` is enabled.
    """
    if config is None:
        for view in catalog.views:
            yield view.schema_name, view.view_name, {"kind": view.kind}
    else:
        yield from _skipped_views(catalog, config)
        yield from _skipped_functions(catalog, config)
    for obj in catalog.skipped_objects:
        yield _audit_target(obj), _audit_table_name(obj), _audit_payload(obj)


def _excluded_table_ids(config: Config) -> frozenset[str]:
    return frozenset(
        table_id
        for table_id, table_cfg in config.tables.items()
        if table_cfg.strategy == "exclude"
    )


def _skipped_views(
    catalog: CatalogResult,
    config: Config,
) -> Iterator[tuple[str | None, str | None, dict[str, str]]]:
    excluded = _excluded_table_ids(config)
    yield from _skipped_matviews(catalog, config, excluded)
    for view in catalog.views:
        if view.kind == "materialized_view":
            continue
        disposition = disposition_for_view(view, config)
        if disposition == "replicate":
            if excluded.intersection(view.depends_on):
                yield (
                    view.schema_name,
                    view.view_name,
                    {"kind": view.kind, "reason": "dependency_excluded"},
                )
            continue
        payload: dict[str, str] = {"kind": view.kind}
        if disposition == "skip" and view.is_elevated:
            payload["reason"] = "elevated_object_skipped"
        yield view.schema_name, view.view_name, payload


def _skipped_matviews(
    catalog: CatalogResult,
    config: Config,
    excluded: frozenset[str],
) -> Iterator[tuple[str | None, str | None, dict[str, str]]]:
    if not config.replicate_materialized_views:
        for view in matviews_in_dependency_order(catalog.views):
            yield view.schema_name, view.view_name, {"kind": view.kind}
        return
    in_scope = {
        view.identifier
        for view in matviews_in_scope(
            catalog.views,
            replicate=True,
            excluded_table_ids=excluded,
        )
    }
    for view in matviews_in_dependency_order(catalog.views):
        if view.identifier in in_scope:
            continue
        yield (
            view.schema_name,
            view.view_name,
            {"kind": view.kind, "reason": "dependency_excluded"},
        )


def _skipped_functions(
    catalog: CatalogResult,
    config: Config,
) -> Iterator[tuple[str | None, str | None, dict[str, str]]]:
    for function in catalog.functions:
        disposition = disposition_for_function(function, config)
        if disposition == "replicate":
            continue
        payload: dict[str, str] = {"kind": "function"}
        if disposition == "skip" and function.is_elevated:
            payload["reason"] = "elevated_object_skipped"
        name = function.function_name
        if function.identity_args.strip():
            name = f"{function.function_name}({function.identity_args})"
        yield function.schema_name, name, payload


def _audit_target(obj: SkippedObjectInfo | ViewInfo) -> str | None:
    if isinstance(obj, ViewInfo):
        return obj.schema_name
    if obj.schema_name:
        return obj.schema_name
    return None


def _audit_table_name(obj: SkippedObjectInfo | ViewInfo) -> str | None:
    if isinstance(obj, ViewInfo):
        return obj.view_name
    if obj.parent_table is not None:
        return obj.parent_table
    return obj.object_name


def _audit_payload(obj: SkippedObjectInfo) -> dict[str, str]:
    payload: dict[str, str] = {"kind": obj.kind}
    if obj.parent_table is not None:
        payload["object_name"] = obj.object_name
    if obj.kind == "trigger":
        payload["reason"] = "unsafe_during_load"
    elif obj.kind == "rule":
        payload["reason"] = "customer_owned_semantics"
    elif obj.kind == "publication":
        payload["reason"] = "low_value_footgun"
    return payload

"""Helpers for emitting skipped-object audit events from catalog introspection."""

from __future__ import annotations

from collections.abc import Iterator

from privaci.catalog.models import CatalogResult, SkippedObjectInfo, ViewInfo


def iter_skipped_object_audits(
    catalog: CatalogResult,
) -> Iterator[tuple[str | None, str | None, dict[str, str]]]:
    """Yield ``(schema_name, table_name, payload)`` tuples for skipped objects."""
    for view in catalog.views:
        yield view.schema_name, view.view_name, {"kind": view.kind}
    for obj in catalog.skipped_objects:
        yield _audit_target(obj), _audit_table_name(obj), _audit_payload(obj)


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
    return payload

"""Canonical JSON snapshots for catalog introspection results.

Pure serialize path only — persist/load/validate against ``_privaci.runs``
lives in :mod:`privaci.state.schema_snapshot`.
"""

from __future__ import annotations

import json
from typing import Any

from privaci.catalog.models import CatalogResult, TableInfo


def table_to_dict(table: TableInfo) -> dict[str, Any]:
    """Serialize one :class:`TableInfo` to a JSON-compatible dict."""
    return {
        "check_constraints": _check_constraints_dict(table),
        "columns": _columns_dict(table),
        "estimated_rows": table.estimated_rows,
        "foreign_keys": _foreign_keys_dict(table),
        "indexes": _indexes_dict(table),
        "is_partitioned": table.is_partitioned,
        "parent_partition": table.parent_partition,
        "partition_bound": table.partition_bound,
        "partition_children": list(table.partition_children),
        "partition_key_def": table.partition_key_def,
        "partition_strategy": table.partition_strategy,
        "primary_key": list(table.primary_key),
        "schema_name": table.schema_name,
        "self_cycle": table.self_cycle,
        "table_name": table.table_name,
        "unique_constraints": [list(group) for group in table.unique_constraints],
    }


def _columns_dict(table: TableInfo) -> list[dict[str, Any]]:
    return [
        {
            "data_type": column.data_type,
            "default_expression": column.default_expression,
            "identity_generation": column.identity_generation,
            "is_identity": column.is_identity,
            "name": column.name,
            "sequence_name": column.sequence_name,
            "uses_serial": column.uses_serial,
            "not_null": column.not_null,
        }
        for column in table.columns
    ]


def _foreign_keys_dict(table: TableInfo) -> list[dict[str, Any]]:
    return [
        {
            "deferrable": fk.deferrable,
            "initially_deferred": fk.initially_deferred,
            "name": fk.name,
            "on_delete": fk.on_delete,
            "on_update": fk.on_update,
            "referenced_columns": list(fk.referenced_columns),
            "referenced_schema": fk.referenced_schema,
            "referenced_table": fk.referenced_table,
            "source_columns": list(fk.source_columns),
        }
        for fk in table.foreign_keys
    ]


def _indexes_dict(table: TableInfo) -> list[dict[str, Any]]:
    return [
        {
            "columns": list(index.columns),
            "definition": index.definition,
            "is_unique": index.is_unique,
            "name": index.name,
        }
        for index in table.indexes
    ]


def _check_constraints_dict(table: TableInfo) -> list[dict[str, Any]]:
    return [
        {"definition": check.definition, "name": check.name}
        for check in table.check_constraints
    ]


def catalog_to_snapshot_dict(catalog: CatalogResult) -> dict[str, Any]:
    """Return a JSON-serializable snapshot dict with stable ordering."""
    ordered_tables = {
        table_id: table_to_dict(info)
        for table_id, info in sorted(catalog.tables.items())
    }
    return {
        "tables": ordered_tables,
        "views": _views_snapshot(catalog),
        "functions": _functions_snapshot(catalog),
        "triggers": _triggers_snapshot(catalog),
        "skipped_objects": _skipped_objects_snapshot(catalog),
        "load_plan": _load_plan_snapshot(catalog),
        "warnings": _warnings_snapshot(catalog),
    }


def _views_snapshot(catalog: CatalogResult) -> list[dict[str, Any]]:
    return [
        {
            "definition": view.definition,
            "depends_on": list(view.depends_on),
            "is_elevated": view.is_elevated,
            "kind": view.kind,
            "schema_name": view.schema_name,
            "view_name": view.view_name,
        }
        for view in sorted(catalog.views, key=lambda item: item.identifier)
    ]


def _functions_snapshot(catalog: CatalogResult) -> list[dict[str, Any]]:
    return [
        {
            "create_sql": function.create_sql,
            "depends_on_functions": list(function.depends_on_functions),
            "depends_on_tables": list(function.depends_on_tables),
            "function_name": function.function_name,
            "identity_args": function.identity_args,
            "is_elevated": function.is_elevated,
            "language": function.language,
            "schema_name": function.schema_name,
        }
        for function in sorted(catalog.functions, key=lambda item: item.identifier)
    ]


def _triggers_snapshot(catalog: CatalogResult) -> list[dict[str, Any]]:
    return [
        {
            "create_sql": trigger.create_sql,
            "function_identity": trigger.function_identity,
            "schema_name": trigger.schema_name,
            "table_name": trigger.table_name,
            "trigger_name": trigger.trigger_name,
        }
        for trigger in sorted(catalog.triggers, key=lambda item: item.identifier)
    ]


def _skipped_objects_snapshot(catalog: CatalogResult) -> list[dict[str, Any]]:
    return [
        {
            "kind": item.kind,
            "object_name": item.object_name,
            "parent_table": item.parent_table,
            "schema_name": item.schema_name,
        }
        for item in sorted(
            catalog.skipped_objects,
            key=lambda item: (item.schema_name, item.kind, item.object_name),
        )
    ]


def _load_plan_snapshot(catalog: CatalogResult) -> dict[str, Any]:
    return {
        "layers": [list(layer.table_ids) for layer in catalog.load_plan.layers],
        "deferred_edges": [
            {
                "foreign_key_name": edge.foreign_key_name,
                "referenced_table": edge.referenced_table,
                "referencing_table": edge.referencing_table,
            }
            for edge in catalog.load_plan.deferred_edges
        ],
    }


def _warnings_snapshot(catalog: CatalogResult) -> list[dict[str, Any]]:
    return [
        {
            "code": warning.code,
            "message": warning.message,
            "table_id": warning.table_id,
        }
        for warning in sorted(
            catalog.warnings,
            key=lambda item: (item.code, item.table_id, item.message),
        )
    ]


def canonical_snapshot_json(catalog: CatalogResult) -> str:
    """Return deterministic canonical JSON for a catalog snapshot.

    Two introspection runs against an unchanged source MUST produce
    byte-identical output.
    """
    payload = catalog.to_snapshot_dict()
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def normalize_snapshot_for_resume_compare(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Drop volatile planner stats before comparing resume snapshots.

    ``estimated_rows`` comes from ``pg_class.reltuples`` and may change between
    two introspection passes against an unchanged schema (ANALYZE, autovacuum,
    or fresh INSERT statistics). Resume must not fail on that alone.
    """
    normalized: dict[str, Any] = json.loads(json.dumps(snapshot))
    tables = normalized.get("tables")
    if isinstance(tables, dict):
        for table in tables.values():
            if isinstance(table, dict):
                table.pop("estimated_rows", None)
    return normalized


def find_new_partition_children(
    previous: dict[str, Any] | None,
    catalog: CatalogResult,
) -> tuple[TableInfo, ...]:
    """Return partition children present in ``catalog`` but not ``previous``."""
    if previous is None:
        return ()
    known = set(previous.get("tables", {}))
    new_children = [
        table
        for table in catalog.tables.values()
        if table.parent_partition is not None and table.identifier not in known
    ]
    return tuple(sorted(new_children, key=lambda table: table.identifier))

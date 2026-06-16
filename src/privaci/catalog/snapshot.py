"""Canonical JSON snapshots for catalog introspection results."""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg

from privaci.catalog.models import CatalogResult, TableInfo
from privaci.errors import PreflightError, StateError
from privaci.state.models import RunStatus


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
        "skipped_objects": _skipped_objects_snapshot(catalog),
        "load_plan": _load_plan_snapshot(catalog),
        "warnings": _warnings_snapshot(catalog),
    }


def _views_snapshot(catalog: CatalogResult) -> list[dict[str, Any]]:
    return [
        {
            "kind": view.kind,
            "schema_name": view.schema_name,
            "view_name": view.view_name,
        }
        for view in sorted(catalog.views, key=lambda item: item.identifier)
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
        for warning in catalog.warnings
    ]


def canonical_snapshot_json(catalog: CatalogResult) -> str:
    """Return deterministic canonical JSON for a catalog snapshot.

    Two introspection runs against an unchanged source MUST produce
    byte-identical output.
    """
    payload = catalog.to_snapshot_dict()
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


_LOAD_LATEST_SNAPSHOT_SQL = """
SELECT source_schema_snapshot
FROM _privaci.runs
WHERE source_db_hash = $1
  AND status = $2
  AND source_schema_snapshot IS NOT NULL
  AND ($3::uuid IS NULL OR run_id != $3)
ORDER BY started_at DESC
LIMIT 1
"""

_LOAD_RUN_SNAPSHOT_SQL = """
SELECT source_schema_snapshot
FROM _privaci.runs
WHERE run_id = $1
"""


def _snapshot_payload(raw: object) -> dict[str, Any] | None:
    """Normalize a jsonb column value to a dict."""
    if raw is None:
        return None
    if isinstance(raw, str):
        parsed: dict[str, Any] = json.loads(raw)
        return parsed
    if isinstance(raw, dict):
        return dict(raw)
    msg = f"unexpected snapshot payload type: {type(raw).__name__}"
    raise StateError(
        "Loading source schema snapshot",
        cause=msg,
        remediation="Re-run with a fresh `privaci run`.",
    )


async def validate_resume_schema_snapshot(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
    catalog: CatalogResult,
) -> None:
    """Fail resume when the live source catalog drifted from the run snapshot.

    Raises:
        PreflightError: When a stored snapshot exists and differs from ``catalog``.
    """
    row = await conn.fetchrow(_LOAD_RUN_SNAPSHOT_SQL, run_id)
    if row is None:
        return
    stored = _snapshot_payload(row["source_schema_snapshot"])
    if stored is None:
        return
    current = json.loads(canonical_snapshot_json(catalog))
    if stored == current:
        return
    raise PreflightError(
        "Validating resume prerequisites",
        cause="The source database schema changed since the incomplete run.",
        remediation=(
            "Restore the original source schema, truncate affected target tables, "
            "and start a fresh run with `privaci run --force-restart`."
        ),
    )


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


async def load_latest_schema_snapshot(
    conn: asyncpg.Connection,
    *,
    source_db_hash: str,
    exclude_run_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    """Load the newest succeeded run snapshot for one source database."""
    row = await conn.fetchrow(
        _LOAD_LATEST_SNAPSHOT_SQL,
        source_db_hash,
        RunStatus.SUCCEEDED.value,
        exclude_run_id,
    )
    if row is None:
        return None
    return _snapshot_payload(row["source_schema_snapshot"])


async def persist_source_schema_snapshot(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
    catalog: CatalogResult,
) -> None:
    """Write the canonical snapshot JSON to ``_privaci.runs``.

    Raises:
        StateError: When the snapshot cannot be written.
    """
    snapshot = canonical_snapshot_json(catalog)
    try:
        await conn.execute(
            """
            UPDATE _privaci.runs
            SET source_schema_snapshot = $2::jsonb
            WHERE run_id = $1
            """,
            run_id,
            snapshot,
        )
    except asyncpg.PostgresError as exc:
        raise StateError(
            "Persisting source schema snapshot",
            cause="Could not write source_schema_snapshot to _privaci.runs.",
            remediation=(
                "Ensure the _privaci schema exists and the run row was created."
            ),
        ) from exc

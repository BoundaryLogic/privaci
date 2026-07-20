"""Audit helpers for schema object create / definition-only events."""

from __future__ import annotations

from typing import Any

import asyncpg

from privaci.observability import Event, emit
from privaci.schema.objects import ReplicatedObject
from privaci.state import AuditWriter
from privaci.state.models import EventType

_CREATED_EXISTS_SQL = """
SELECT EXISTS (
    SELECT 1
    FROM _privaci.audit_log
    WHERE run_id = $1
      AND event_type = $2
      AND schema_name IS NOT DISTINCT FROM $3
      AND table_name IS NOT DISTINCT FROM $4
      AND payload->>'kind' = $5
      AND (
          ($6::text IS NULL AND payload->>'object_name' IS NULL)
          OR payload->>'object_name' = $6
      )
)
"""


async def emit_definition_only_audit(
    target: asyncpg.Connection,
    audit: AuditWriter,
    obj: ReplicatedObject,
) -> None:
    """Record a definition-only object (e.g. matview shell) with ddl_phase."""
    if await _already_audited(target, audit, EventType.DEFINITION_ONLY_OBJECT, obj):
        return
    payload: dict[str, Any] = {
        "kind": obj.kind,
        "contents_copied": False,
        "refreshed": False,
        "depends_on": list(obj.depends_on),
        "ddl_phase": obj.ddl_phase,
    }
    await audit.write(
        target,
        EventType.DEFINITION_ONLY_OBJECT,
        schema_name=obj.schema_name,
        table_name=obj.object_name,
        payload=payload,
    )
    emit(
        Event.DEFINITION_ONLY_OBJECT,
        schema_name=obj.schema_name,
        object_name=obj.object_name,
        kind=obj.kind,
        contents_copied=False,
        refreshed=False,
        ddl_phase=obj.ddl_phase,
    )


async def emit_created_object_audit(
    target: asyncpg.Connection,
    audit: AuditWriter,
    obj: ReplicatedObject,
) -> None:
    """Record a created catalog object with ddl_phase (idempotent on resume)."""
    if await _already_audited(target, audit, EventType.CREATED_OBJECT, obj):
        return
    created_payload: dict[str, Any] = {
        "kind": obj.kind,
        "depends_on": list(obj.depends_on),
        "ddl_phase": obj.ddl_phase,
    }
    if obj.is_elevated:
        created_payload["elevated"] = True
    if obj.payload_object_name is not None:
        created_payload["object_name"] = obj.payload_object_name
    await audit.write(
        target,
        EventType.CREATED_OBJECT,
        schema_name=obj.schema_name,
        table_name=obj.object_name,
        payload=created_payload,
    )
    emit(
        Event.CREATED_OBJECT,
        schema_name=obj.schema_name,
        object_name=obj.payload_object_name or obj.object_name,
        kind=obj.kind,
        elevated=obj.is_elevated,
        ddl_phase=obj.ddl_phase,
    )


async def _already_audited(
    target: asyncpg.Connection,
    audit: AuditWriter,
    event_type: EventType,
    obj: ReplicatedObject,
) -> bool:
    if not audit.enabled:
        return False
    found = await target.fetchval(
        _CREATED_EXISTS_SQL,
        audit.run_id,
        event_type.value,
        obj.schema_name,
        obj.object_name,
        obj.kind,
        obj.payload_object_name,
    )
    return bool(found)

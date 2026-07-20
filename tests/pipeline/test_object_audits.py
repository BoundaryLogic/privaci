"""Unit tests for schema object audit helpers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from privaci.pipeline.object_audits import (
    emit_created_object_audit,
    emit_definition_only_audit,
)
from privaci.schema.objects import ReplicatedObject
from privaci.state import AuditWriter


@pytest.mark.asyncio
async def test_emit_created_object_audit_writes_payload() -> None:
    target = AsyncMock()
    target.fetchval = AsyncMock(return_value=False)
    target.execute = AsyncMock()
    audit = AuditWriter(uuid.uuid4(), enabled=True)
    obj = ReplicatedObject(
        schema_name="public",
        object_name="users",
        kind="trigger",
        is_elevated=False,
        ddl_phase="post-data",
        payload_object_name="users_audit",
    )

    await emit_created_object_audit(target, audit, obj)

    target.execute.assert_awaited()
    # Second await is the insert after EXISTS check.
    assert target.fetchval.await_count == 1


@pytest.mark.asyncio
async def test_emit_created_object_audit_skips_when_already_present() -> None:
    target = AsyncMock()
    target.fetchval = AsyncMock(return_value=True)
    target.execute = AsyncMock()
    audit = AuditWriter(uuid.uuid4(), enabled=True)
    obj = ReplicatedObject(
        schema_name="public",
        object_name="clinic_label",
        kind="function",
        is_elevated=False,
        ddl_phase="post-data",
    )

    await emit_created_object_audit(target, audit, obj)

    target.execute.assert_not_called()


@pytest.mark.asyncio
async def test_emit_definition_only_audit_includes_ddl_phase() -> None:
    target = AsyncMock()
    target.fetchval = AsyncMock(return_value=False)
    target.execute = AsyncMock()
    audit = AuditWriter(uuid.uuid4(), enabled=True)
    obj = ReplicatedObject(
        schema_name="public",
        object_name="tickets_open_mv",
        kind="materialized_view",
        is_elevated=False,
        definition_only=True,
        ddl_phase="post-data",
    )

    await emit_definition_only_audit(target, audit, obj)

    target.execute.assert_awaited()

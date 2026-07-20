"""Tests for skipped-object catalog introspection."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.graph import build_load_plan
from privaci.catalog.models import (
    CatalogResult,
    SkippedObjectInfo,
    TriggerInfo,
    ViewInfo,
)
from privaci.catalog.skipped import fetch_skipped_objects
from privaci.catalog.triggers import fetch_triggers
from privaci.config.models import Config
from privaci.schema.skipped_audits import iter_skipped_object_audits


@pytest.mark.asyncio
async def test_fetch_skipped_objects_returns_rules_and_publications() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "schema_name": "public",
                    "table_name": "users",
                    "rule_name": "users_upsert",
                }
            ],
            [{"publication_name": "events_pub"}],
        ]
    )

    # Act
    objects = await fetch_skipped_objects(conn)

    # Assert
    assert objects == (
        SkippedObjectInfo(
            schema_name="",
            object_name="events_pub",
            kind="publication",
        ),
        SkippedObjectInfo(
            schema_name="public",
            object_name="users_upsert",
            kind="rule",
            parent_table="users",
        ),
    )


@pytest.mark.asyncio
async def test_fetch_triggers_returns_create_sql() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "schema_name": "public",
                "table_name": "users",
                "trigger_name": "users_audit",
                "create_sql": (
                    "CREATE TRIGGER users_audit AFTER INSERT ON public.users "
                    "FOR EACH ROW EXECUTE FUNCTION public.users_audit()"
                ),
                "function_identity": "public.users_audit",
            }
        ]
    )

    # Act
    triggers = await fetch_triggers(conn)

    # Assert
    assert len(triggers) == 1
    assert triggers[0].trigger_name == "users_audit"
    assert "CREATE TRIGGER" in triggers[0].create_sql


def test_iter_skipped_object_audits_skips_triggers_when_flag_disabled() -> None:
    # Arrange
    catalog = CatalogResult(
        tables={},
        load_plan=build_load_plan({}),
        views=(ViewInfo(schema_name="public", view_name="active_users", kind="view"),),
        triggers=(
            TriggerInfo(
                schema_name="public",
                table_name="users",
                trigger_name="users_audit",
                create_sql="CREATE TRIGGER users_audit ...",
            ),
        ),
        skipped_objects=(
            SkippedObjectInfo(
                schema_name="public",
                object_name="users_upsert",
                kind="rule",
                parent_table="users",
            ),
        ),
    )
    config = Config(version="1.0", replicate_triggers=False, replicate_views=False)

    # Act
    entries = list(iter_skipped_object_audits(catalog, config))

    # Assert
    kinds = {payload["kind"] for _, _, payload in entries}
    assert "view" in kinds
    assert "trigger" in kinds
    assert "rule" in kinds
    trigger_entry = next(p for _, _, p in entries if p["kind"] == "trigger")
    assert trigger_entry["reason"] == "flag_disabled"

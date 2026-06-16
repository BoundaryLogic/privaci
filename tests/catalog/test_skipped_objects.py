"""Tests for skipped-object catalog introspection."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.audit_skipped import iter_skipped_object_audits
from privaci.catalog.graph import build_load_plan
from privaci.catalog.models import CatalogResult, SkippedObjectInfo, ViewInfo
from privaci.catalog.skipped import fetch_skipped_objects


@pytest.mark.asyncio
async def test_fetch_skipped_objects_returns_triggers_rules_publications() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [
                {
                    "schema_name": "public",
                    "table_name": "users",
                    "trigger_name": "users_audit",
                }
            ],
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
        SkippedObjectInfo(
            schema_name="public",
            object_name="users_audit",
            kind="trigger",
            parent_table="users",
        ),
    )


def test_iter_skipped_object_audits_includes_views_and_triggers() -> None:
    # Arrange
    catalog = CatalogResult(
        tables={},
        load_plan=build_load_plan({}),
        views=(ViewInfo(schema_name="public", view_name="active_users", kind="view"),),
        skipped_objects=(
            SkippedObjectInfo(
                schema_name="public",
                object_name="users_audit",
                kind="trigger",
                parent_table="users",
            ),
        ),
    )

    # Act
    entries = list(iter_skipped_object_audits(catalog))

    # Assert
    assert entries == [
        ("public", "active_users", {"kind": "view"}),
        (
            "public",
            "users",
            {"kind": "trigger", "object_name": "users_audit"},
        ),
    ]

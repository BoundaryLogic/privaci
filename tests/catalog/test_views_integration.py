"""Integration tests for view catalog introspection."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from privaci.catalog import introspect_catalog

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_DEMO_CORP_SQL_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "demo-corp"
)


async def test_introspect_catalog_lists_demo_corp_views(
    source_dsn: str, postgres_available: None
) -> None:
    # Arrange
    from tests.integration.conftest import _apply_sql_dir

    await _apply_sql_dir(source_dsn, _DEMO_CORP_SQL_DIR)
    conn = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()

    # Assert
    by_id = {view.identifier: view.kind for view in catalog.views}
    assert by_id["public.active_clinics_v"] == "view"
    assert by_id["public.monthly_revenue_v"] == "view"
    assert by_id["public.tickets_open_mv"] == "materialized_view"

    users = catalog.tables["public.users"]
    id_column = users.column_by_name("id")
    assert id_column is not None
    assert id_column.is_identity is True
    assert id_column.identity_generation == "ALWAYS"
    assert id_column.sequence_name is not None
    assert id_column.uses_serial is False

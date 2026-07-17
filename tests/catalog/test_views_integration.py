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
    by_id = {view.identifier: view for view in catalog.views}
    assert by_id["public.active_clinics_v"].kind == "view"
    assert by_id["public.active_clinics_v"].is_elevated is False
    assert by_id["public.monthly_revenue_v"].kind == "view"
    assert by_id["public.elevated_orgs_v"].is_elevated is True
    assert by_id["public.tickets_open_mv"].kind == "materialized_view"

    fn_ids = {fn.identifier for fn in catalog.functions}
    assert "public.clinic_label(org_id bigint)" in fn_ids
    assert "public.elevated_org_name(org_id bigint)" in fn_ids
    assert any(
        fn.is_elevated
        for fn in catalog.functions
        if fn.identifier == "public.elevated_org_name(org_id bigint)"
    )

    skipped_kinds = {obj.kind for obj in catalog.skipped_objects}
    assert "trigger" in skipped_kinds
    assert "rule" in skipped_kinds
    assert "publication" in skipped_kinds

    users = catalog.tables["public.users"]
    id_column = users.column_by_name("id")
    assert id_column is not None
    assert id_column.is_identity is True
    assert id_column.identity_generation == "ALWAYS"
    assert id_column.sequence_name is not None
    assert id_column.uses_serial is False

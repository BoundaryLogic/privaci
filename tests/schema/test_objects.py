"""Unit tests for view CREATE DDL emission."""

from __future__ import annotations

from privaci.catalog.models import ViewInfo
from privaci.schema.objects import emit_create_matview, emit_create_view


def test_emit_create_view_includes_security_invoker_for_non_elevated() -> None:
    view = ViewInfo(
        schema_name="public",
        view_name="active_v",
        kind="view",
        definition=" SELECT 1 AS id",
        is_elevated=False,
    )

    sql = emit_create_view(view)

    assert "security_invoker = true" in sql
    assert "CREATE OR REPLACE VIEW" in sql
    assert "SELECT 1 AS id" in sql


def test_emit_create_view_omits_invoker_option_when_elevated() -> None:
    view = ViewInfo(
        schema_name="public",
        view_name="elevated_v",
        kind="view",
        definition=" SELECT 1 AS id",
        is_elevated=True,
    )

    sql = emit_create_view(view)

    assert "security_invoker" not in sql


def test_emit_create_matview_uses_with_no_data() -> None:
    view = ViewInfo(
        schema_name="public",
        view_name="tickets_open_mv",
        kind="materialized_view",
        definition=" SELECT id FROM public.tickets WHERE status <> 'closed';",
    )

    sql = emit_create_matview(view)

    assert sql.startswith("CREATE MATERIALIZED VIEW")
    assert "WITH NO DATA" in sql
    assert "status <> 'closed'" in sql
    assert not sql.rstrip().endswith(";")

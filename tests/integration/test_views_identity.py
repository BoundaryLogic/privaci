"""Integration tests for view/function replication and identity sequence sync."""

from __future__ import annotations

import asyncpg
import pytest

from privaci.config import load_config
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import audit_count
from tests.integration.conftest import DEMO_CORP_CONFIG_PATH

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_CREATED_VIEWS = (
    ("public", "active_clinics_v"),
    ("public", "monthly_revenue_v"),
)
_SKIPPED_ELEVATED = ("public", "elevated_orgs_v")
_SKIPPED_MATVIEW = ("public", "tickets_open_mv")
_SKIPPED_TRIGGER = ("public", "users", "users_audit_noop")
_SKIPPED_PUBLICATION = "privaci_demo_fixture_pub"


async def test_demo_corp_pipeline_replicates_views_and_syncs_identity_sequences(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    """Shared Demo Corp fixtures cover views, functions, elevated, and Tier-3 skips."""
    config = load_config(DEMO_CORP_CONFIG_PATH)

    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=True,
    )

    target = await asyncpg.connect(target_dsn)
    source = await asyncpg.connect(source_dsn)
    try:
        for schema_name, view_name in _CREATED_VIEWS:
            exists = await target.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.views
                    WHERE table_schema = $1 AND table_name = $2
                )
                """,
                schema_name,
                view_name,
            )
            assert exists is True, f"view {schema_name}.{view_name} should be created"

        for schema_name, view_name in (_SKIPPED_ELEVATED, _SKIPPED_MATVIEW):
            exists = await target.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.views
                    WHERE table_schema = $1 AND table_name = $2
                )
                OR EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_matviews
                    WHERE schemaname = $1 AND matviewname = $2
                )
                """,
                schema_name,
                view_name,
            )
            assert exists is False, f"{schema_name}.{view_name} should be skipped"

        for fn_name in ("clinic_label", "users_audit_noop"):
            fn_exists = await target.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_proc p
                    JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public' AND p.proname = $1
                )
                """,
                fn_name,
            )
            assert fn_exists is True, f"function {fn_name} should be replicated"

        elevated_fn = await target.fetchval("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = 'elevated_org_name'
            )
            """)
        assert elevated_fn is False

        created = await audit_count(target, event_type="created_object")
        assert created >= 4  # 2 views + clinic_label + users_audit_noop

        skipped_elevated = await target.fetchval("""
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = 'skipped_object'
              AND table_name = 'elevated_orgs_v'
              AND payload->>'reason' = 'elevated_object_skipped'
            """)
        assert int(skipped_elevated or 0) == 1

        skipped_elevated_fn = await target.fetchval("""
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = 'skipped_object'
              AND table_name LIKE 'elevated_org_name%'
              AND payload->>'reason' = 'elevated_object_skipped'
            """)
        assert int(skipped_elevated_fn or 0) == 1

        skipped_mv = await target.fetchval("""
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = 'skipped_object'
              AND table_name = 'tickets_open_mv'
            """)
        assert int(skipped_mv or 0) == 1

        schema_name, table_name, trigger_name = _SKIPPED_TRIGGER
        skipped_trigger = await target.fetchval(
            """
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = 'skipped_object'
              AND schema_name = $1
              AND table_name = $2
              AND payload->>'object_name' = $3
              AND payload->>'reason' = 'unsafe_during_load'
            """,
            schema_name,
            table_name,
            trigger_name,
        )
        assert int(skipped_trigger or 0) == 1

        skipped_rule = await target.fetchval("""
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = 'skipped_object'
              AND payload->>'object_name' = 'tickets_insert_also_noop'
              AND payload->>'reason' = 'customer_owned_semantics'
            """)
        assert int(skipped_rule or 0) == 1

        skipped_pub = await target.fetchval(
            """
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = 'skipped_object'
              AND table_name = $1
              AND payload->>'reason' = 'low_value_footgun'
            """,
            _SKIPPED_PUBLICATION,
        )
        assert int(skipped_pub or 0) == 1

        source_max = await source.fetchval("SELECT max(id)::bigint FROM public.users")
        sequence_last = await target.fetchval(
            "SELECT last_value::bigint FROM public.users_id_seq"
        )
        assert sequence_last == source_max
    finally:
        await target.close()
        await source.close()


async def test_assume_existing_does_not_replicate_source_views(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    """assume_existing owns DDL — views/functions stay absent unless prebuilt."""
    base = load_config(DEMO_CORP_CONFIG_PATH)
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        base,
        TEST_SALT,
        audit_enabled=True,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        await target.execute("DROP VIEW IF EXISTS public.active_clinics_v")
        await target.execute("DROP FUNCTION IF EXISTS public.clinic_label(bigint)")
    finally:
        await target.close()

    assume = base.model_copy(
        update={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
        }
    )
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        assume,
        TEST_SALT,
        audit_enabled=True,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        view_exists = await target.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views
                WHERE table_schema = 'public' AND table_name = 'active_clinics_v'
            )
            """)
        fn_exists = await target.fetchval("""
            SELECT EXISTS (
                SELECT 1
                FROM pg_catalog.pg_proc p
                JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname = 'clinic_label'
            )
            """)
        assert view_exists is False
        assert fn_exists is False
    finally:
        await target.close()

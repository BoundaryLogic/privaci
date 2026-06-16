"""Integration tests for view skipping and identity sequence sync."""

from __future__ import annotations

import asyncpg
import pytest

from privaci.config import load_config
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import audit_count
from tests.integration.conftest import DEMO_CORP_CONFIG_PATH

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_EXPECTED_VIEWS = (
    ("public", "active_clinics_v"),
    ("public", "monthly_revenue_v"),
    ("public", "tickets_open_mv"),
)


async def test_demo_corp_pipeline_skips_views_and_syncs_identity_sequences(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    # Arrange
    config = load_config(DEMO_CORP_CONFIG_PATH)

    # Act
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=True,
    )

    # Assert
    target = await asyncpg.connect(target_dsn)
    source = await asyncpg.connect(source_dsn)
    try:
        for schema_name, view_name in _EXPECTED_VIEWS:
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
            assert exists is False, f"view {schema_name}.{view_name} should be skipped"

        skipped = await target.fetchval("""
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = 'skipped_object'
            """)
        assert skipped == len(_EXPECTED_VIEWS)

        source_max = await source.fetchval("SELECT max(id)::bigint FROM public.users")
        sequence_last = await target.fetchval(
            "SELECT last_value::bigint FROM public.users_id_seq"
        )
        assert sequence_last == source_max
        assert await audit_count(target, event_type="skipped_object") == len(
            _EXPECTED_VIEWS
        )
    finally:
        await target.close()
        await source.close()

"""Likelihood-ranked schema_mode matrix cells (P1–P2 public).

P0 baselines live in dedicated capabilities (demo-corp, assume_existing, views).
See ``scripts/capability_test/matrix.py`` and docs/test-fixtures.md.
"""

from __future__ import annotations

import asyncpg
import pytest
from pydantic import SecretStr

from privaci.config import load_config
from privaci.config.actions import HmacHashAction
from privaci.config.models import TableConfig
from privaci.errors import PreflightError
from privaci.pipeline import run_masking_pipeline
from privaci.state.models import EventType
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import (
    audit_count,
    count_partitioned_table_rows,
    count_rows,
)
from tests.integration.conftest import DEMO_CORP_CONFIG_PATH

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_PSEUDONYM_KEY = "pseudonym-key-with-32-byte-minimum-length!!"


def _demo_config(**updates: object):
    return load_config(DEMO_CORP_CONFIG_PATH).model_copy(update=updates)


async def test_elevated_unresolved_fail(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    # Leave elevated_org_name without a disposition (orgs_v still skipped).
    config = _demo_config(
        elevated_objects={"public.elevated_orgs_v": "skip"},
        auto_detect=False,
    )

    with pytest.raises(PreflightError, match="elevated|Elevated"):
        await run_masking_pipeline(
            source_dsn,
            target_dsn,
            config,
            TEST_SALT,
            audit_enabled=False,
        )


async def test_elevated_replicate_one(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    base = load_config(DEMO_CORP_CONFIG_PATH)
    elevated = dict(base.elevated_objects)
    elevated["public.elevated_orgs_v"] = "replicate"
    config = base.model_copy(
        update={"elevated_objects": elevated, "auto_detect": False}
    )

    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=True,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        exists = await target.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views
                WHERE table_schema = 'public' AND table_name = 'elevated_orgs_v'
            )
            """)
        assert exists is True
        created = await target.fetchval("""
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = 'created_object'
              AND table_name = 'elevated_orgs_v'
            """)
        assert int(created or 0) >= 1
    finally:
        await target.close()


async def test_replicate_views_functions_off(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    config = _demo_config(replicate_views=False, replicate_functions=False)

    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
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
        assert await count_rows(target, "public.users") > 0
    finally:
        await target.close()


async def test_assume_fail_empty(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    base = load_config(DEMO_CORP_CONFIG_PATH).model_copy(update={"auto_detect": False})
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        base,
        TEST_SALT,
        audit_enabled=False,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        await target.execute("""
            DO $$
            DECLARE r record;
            BEGIN
              FOR r IN
                SELECT quote_ident(schemaname) || '.' || quote_ident(tablename) AS q
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                  AND schemaname NOT LIKE 'pg\\_%'
                  AND schemaname <> '_privaci'
              LOOP
                EXECUTE 'TRUNCATE ' || r.q || ' CASCADE';
              END LOOP;
            END $$;
            """)
    finally:
        await target.close()

    assume = base.model_copy(
        update={
            "schema_mode": "assume_existing",
            "on_existing_data": "fail",
            "passthrough_copy": "auto",
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
        assert await count_rows(target, "public.users") > 0
        validated = await audit_count(
            target, event_type=EventType.SCHEMA_VALIDATED.value
        )
        assert validated >= 1
    finally:
        await target.close()


async def test_passthrough_batch(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    config = _demo_config(passthrough_copy="batch")

    summary = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )

    assert summary.rows_processed > 0
    target = await asyncpg.connect(target_dsn)
    try:
        assert await count_rows(target, "public.users") > 0
    finally:
        await target.close()


async def test_passthrough_require_binary_fail(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    base = load_config(DEMO_CORP_CONFIG_PATH)
    tables = dict(base.tables)
    # Composite-PK table with no IDENTITY — eligible for whole-table binary COPY.
    tables["public.invoice_line_items"] = TableConfig()
    first = base.model_copy(update={"tables": tables, "auto_detect": False})
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        first,
        TEST_SALT,
        audit_enabled=False,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        await target.execute(
            "ALTER TABLE public.invoice_line_items "
            "ADD COLUMN IF NOT EXISTS matrix_extra text"
        )
    finally:
        await target.close()

    assume = first.model_copy(
        update={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
            "passthrough_copy": "require_binary",
        }
    )
    with pytest.raises(PreflightError, match="require_binary|binary-COPY"):
        await run_masking_pipeline(
            source_dsn,
            target_dsn,
            assume,
            TEST_SALT,
            audit_enabled=False,
        )


async def test_partitions_x_assume(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    base = load_config(DEMO_CORP_CONFIG_PATH)
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        base,
        TEST_SALT,
        audit_enabled=False,
    )

    assume = base.model_copy(
        update={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
            "passthrough_copy": "auto",
        }
    )
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        assume,
        TEST_SALT,
        audit_enabled=False,
    )

    source = await asyncpg.connect(source_dsn)
    target = await asyncpg.connect(target_dsn)
    try:
        source_count = await count_partitioned_table_rows(
            source, "public.raw_events", child_prefix="raw_events_"
        )
        target_count = await count_partitioned_table_rows(
            target, "public.raw_events", child_prefix="raw_events_"
        )
        assert target_count == source_count
        assert target_count > 0
    finally:
        await source.close()
        await target.close()


async def test_streaming_x_assume(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    base = load_config(DEMO_CORP_CONFIG_PATH)
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        base,
        TEST_SALT,
        audit_enabled=False,
    )

    assume = base.model_copy(
        update={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
            "passthrough_copy": "batch",
        }
    )
    summary = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        assume,
        TEST_SALT,
        audit_enabled=True,
    )

    assert summary.rows_processed > 0
    target = await asyncpg.connect(target_dsn)
    try:
        assert await count_rows(target, "public.tickets") > 0
        validated = await audit_count(
            target, event_type=EventType.SCHEMA_VALIDATED.value
        )
        assert validated >= 1
    finally:
        await target.close()


async def test_keyed_x_replicate(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    base = load_config(DEMO_CORP_CONFIG_PATH)
    users = base.tables["public.users"]
    columns = dict(users.columns)
    columns["email"] = HmacHashAction(action="hmac_hash")
    tables = dict(base.tables)
    tables["public.users"] = TableConfig(
        strategy=users.strategy,
        columns=columns,
    )
    config = base.model_copy(
        update={
            "tables": tables,
            "pseudonym_key": SecretStr(_PSEUDONYM_KEY),
            "auto_detect": False,
        }
    )

    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
        pseudonym_key=_PSEUDONYM_KEY,
    )

    target = await asyncpg.connect(target_dsn)
    try:
        email = await target.fetchval(
            "SELECT email FROM public.users ORDER BY id LIMIT 1"
        )
        assert email is not None
        assert "@" not in str(email)  # hmac digest, not a fake email
        assert len(str(email)) >= 32
    finally:
        await target.close()

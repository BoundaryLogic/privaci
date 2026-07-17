"""Integration: assume_existing load into a prebuilt Demo Corp target."""

from __future__ import annotations

import asyncpg
import pytest

from privaci.config import load_config
from privaci.errors import PreflightError
from privaci.pipeline import run_masking_pipeline
from privaci.state.models import EventType
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import audit_count, count_rows
from tests.integration.conftest import DEMO_CORP_CONFIG_PATH

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_assume_existing_loads_into_prebuilt_target(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    """Replicate once, then reload with schema_mode assume_existing + truncate."""
    base = load_config(DEMO_CORP_CONFIG_PATH)
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        base,
        TEST_SALT,
        audit_enabled=True,
    )

    assume = base.model_copy(
        update={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
            "passthrough_copy": "auto",
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
        assert await count_rows(target, "public.users") > 0
        assert await audit_count(target) > 0
        validated = await target.fetchval(
            """
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = $1
            """,
            EventType.SCHEMA_VALIDATED.value,
        )
        assert int(validated or 0) >= 1
    finally:
        await target.close()


async def test_assume_existing_failure_is_audited(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    """A missing prebuilt schema leaves a durable refusal record."""
    base = load_config(DEMO_CORP_CONFIG_PATH)
    assume = base.model_copy(
        update={
            "schema_mode": "assume_existing",
            "on_existing_data": "truncate",
        }
    )

    with pytest.raises(PreflightError, match="missing table"):
        await run_masking_pipeline(
            source_dsn,
            target_dsn,
            assume,
            TEST_SALT,
            audit_enabled=True,
        )

    target = await asyncpg.connect(target_dsn)
    try:
        failed = await target.fetchval(
            """
            SELECT count(*)::int
            FROM _privaci.audit_log
            WHERE event_type = $1
            """,
            EventType.SCHEMA_VALIDATION_FAILED.value,
        )
        assert int(failed or 0) == 1
    finally:
        await target.close()

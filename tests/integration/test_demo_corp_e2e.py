"""End-to-end integration test: Demo Corp source through the masking pipeline."""

from __future__ import annotations

import asyncpg
import pytest

from privaci.config import load_config
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import (
    all_fks_valid,
    audit_count,
    count_partitioned_table_rows,
    count_rows,
    partition_count,
    table_exists,
)
from tests.integration.conftest import DEMO_CORP_CONFIG_PATH
from tests.integration.masking_checks import (
    assert_demo_corp_action_shapes,
    assert_demo_corp_leak_probes,
    assert_demo_corp_ner_columns_changed,
    assert_demo_corp_passthrough_unchanged,
    run_demo_corp_verification,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_RAW_EVENT_PARTITIONS = 24
_PATIENT_VISIT_PARTITIONS = 4


async def test_demo_corp_masking_pipeline(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    """Full demo-corp run with leak probes, action shapes, and value-free verify."""
    config = load_config(DEMO_CORP_CONFIG_PATH)

    summary = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=True,
    )

    assert summary.rows_processed > 0
    assert summary.table_row_counts.get("public.users", 0) > 0

    target = await asyncpg.connect(target_dsn)
    source = await asyncpg.connect(source_dsn)
    try:
        leak_stats = await assert_demo_corp_leak_probes(target)
        assert leak_stats["probes_passed"] == leak_stats["probes_run"]
        await assert_demo_corp_action_shapes(target)
        await assert_demo_corp_ner_columns_changed(source, target)
        await assert_demo_corp_passthrough_unchanged(source, target)
        await _assert_row_parity(source, target)
        await _assert_structural_integrity(target)
        assert await audit_count(target) > 0
    finally:
        await target.close()
        await source.close()

    verify_report = await run_demo_corp_verification(
        config=config,
        source_dsn=source_dsn,
        target_dsn=target_dsn,
    )
    assert verify_report.counts()  # exercised; failures raise inside helper


async def _assert_row_parity(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
) -> None:
    for table in ("public.users", "public.organizations", "clinical.patients"):
        source_count = await count_rows(source, table)
        target_count = await count_rows(target, table)
        assert target_count == source_count, f"row count mismatch for {table}"

    for parent, child_prefix in (
        ("clinical.patient_visits", "patient_visits_"),
        ("public.raw_events", "raw_events_"),
    ):
        source_count = await count_partitioned_table_rows(
            source, parent, child_prefix=child_prefix
        )
        target_count = await count_partitioned_table_rows(
            target, parent, child_prefix=child_prefix
        )
        assert target_count == source_count, f"row count mismatch for {parent}"


async def _assert_structural_integrity(conn: asyncpg.Connection) -> None:
    assert await all_fks_valid(conn)
    assert await partition_count(conn, "public.raw_events") == _RAW_EVENT_PARTITIONS
    assert (
        await partition_count(conn, "clinical.patient_visits")
        == _PATIENT_VISIT_PARTITIONS
    )
    assert not await table_exists(conn, "audit_internal.audit_log_events")

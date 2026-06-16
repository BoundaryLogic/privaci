"""End-to-end integration test: Demo Corp source through the masking pipeline."""

from __future__ import annotations

import asyncpg
import pytest

from privaci.config import load_config
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import (
    DEMO_CORP_FORBIDDEN_EMAILS,
    DEMO_CORP_FORBIDDEN_PHONES,
    DEMO_CORP_FORBIDDEN_SSNS,
    DEMO_CORP_STATIC_PASSWORD,
    TEST_SALT,
)
from tests.integration.assertions import (
    all_fks_valid,
    assert_no_pii_present,
    audit_count,
    count_partitioned_table_rows,
    count_rows,
    fetch_column_values,
    partition_count,
    table_exists,
)
from tests.integration.conftest import DEMO_CORP_CONFIG_PATH

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_RAW_EVENT_PARTITIONS = 24
_PATIENT_VISIT_PARTITIONS = 4


async def test_demo_corp_masking_pipeline(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
) -> None:
    # Arrange
    config = load_config(DEMO_CORP_CONFIG_PATH)

    # Act
    summary = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=True,
    )

    # Assert — pipeline processed the configured transform tables.
    assert summary.rows_processed > 0
    assert summary.table_row_counts.get("public.users", 0) > 0

    target = await asyncpg.connect(target_dsn)
    try:
        await _assert_no_source_pii_leaked(target)
        await _assert_row_parity(source_dsn, target)
        await _assert_structural_integrity(target)
        assert await audit_count(target) > 0
    finally:
        await target.close()


async def _assert_no_source_pii_leaked(conn: asyncpg.Connection) -> None:
    await assert_no_pii_present(
        conn,
        "public.users",
        "email",
        list(DEMO_CORP_FORBIDDEN_EMAILS),
    )
    await assert_no_pii_present(
        conn,
        "public.organizations",
        "billing_email",
        ["billing1@example.test"],
    )
    await assert_no_pii_present(
        conn,
        "clinical.patients",
        "email",
        ["patient1@example.test"],
    )
    await assert_no_pii_present(
        conn,
        "public.users",
        "ssn",
        list(DEMO_CORP_FORBIDDEN_SSNS),
    )
    await assert_no_pii_present(
        conn,
        "public.users",
        "phone",
        list(DEMO_CORP_FORBIDDEN_PHONES),
    )

    password_hashes = await fetch_column_values(
        conn, "public.users", "password_hash", limit=20
    )
    assert password_hashes
    assert all(value == DEMO_CORP_STATIC_PASSWORD for value in password_hashes)


async def _assert_row_parity(
    source_dsn: str,
    target: asyncpg.Connection,
) -> None:
    source = await asyncpg.connect(source_dsn)
    try:
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
    finally:
        await source.close()


async def _assert_structural_integrity(conn: asyncpg.Connection) -> None:
    assert await all_fks_valid(conn)
    assert await partition_count(conn, "public.raw_events") == _RAW_EVENT_PARTITIONS
    assert (
        await partition_count(conn, "clinical.patient_visits")
        == _PATIENT_VISIT_PARTITIONS
    )
    assert not await table_exists(conn, "audit_internal.audit_log_events")

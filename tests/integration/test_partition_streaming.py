"""Integration tests for native partition streaming and resume."""

from __future__ import annotations

import asyncpg
import pytest

from privaci.config import load_config
from privaci.pipeline import run_masking_pipeline
from privaci.state.resume import load_checkpoints
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import (
    count_partitioned_table_rows,
    count_rows,
    partition_count,
)
from tests.integration.conftest import DEMO_CORP_CONFIG_PATH

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_RAW_EVENT_PARTITIONS = 24
_PATIENT_VISIT_PARTITIONS = 4


async def test_partitioned_tables_stream_with_full_row_parity(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    # Arrange
    config = load_config(DEMO_CORP_CONFIG_PATH)

    # Act
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )

    # Assert
    source = await asyncpg.connect(source_dsn)
    target = await asyncpg.connect(target_dsn)
    try:
        for parent, child_prefix in (
            ("public.raw_events", "raw_events_"),
            ("clinical.patient_visits", "patient_visits_"),
        ):
            source_count = await count_partitioned_table_rows(
                source, parent, child_prefix=child_prefix
            )
            target_count = await count_partitioned_table_rows(
                target, parent, child_prefix=child_prefix
            )
            assert target_count == source_count

        assert (
            await partition_count(target, "public.raw_events") == _RAW_EVENT_PARTITIONS
        )
        assert (
            await partition_count(target, "clinical.patient_visits")
            == _PATIENT_VISIT_PARTITIONS
        )
    finally:
        await source.close()
        await target.close()


async def test_resume_restreams_only_affected_partition_child(
    source_dsn: str,
    target_dsn: str,
    demo_corp_source_loaded: None,
    clean_target: None,
    spacy_ner_ready: None,
) -> None:
    # Arrange
    config = load_config(DEMO_CORP_CONFIG_PATH)
    summary = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )
    partition = "public.raw_events_2024_06"
    schema, table_name = "public", "raw_events_2024_06"
    control_partition = "public.raw_events_2024_01"

    target = await asyncpg.connect(target_dsn)
    source = await asyncpg.connect(source_dsn)
    try:
        control_before = await count_rows(target, control_partition)
        await target.execute(f'TRUNCATE TABLE "{schema}"."{table_name}"')
        await target.execute(
            """
            UPDATE _privaci.table_checkpoints
            SET status = 'pending',
                last_pk_value = NULL,
                rows_processed = 0
            WHERE run_id = $1
              AND schema_name = $2
              AND table_name = $3
            """,
            summary.run_id,
            schema,
            table_name,
        )
        checkpoints = await load_checkpoints(target, summary.run_id)
        expected = await count_rows(source, partition)
    finally:
        await target.close()
        await source.close()

    # Act
    await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
        resume_run_id=summary.run_id,
        checkpoints=checkpoints,
    )

    # Assert
    target = await asyncpg.connect(target_dsn)
    try:
        assert await count_rows(target, partition) == expected
        assert await count_rows(target, control_partition) == control_before
    finally:
        await target.close()

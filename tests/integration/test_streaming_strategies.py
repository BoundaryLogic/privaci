"""Integration tests for streaming strategies and COPY-binary passthrough."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from privaci.catalog import introspect_catalog
from privaci.config.actions import FakeAction
from privaci.config.models import Config, TableConfig
from privaci.pipeline import run_masking_pipeline
from privaci.state.resume import load_checkpoints
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import count_rows

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_SPIKE_COPY_SQL = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "sql"
    / "spikes"
    / "01_copy_roundtrip.sql"
)
_SPIKE_CYCLE_SQL = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "sql"
    / "spikes"
    / "02_cyclic_fk.sql"
)
_SPIKE_TABLE = "public.spike_copy_roundtrip"


async def _load_spike_copy(source_dsn: str) -> None:
    conn = await asyncpg.connect(source_dsn)
    try:
        await conn.execute(_SPIKE_COPY_SQL.read_text(encoding="utf-8"))
    finally:
        await conn.close()


async def _load_spike_cycle(source_dsn: str) -> None:
    conn = await asyncpg.connect(source_dsn)
    try:
        await conn.execute(_SPIKE_CYCLE_SQL.read_text(encoding="utf-8"))
        await conn.execute("""
            INSERT INTO spike_cycle_a (id, b_id) VALUES (1, NULL);
            INSERT INTO spike_cycle_b (id, a_id) VALUES (1, 1);
            UPDATE spike_cycle_a SET b_id = 1 WHERE id = 1;
            """)
    finally:
        await conn.close()


async def _row_count(dsn: str, qualified_table: str) -> int:
    conn = await asyncpg.connect(dsn)
    try:
        return await count_rows(conn, qualified_table)
    finally:
        await conn.close()


async def _spike_passthrough_config(source_dsn: str) -> Config:
    conn = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()
    tables = {
        table_id: TableConfig(strategy="exclude")
        for table_id in catalog.tables
        if table_id != _SPIKE_TABLE
    }
    tables[_SPIKE_TABLE] = TableConfig()
    return Config(version="1.0", auto_detect=False, batch_size=500, tables=tables)


async def _spike_cycle_config(source_dsn: str) -> Config:
    conn = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()
    tables = {table_id: TableConfig(strategy="exclude") for table_id in catalog.tables}
    tables["public.spike_cycle_a"] = TableConfig()
    tables["public.spike_cycle_b"] = TableConfig()
    return Config(version="1.0", auto_detect=False, tables=tables)


async def test_passthrough_binary_copy_preserves_spike_table(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange
    await _load_spike_copy(source_dsn)
    config = await _spike_passthrough_config(source_dsn)
    source_count = await _row_count(source_dsn, _SPIKE_TABLE)

    # Act
    summary = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )

    # Assert
    assert summary.table_row_counts[_SPIKE_TABLE] == source_count
    target_count = await _row_count(target_dsn, _SPIKE_TABLE)
    assert target_count == source_count

    source = await asyncpg.connect(source_dsn)
    target = await asyncpg.connect(target_dsn)
    try:
        row_sql = (
            "SELECT id, label, amount, active, payload "
            "FROM spike_copy_roundtrip ORDER BY id"
        )
        source_rows = await source.fetch(row_sql)
        target_rows = await target.fetch(row_sql)
    finally:
        await source.close()
        await target.close()
    assert [dict(row) for row in source_rows] == [dict(row) for row in target_rows]


async def test_empty_strategy_creates_table_without_rows(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange
    await _load_spike_copy(source_dsn)
    config = await _spike_passthrough_config(source_dsn)
    config.tables[_SPIKE_TABLE] = TableConfig(strategy="empty")
    source_count = await _row_count(source_dsn, _SPIKE_TABLE)
    assert source_count > 0

    # Act
    summary = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )

    # Assert
    assert summary.table_row_counts[_SPIKE_TABLE] == 0
    target_count = await _row_count(target_dsn, _SPIKE_TABLE)
    assert target_count == 0


async def test_deferred_fk_cycle_streams_both_tables(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange
    await _load_spike_cycle(source_dsn)
    config = await _spike_cycle_config(source_dsn)

    # Act
    summary = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
    )

    # Assert
    assert summary.table_row_counts["public.spike_cycle_a"] == 1
    assert summary.table_row_counts["public.spike_cycle_b"] == 1


async def test_resume_continues_spike_table_after_partial_run(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    await _load_spike_copy(source_dsn)
    config = await _spike_passthrough_config(source_dsn)
    tables = dict(config.tables)
    tables[_SPIKE_TABLE] = TableConfig(
        columns={"label": FakeAction(action="fake", provider="company")},
    )
    config = config.model_copy(update={"batch_size": 1, "tables": tables})
    original_stream = __import__(
        "privaci.stream.table",
        fromlist=["stream_table"],
    ).stream_table
    calls = {"count": 0}

    async def _interrupt_after_first_batch(*args: object, **kwargs: object) -> int:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated crash")
        return await original_stream(*args, **kwargs)

    mocker.patch(
        "privaci.pipeline.streaming.stream_table",
        side_effect=_interrupt_after_first_batch,
    )

    # Act
    with pytest.raises(RuntimeError, match="simulated crash"):
        await run_masking_pipeline(
            source_dsn,
            target_dsn,
            config,
            TEST_SALT,
            audit_enabled=False,
        )

    target = await asyncpg.connect(target_dsn)
    try:
        runs = await target.fetch("""
            SELECT run_id
            FROM _privaci.runs
            WHERE status = 'failed'
            ORDER BY started_at DESC
            LIMIT 1
            """)
        run_id = runs[0]["run_id"]
        checkpoints = await load_checkpoints(target, run_id)
    finally:
        await target.close()

    resumed = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
        resume_run_id=run_id,
        checkpoints=checkpoints,
    )

    # Assert
    source_count = await _row_count(source_dsn, _SPIKE_TABLE)
    target_count = await _row_count(target_dsn, _SPIKE_TABLE)
    assert resumed.rows_processed >= source_count - 1
    assert target_count == source_count

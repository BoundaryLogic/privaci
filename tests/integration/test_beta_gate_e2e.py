"""Beta-gate end-to-end tests (OpenSpec §18.4-18.6).

Each test loads a focused edge-case schema into the source database, runs the
full masking pipeline against a real target, and verifies the engine's headline
guarantees: cyclic-FK integrity, graceful handling of polymorphic (soft) FKs,
and crash-safe resume with zero data loss or duplication.

These are integration tests and require the compose.dev.yml Postgres pair.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import asyncpg
import pytest

from privaci.config.actions import FakeAction
from privaci.config.models import TableConfig
from privaci.observability import configure_logging
from privaci.pipeline import run_masking_pipeline
from privaci.state.resume import load_checkpoints
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import all_fks_valid, count_rows, value_present
from tests.integration.catalog_config import config_keep_only

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_EDGE_CASE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "edge-cases"


async def _load_sql(dsn: str, filename: str) -> None:
    """Execute one edge-case SQL file against ``dsn``."""
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute((_EDGE_CASE_DIR / filename).read_text(encoding="utf-8"))
    finally:
        await conn.close()


async def test_cyclic_fk_schema_streams_with_integrity(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange
    await _load_sql(source_dsn, "deferrable-cycle.sql")
    config = await config_keep_only(
        source_dsn,
        {
            "beta_cycle.departments": TableConfig(),
            "beta_cycle.employees": TableConfig(
                columns={
                    "email": FakeAction(action="fake", provider="email"),
                    "full_name": FakeAction(action="fake", provider="full_name"),
                },
            ),
        },
        auto_detect=False,
        batch_size=500,
    )

    # Act
    summary = await run_masking_pipeline(
        source_dsn, target_dsn, config, TEST_SALT, audit_enabled=False
    )

    # Assert — both sides of the cycle stream and integrity holds.
    assert summary.table_row_counts["beta_cycle.employees"] == 30
    assert summary.table_row_counts["beta_cycle.departments"] == 5

    target = await asyncpg.connect(target_dsn)
    try:
        assert await count_rows(target, "beta_cycle.employees") == 30
        assert await count_rows(target, "beta_cycle.departments") == 5
        assert await all_fks_valid(target)
        # PII did not survive masking.
        assert not await value_present(
            target, "beta_cycle.employees", "email", "employee1@example.test"
        )
    finally:
        await target.close()


async def test_polymorphic_fk_warns_but_run_succeeds(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange
    await _load_sql(source_dsn, "polymorphic-fk.sql")
    config = await config_keep_only(
        source_dsn,
        {
            "beta_poly.users": TableConfig(
                columns={"email": FakeAction(action="fake", provider="email")},
            ),
            "beta_poly.posts": TableConfig(),
            "beta_poly.comments": TableConfig(
                columns={
                    "author_email": FakeAction(action="fake", provider="email"),
                },
            ),
        },
        auto_detect=False,
        batch_size=500,
    )
    stream = io.StringIO()
    configure_logging("info", stream=stream)

    # Act
    try:
        summary = await run_masking_pipeline(
            source_dsn, target_dsn, config, TEST_SALT, audit_enabled=False
        )
    finally:
        logging.getLogger().handlers.clear()

    # Assert — run completes and a polymorphic warning was emitted.
    assert summary.table_row_counts["beta_poly.comments"] == 20
    lines = [json.loads(raw) for raw in stream.getvalue().splitlines() if raw]
    events = [line["event"] for line in lines]
    assert "polymorphic_fk_warning" in events
    warning = next(line for line in lines if line["event"] == "polymorphic_fk_warning")
    assert warning["table_id"] == "beta_poly.comments"
    assert lines[-1]["event"] == "run.end"
    assert lines[-1]["status"] == "succeeded"

    target = await asyncpg.connect(target_dsn)
    try:
        assert await count_rows(target, "beta_poly.comments") == 20
        assert not await value_present(
            target, "beta_poly.comments", "author_email", "author1@example.test"
        )
    finally:
        await target.close()


async def test_resume_after_crash_has_no_loss_or_duplication(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
    mocker: pytest.MockFixture,
) -> None:
    # Arrange — many small batches so the crash lands mid-table.
    await _load_sql(source_dsn, "resume-many-rows.sql")
    config = await config_keep_only(
        source_dsn,
        {
            "beta_resume.records": TableConfig(
                columns={"email": FakeAction(action="fake", provider="email")},
            )
        },
        auto_detect=False,
        batch_size=10,
    )

    original_stream = __import__(
        "privaci.stream.table", fromlist=["stream_table"]
    ).stream_table
    calls = {"count": 0}

    async def _crash_on_first(*args: object, **kwargs: object) -> int:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("simulated crash")
        return await original_stream(*args, **kwargs)

    mocker.patch("privaci.pipeline.streaming.stream_table", side_effect=_crash_on_first)

    # Act 1 — first run crashes and records a failed run.
    with pytest.raises(RuntimeError, match="simulated crash"):
        await run_masking_pipeline(
            source_dsn, target_dsn, config, TEST_SALT, audit_enabled=False
        )

    target = await asyncpg.connect(target_dsn)
    try:
        failed = await target.fetch("""
            SELECT run_id FROM _privaci.runs
            WHERE status = 'failed' ORDER BY started_at DESC LIMIT 1
            """)
        run_id = failed[0]["run_id"]
        checkpoints = await load_checkpoints(target, run_id)
    finally:
        await target.close()

    # Act 2 — resume from the recorded checkpoints.
    resumed = await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        TEST_SALT,
        audit_enabled=False,
        resume_run_id=run_id,
        checkpoints=checkpoints,
    )

    # Assert — exact parity, zero duplicate primary keys.
    source_count = 100
    assert resumed.rows_processed >= source_count - config.batch_size
    target = await asyncpg.connect(target_dsn)
    try:
        assert await count_rows(target, "beta_resume.records") == source_count
        distinct_ids = await target.fetchval(
            "SELECT count(DISTINCT id)::int FROM beta_resume.records"
        )
        assert distinct_ids == source_count  # no duplication
        assert not await value_present(
            target, "beta_resume.records", "email", "record1@example.test"
        )
    finally:
        await target.close()

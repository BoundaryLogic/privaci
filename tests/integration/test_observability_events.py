"""Integration test: a real run emits a valid JSON-lines event stream."""

from __future__ import annotations

import io
import json
import logging

import asyncpg
import pytest

from privaci.catalog import introspect_catalog
from privaci.config.actions import FakeAction
from privaci.config.models import Config, TableConfig
from privaci.observability import configure_logging
from privaci.pipeline import run_masking_pipeline
from tests.fixtures.constants import TEST_SALT

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_KEEP_TABLES = frozenset({"public.organizations", "public.users"})


async def _minimal_config(source_dsn: str) -> Config:
    conn = await asyncpg.connect(source_dsn)
    try:
        catalog = await introspect_catalog(conn)
    finally:
        await conn.close()
    tables: dict[str, TableConfig] = {
        table_id: TableConfig(strategy="exclude")
        for table_id in catalog.tables
        if table_id not in _KEEP_TABLES
    }
    tables["public.organizations"] = TableConfig()
    tables["public.users"] = TableConfig(
        columns={"email": FakeAction(action="fake", provider="email")},
    )
    return Config(version="1.0", auto_detect=False, batch_size=500, tables=tables)


async def test_run_emits_parseable_lifecycle_events(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange
    stream = io.StringIO()
    configure_logging("info", stream=stream)
    config = await _minimal_config(source_dsn)

    # Act
    try:
        await run_masking_pipeline(
            source_dsn,
            target_dsn,
            config,
            TEST_SALT,
            audit_enabled=False,
        )
    finally:
        logging.getLogger().handlers.clear()

    # Assert: every non-empty line parses as JSON.
    lines = [json.loads(raw) for raw in stream.getvalue().splitlines() if raw]
    assert lines
    events = [line["event"] for line in lines]
    assert events.count("run.start") == 1
    assert events.count("run.end") == 1
    assert "schema.cloned" in events
    assert "table.start" in events
    assert "table.end" in events

    run_starts = [line for line in lines if line["event"] == "run.start"]
    run_ends = [line for line in lines if line["event"] == "run.end"]
    assert run_starts[0]["run_id"] == run_ends[0]["run_id"]
    assert run_ends[0]["status"] == "succeeded"

"""Integration tests for the programmatic masking pipeline."""

from __future__ import annotations

import os

import asyncpg
import pytest

from privaci.catalog import introspect_catalog
from privaci.catalog.identifiers import quote_pg_identifier
from privaci.config.actions import FakeAction
from privaci.config.models import Config, TableConfig
from privaci.pipeline import run_masking_pipeline

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_SOURCE = os.environ.get(
    "SOURCE_DB_URL",
    "postgresql://postgres:dev@127.0.0.1:55432/privaci_source",
)
_TARGET = os.environ.get(
    "TARGET_DB_URL",
    "postgresql://postgres:dev@127.0.0.1:55433/privaci_target",
)
_KEEP_TABLES = frozenset({"public.organizations", "public.users"})


async def _minimal_demo_config() -> Config:
    """Build a config that masks ``public.users`` and excludes everything else."""
    conn = await asyncpg.connect(_SOURCE)
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
    return Config(version="1.0", batch_size=500, tables=tables)


async def _reset_target() -> None:
    """Drop application schemas on the target so each run starts clean."""
    conn = await asyncpg.connect(_TARGET)
    try:
        rows = await conn.fetch("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND schema_name NOT LIKE 'pg_%'
            """)
        for row in rows:
            quoted_schema = quote_pg_identifier(row["schema_name"])
            await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
    finally:
        await conn.close()


async def test_run_masking_pipeline_masks_users_email(
    test_salt: str,
    postgres_available: None,
) -> None:
    # Arrange
    await _reset_target()
    config = await _minimal_demo_config()

    # Act
    summary = await run_masking_pipeline(
        _SOURCE,
        _TARGET,
        config,
        test_salt,
        audit_enabled=False,
    )

    # Assert
    assert summary.rows_processed > 0
    assert summary.table_row_counts.get("public.users", 0) > 0

    target = await asyncpg.connect(_TARGET)
    try:
        emails = await target.fetch("SELECT email FROM public.users LIMIT 5")
    finally:
        await target.close()
    assert emails
    assert all("@" in row["email"] for row in emails)

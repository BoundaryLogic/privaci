"""Fixtures for Demo Corp end-to-end integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest

from privaci.catalog.identifiers import quote_pg_identifier

_DEMO_CORP_SQL_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "demo-corp"
)
DEMO_CORP_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "configs" / "demo-corp.yaml"
)


async def _apply_sql_dir(dsn: str, sql_dir: Path) -> None:
    """Execute every ``*.sql`` file in ``sql_dir`` in lexicographic order."""
    import asyncpg

    paths = sorted(sql_dir.glob("*.sql"))
    conn = await asyncpg.connect(dsn)
    try:
        for path in paths:
            await conn.execute(path.read_text(encoding="utf-8"))
    finally:
        await conn.close()


async def _reset_target(dsn: str) -> None:
    """Drop every user schema on the target so each run starts clean."""
    import asyncpg

    conn = await asyncpg.connect(dsn)
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


@pytest.fixture(scope="session")
def demo_corp_source_loaded(source_dsn: str, postgres_available: None) -> None:
    """Load the committed Demo Corp mini-tier SQL into the source database."""
    asyncio.run(_apply_sql_dir(source_dsn, _DEMO_CORP_SQL_DIR))


@pytest.fixture
def clean_target(target_dsn: str, postgres_available: None) -> Iterator[None]:
    """Reset the target database before each integration test."""
    asyncio.run(_reset_target(target_dsn))
    yield
    asyncio.run(_reset_target(target_dsn))

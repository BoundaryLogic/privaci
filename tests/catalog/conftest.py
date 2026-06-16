"""Fixtures for catalog integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

_CATALOG_SQL_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sql" / "catalog"


@pytest.fixture(scope="session")
def catalog_sql_paths() -> list[Path]:
    """Return catalog SQL fixture paths in apply order."""
    return sorted(_CATALOG_SQL_DIR.glob("*.sql"))


@pytest.fixture
async def catalog_schema(
    source_dsn: str,
    catalog_sql_paths: list[Path],
    postgres_available: None,
) -> str:
    """Apply catalog fixtures and return the source DSN."""
    import asyncpg

    conn = await asyncpg.connect(source_dsn)
    try:
        await conn.execute("DROP SCHEMA IF EXISTS catalog_demo CASCADE")
        await conn.execute("CREATE SCHEMA catalog_demo")
        for path in catalog_sql_paths:
            await conn.execute(path.read_text(encoding="utf-8"))
    finally:
        await conn.close()
    return source_dsn

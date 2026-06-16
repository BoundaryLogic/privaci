"""Verify edge-case SQL fixtures apply cleanly to Postgres."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

_EDGE_SQL_DIR = Path(__file__).resolve().parent / "sql" / "edge-cases"

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize(
    "sql_path", sorted(_EDGE_SQL_DIR.glob("*.sql")), ids=lambda p: p.name
)
async def test_edge_case_sql_applies(
    source_dsn: str,
    postgres_available: None,
    sql_path: Path,
) -> None:
    # Arrange
    conn = await asyncpg.connect(source_dsn)

    # Act / Assert
    try:
        await conn.execute(sql_path.read_text(encoding="utf-8"))
    finally:
        await conn.execute("DROP SCHEMA IF EXISTS edge_cases CASCADE")
        await conn.execute("DROP ROLE IF EXISTS fixture_ro")
        await conn.close()

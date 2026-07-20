"""Unit tests for shared DDL execute helper."""

from __future__ import annotations

from unittest.mock import AsyncMock

import asyncpg
import pytest

from privaci.errors import PreflightError
from privaci.schema.execute import execute_ddl


@pytest.mark.asyncio
async def test_execute_ddl_success() -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="OK")

    await execute_ddl(conn, "CREATE SCHEMA IF NOT EXISTS public")

    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_ddl_wraps_postgres_error() -> None:
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=asyncpg.PostgresError("boom"))

    with pytest.raises(PreflightError, match="DDL execution failed"):
        await execute_ddl(conn, "CREATE TABLE t (id int)")

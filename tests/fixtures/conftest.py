"""Tier-1 mini-schema pytest fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest

from privaci.catalog.identifiers import quote_pg_identifier
from tests.fixtures.builders import MiniSchema, orgs_users_cycle, users_only


@pytest.fixture
async def mini_schema_conn(
    source_dsn: str,
    postgres_available: None,
    request: pytest.FixtureRequest,
) -> AsyncIterator[asyncpg.Connection]:
    """Apply a parametrized :class:`MiniSchema` and yield a source connection.

    Parametrize with
    ``@pytest.mark.parametrize("mini_schema_conn", [...], indirect=True)``.
    Each factory is called with default kwargs unless the param is a ``MiniSchema``.
    """
    param = getattr(request, "param", orgs_users_cycle)
    build: MiniSchema
    if callable(param):
        build = param()
    else:
        build = param

    quoted_schema = quote_pg_identifier(build.schema_name)
    conn = await asyncpg.connect(source_dsn)
    try:
        await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
        await conn.execute(build.sql)
        yield conn
    finally:
        await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
        await conn.close()


@pytest.fixture
async def mini_users_schema(
    source_dsn: str,
    postgres_available: None,
) -> AsyncIterator[str]:
    """Apply the default ``users_only`` mini schema; yield the source DSN."""
    build = users_only()
    quoted_schema = quote_pg_identifier(build.schema_name)
    conn = await asyncpg.connect(source_dsn)
    try:
        await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
        await conn.execute(build.sql)
    finally:
        await conn.close()
    yield source_dsn
    conn = await asyncpg.connect(source_dsn)
    try:
        await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
    finally:
        await conn.close()

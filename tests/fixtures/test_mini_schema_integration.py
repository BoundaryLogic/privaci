"""Integration tests for Tier-1 mini-schema fixtures."""

from __future__ import annotations

import asyncpg
import pytest

from tests.fixtures.builders import orgs_users_cycle
from tests.fixtures.constants import DEMO_CORP_FORBIDDEN_EMAILS

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("mini_schema_conn", [orgs_users_cycle], indirect=True)
async def test_mini_schema_conn_loads_orgs_users_cycle(
    mini_schema_conn: asyncpg.Connection,
) -> None:
    # Act
    count = await mini_schema_conn.fetchval("SELECT count(*)::int FROM mini_demo.users")

    # Assert
    assert count == 2
    leaked = await mini_schema_conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM mini_demo.users WHERE email = $1)",
        DEMO_CORP_FORBIDDEN_EMAILS[0],
    )
    assert leaked is True

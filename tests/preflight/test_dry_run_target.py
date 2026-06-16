"""Tests for dry-run target collision behaviour."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import CatalogResult, LoadPlan
from privaci.config.models import Config
from privaci.preflight.checks import run_target_checks


@pytest.mark.asyncio
async def test_run_target_checks_skips_collision_enforcement_in_dry_run() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchval = AsyncMock(
        side_effect=[True, False, 2]
    )  # CREATE priv, _privaci exists, user table count
    catalog = CatalogResult(tables={}, load_plan=LoadPlan(layers=()))
    config = Config(version="1.0", on_existing_data="fail")

    # Act
    warnings = await run_target_checks(conn, config, catalog, dry_run=True)

    # Assert
    assert any("real run will fail" in warning for warning in warnings)


@pytest.mark.asyncio
async def test_run_target_checks_enforces_collision_on_real_run() -> None:
    # Arrange
    from privaci.errors import PreflightError

    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=2)
    catalog = CatalogResult(tables={}, load_plan=LoadPlan(layers=()))
    config = Config(version="1.0", on_existing_data="fail")

    # Act / Assert
    with pytest.raises(PreflightError, match="user table"):
        await run_target_checks(conn, config, catalog, dry_run=False)

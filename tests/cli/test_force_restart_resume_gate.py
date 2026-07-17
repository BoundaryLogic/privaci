"""Unit tests for resume schema-snapshot gate and force-restart policy."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from privaci.catalog.models import CatalogResult, LoadPlan
from privaci.cli._run import _apply_force_restart
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.state.schema_snapshot import validate_resume_schema_snapshot


@pytest.mark.asyncio
async def test_resume_without_snapshot_fails_in_replicate(
    mocker: MockerFixture,
) -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"source_schema_snapshot": None})
    catalog = CatalogResult(tables={}, load_plan=LoadPlan(layers=()))

    # Act / Assert
    with pytest.raises(PreflightError, match="schema snapshot"):
        await validate_resume_schema_snapshot(
            conn,
            uuid.uuid4(),
            catalog,
            schema_mode="replicate",
        )


@pytest.mark.asyncio
async def test_resume_without_snapshot_ok_assume_existing(
    mocker: MockerFixture,
) -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"source_schema_snapshot": None})
    catalog = CatalogResult(tables={}, load_plan=LoadPlan(layers=()))

    # Act / Assert — must not raise
    await validate_resume_schema_snapshot(
        conn,
        uuid.uuid4(),
        catalog,
        schema_mode="assume_existing",
    )


@pytest.mark.asyncio
async def test_force_restart_rejects_fail_policy() -> None:
    # Arrange
    config = Config(version="1.0", on_existing_data="fail")

    # Act / Assert
    with pytest.raises(PreflightError, match="force-restart"):
        await _apply_force_restart(config, "postgresql://localhost/db")


@pytest.mark.asyncio
async def test_force_restart_abandons_runs(mocker: MockerFixture) -> None:
    # Arrange
    config = Config(version="1.0", on_existing_data="truncate")
    target = MagicMock()
    target.close = AsyncMock()
    mocker.patch(
        "privaci.cli._run.asyncpg.connect",
        new=AsyncMock(return_value=target),
    )
    mocker.patch(
        "privaci.cli._run.ensure_state_schema",
        new=AsyncMock(),
    )
    abandon = mocker.patch(
        "privaci.cli._run.abandon_incomplete_runs",
        new=AsyncMock(return_value=2),
    )

    # Act
    await _apply_force_restart(config, "postgresql://localhost/db")

    # Assert
    abandon.assert_awaited_once()
    target.close.assert_awaited()

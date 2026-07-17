"""Unit tests for target collision policy under schema modes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.models import Config, TableConfig
from privaci.errors import PreflightError
from privaci.preflight.target import (
    collision_warning_for_dry_run,
    ensure_target_ready,
)


def _users_catalog() -> CatalogResult:
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="email", data_type="text", not_null=True),
        ),
        primary_key=("id",),
    )
    return CatalogResult(
        tables={"public.users": table},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=("public.users",)),)),
    )


@pytest.mark.asyncio
async def test_replicate_fail_refuses_existing_user_tables() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=3)
    catalog = CatalogResult(tables={}, load_plan=LoadPlan(layers=()))
    config = Config(version="1.0", on_existing_data="fail")

    # Act / Assert
    with pytest.raises(PreflightError, match="user table"):
        await ensure_target_ready(conn, config, catalog)


@pytest.mark.asyncio
async def test_assume_existing_fail_allows_empty_in_scope_tables() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=["public.users", False])
    config = Config(
        version="1.0",
        schema_mode="assume_existing",
        on_existing_data="fail",
    )

    # Act / Assert
    await ensure_target_ready(conn, config, _users_catalog())


@pytest.mark.asyncio
async def test_assume_existing_fail_refuses_populated_in_scope_tables() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=["public.users", True])
    config = Config(
        version="1.0",
        schema_mode="assume_existing",
        on_existing_data="fail",
    )

    # Act / Assert
    with pytest.raises(PreflightError, match="existing rows"):
        await ensure_target_ready(conn, config, _users_catalog())


@pytest.mark.asyncio
async def test_dry_run_warning_for_populated_assume_existing() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=["public.users", True])
    config = Config(
        version="1.0",
        schema_mode="assume_existing",
        on_existing_data="fail",
    )

    # Act
    warning = await collision_warning_for_dry_run(conn, config, _users_catalog())

    # Assert
    assert warning is not None
    assert "public.users" in warning
    assert "truncate" in warning


@pytest.mark.asyncio
async def test_dry_run_no_warning_for_empty_assume_existing() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=["public.users", False])
    config = Config(
        version="1.0",
        schema_mode="assume_existing",
        on_existing_data="fail",
    )

    # Act
    warning = await collision_warning_for_dry_run(conn, config, _users_catalog())

    # Assert
    assert warning is None


@pytest.mark.asyncio
async def test_assume_existing_fail_skips_excluded_partition_children() -> None:
    # Arrange
    child = TableInfo(
        schema_name="public",
        table_name="events_2024",
        columns=(ColumnInfo(name="id", data_type="integer", not_null=True),),
        primary_key=("id",),
        parent_partition="public.events",
    )
    catalog = CatalogResult(
        tables={"public.events_2024": child},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=("public.events_2024",)),)),
    )
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=["public.events_2024", True])
    config = Config(
        version="1.0",
        schema_mode="assume_existing",
        on_existing_data="fail",
        tables={"public.events": TableConfig(strategy="exclude")},
    )

    # Act / Assert — parent exclude applies to children via config_table_id
    await ensure_target_ready(conn, config, catalog)
    conn.fetchval.assert_not_awaited()

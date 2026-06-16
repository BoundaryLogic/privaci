"""Unit tests for individual pre-flight checks."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    ForeignKeyInfo,
    LoadPlan,
    TableInfo,
    table_id,
)
from privaci.config.actions import NullAction
from privaci.config.models import Config, TableConfig
from privaci.errors import ConfigError, PreflightError
from privaci.preflight.checks import (
    verify_config_tables_exist,
    verify_exclude_strategy,
    verify_null_actions,
    warn_disk_capacity,
)
from privaci.preflight.target import ensure_target_ready


@pytest.mark.asyncio
async def test_ensure_target_ready_fails_when_not_empty() -> None:
    # Arrange
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=3)
    catalog = CatalogResult(tables={}, load_plan=LoadPlan(layers=()))
    config = Config(version="1.0", on_existing_data="fail")

    # Act / Assert
    with pytest.raises(PreflightError, match="user table"):
        await ensure_target_ready(conn, config, catalog)


def test_verify_config_tables_exist_rejects_missing_tables() -> None:
    # Arrange
    config = Config(
        version="1.0",
        tables={"public.missing": TableConfig()},
    )
    catalog = CatalogResult(tables={}, load_plan=LoadPlan(layers=()))

    # Act / Assert
    with pytest.raises(ConfigError, match="absent from the source"):
        verify_config_tables_exist(config, catalog)


def test_verify_null_actions_rejects_not_null_column() -> None:
    # Arrange
    users = TableInfo(
        "public",
        "users",
        (ColumnInfo("email", "text", True),),
    )
    catalog = CatalogResult(
        tables={table_id("public", "users"): users},
        load_plan=LoadPlan(layers=()),
    )
    config = Config(
        version="1.0",
        tables={
            "public.users": TableConfig(
                columns={"email": NullAction(action="null")},
            ),
        },
    )

    # Act / Assert
    with pytest.raises(ConfigError, match="NOT NULL"):
        verify_null_actions(config, catalog)


def test_warn_disk_capacity_returns_warning_for_large_catalog() -> None:
    # Arrange
    huge = TableInfo("public", "big", (), estimated_rows=60_000_000)
    catalog = CatalogResult(
        tables={table_id("public", "big"): huge},
        load_plan=LoadPlan(layers=()),
    )

    # Act
    warnings = warn_disk_capacity(catalog)

    # Assert
    assert len(warnings) == 1


def test_verify_exclude_strategy_delegates_to_schema_validation() -> None:
    # Arrange
    orgs = TableInfo("public", "orgs", (ColumnInfo("id", "integer", True),))
    users = TableInfo(
        "public",
        "users",
        (
            ColumnInfo("id", "integer", True),
            ColumnInfo("org_id", "integer", True),
        ),
        foreign_keys=(
            ForeignKeyInfo(
                name="users_org_fk",
                source_columns=("org_id",),
                referenced_schema="public",
                referenced_table="orgs",
                referenced_columns=("id",),
                on_delete="NO ACTION",
                on_update="NO ACTION",
                deferrable=True,
                initially_deferred=False,
            ),
        ),
    )
    catalog = CatalogResult(
        tables={
            table_id("public", "orgs"): orgs,
            table_id("public", "users"): users,
        },
        load_plan=LoadPlan(layers=()),
    )
    config = Config(
        version="1.0",
        tables={table_id("public", "orgs"): TableConfig(strategy="exclude")},
    )

    # Act / Assert
    with pytest.raises(ConfigError, match="NOT NULL FKs"):
        verify_exclude_strategy(config, catalog)

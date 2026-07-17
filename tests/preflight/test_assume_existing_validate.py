"""Async unit tests for assume_existing table validation."""

from __future__ import annotations

import pytest

from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.loader import SUPPORTED_VERSION
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.preflight.checks import run_target_checks
from privaci.schema.assume_existing import (
    AssumeExistingValidation,
    ColumnMismatch,
    raise_validation_failed,
    validate_assume_existing,
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
async def test_validate_assume_existing_happy_path(mocker: pytest.MockFixture) -> None:
    catalog = _users_catalog()
    config = Config(version=SUPPORTED_VERSION, schema_mode="assume_existing")
    fetch_catalog = mocker.patch(
        "privaci.schema.assume_existing.fetch_target_catalog_columns",
        new=mocker.AsyncMock(
            return_value={
                "public.users": [
                    ("id", "integer"),
                    ("email", "text"),
                    ("created_at", "timestamp without time zone"),
                ]
            }
        ),
    )

    result = await validate_assume_existing(mocker.Mock(), catalog, config)

    assert result.is_ok
    assert result.tables_checked == 1
    fetch_catalog.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_assume_existing_missing_table(
    mocker: pytest.MockFixture,
) -> None:
    catalog = _users_catalog()
    config = Config(version=SUPPORTED_VERSION, schema_mode="assume_existing")
    mocker.patch(
        "privaci.schema.assume_existing.fetch_target_catalog_columns",
        new=mocker.AsyncMock(return_value={}),
    )

    result = await validate_assume_existing(mocker.AsyncMock(), catalog, config)

    assert not result.is_ok
    assert result.mismatches[0].reason == "missing_table"
    with pytest.raises(PreflightError, match="missing table public.users"):
        raise_validation_failed(result)


@pytest.mark.asyncio
async def test_validate_assume_existing_type_mismatch(
    mocker: pytest.MockFixture,
) -> None:
    catalog = _users_catalog()
    config = Config(version=SUPPORTED_VERSION, schema_mode="assume_existing")
    mocker.patch(
        "privaci.schema.assume_existing.fetch_target_catalog_columns",
        new=mocker.AsyncMock(
            return_value={
                "public.users": [
                    ("id", "integer"),
                    ("email", "character varying(50)"),
                ]
            }
        ),
    )

    result = await validate_assume_existing(mocker.Mock(), catalog, config)

    assert not result.is_ok
    assert result.mismatches[0].reason == "type_mismatch"
    with pytest.raises(PreflightError, match="type mismatch"):
        raise_validation_failed(result)


@pytest.mark.asyncio
async def test_dry_run_assume_existing_preserves_validation_error(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    validation = AssumeExistingValidation(
        tables_checked=1,
        mismatches=(
            ColumnMismatch(
                table_id="public.users",
                column_name="email",
                source_type="text",
                target_type=None,
                reason="missing_column",
            ),
        ),
    )
    mocker.patch(
        "privaci.preflight.checks.validate_assume_existing",
        new=mocker.AsyncMock(return_value=validation),
    )

    # Act & Assert
    with pytest.raises(PreflightError, match="missing column public.users.email"):
        await run_target_checks(
            mocker.AsyncMock(),
            Config(version=SUPPORTED_VERSION, schema_mode="assume_existing"),
            _users_catalog(),
            dry_run=True,
            detection=None,
        )

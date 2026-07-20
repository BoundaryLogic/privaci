"""Unit tests for conditional masking capability and catalog checks."""

from __future__ import annotations

import pytest

from privaci.catalog.models import CatalogResult, ColumnInfo, LoadPlan, TableInfo
from privaci.config.actions import FakeAction
from privaci.config.conditional import (
    CONDITIONAL_MASKING_CAPABILITY,
    assert_require_binary_allows_when,
    validate_conditional_masking,
    validate_when_against_catalog,
)
from privaci.config.models import Config, TableConfig
from privaci.contracts.base import LicenseStatus
from privaci.errors import ConfigError, LicenseError, PreflightError


def _config_with_when(*, passthrough_copy: str = "auto") -> Config:
    return Config(
        version="1.0",
        passthrough_copy=passthrough_copy,  # type: ignore[arg-type]
        tables={
            "public.users": TableConfig(
                columns={
                    "notes": FakeAction(
                        action="fake",
                        provider="company",
                        when="status == 'closed'",
                    )
                }
            )
        },
    )


def _patch_validator(mocker: pytest.Mock, status: LicenseStatus) -> None:
    plugins = mocker.Mock()
    plugins.license_validator.validate.return_value = status
    mocker.patch("privaci.config.conditional.load_plugins", return_value=plugins)


def test_when_rejected_without_capability(mocker: pytest.Mock) -> None:
    # Arrange
    _patch_validator(
        mocker, LicenseStatus(tier="community", is_valid=True, capabilities=frozenset())
    )

    # Act / Assert
    with pytest.raises(LicenseError, match="conditional_masking"):
        validate_conditional_masking(_config_with_when())


def test_when_allowed_with_capability(mocker: pytest.Mock) -> None:
    # Arrange
    _patch_validator(
        mocker,
        LicenseStatus(
            tier="plugin",
            is_valid=True,
            capabilities=frozenset({CONDITIONAL_MASKING_CAPABILITY}),
        ),
    )

    # Act / Assert
    validate_conditional_masking(_config_with_when())


def test_require_binary_rejects_when() -> None:
    # Arrange / Act / Assert
    with pytest.raises(PreflightError, match="when:"):
        assert_require_binary_allows_when(
            _config_with_when(passthrough_copy="require_binary")
        )


def test_catalog_typecheck_rejects_jsonb_reference(mocker: pytest.Mock) -> None:
    # Arrange
    _patch_validator(
        mocker,
        LicenseStatus(
            tier="plugin",
            is_valid=True,
            capabilities=frozenset({CONDITIONAL_MASKING_CAPABILITY}),
        ),
    )
    config = Config(
        version="1.0",
        tables={
            "public.users": TableConfig(
                columns={
                    "notes": FakeAction(
                        action="fake",
                        provider="company",
                        when="payload != null",
                    )
                }
            )
        },
    )
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="notes", data_type="text", not_null=False),
            ColumnInfo(name="payload", data_type="jsonb", not_null=False),
        ),
    )
    catalog = CatalogResult(
        tables={"public.users": table},
        load_plan=LoadPlan(layers=(("public.users",),)),
    )

    # Act / Assert
    with pytest.raises(ConfigError, match="unsupported"):
        validate_when_against_catalog(config, catalog)


def test_catalog_typecheck_rejects_unknown_column(mocker: pytest.Mock) -> None:
    # Arrange
    _patch_validator(
        mocker,
        LicenseStatus(
            tier="plugin",
            is_valid=True,
            capabilities=frozenset({CONDITIONAL_MASKING_CAPABILITY}),
        ),
    )
    config = Config(
        version="1.0",
        tables={
            "public.users": TableConfig(
                columns={
                    "notes": FakeAction(
                        action="fake",
                        provider="company",
                        when="unknown_field == 1",
                    )
                }
            )
        },
    )
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="notes", data_type="text", not_null=False),
            ColumnInfo(name="status", data_type="text", not_null=False),
        ),
    )
    catalog = CatalogResult(
        tables={"public.users": table},
        load_plan=LoadPlan(layers=(("public.users",),)),
    )

    # Act / Assert
    with pytest.raises(ConfigError, match="unknown column"):
        validate_when_against_catalog(config, catalog)


def test_catalog_typecheck_allows_literal_mentioning_jsonb_name(
    mocker: pytest.Mock,
) -> None:
    # Arrange
    _patch_validator(
        mocker,
        LicenseStatus(
            tier="plugin",
            is_valid=True,
            capabilities=frozenset({CONDITIONAL_MASKING_CAPABILITY}),
        ),
    )
    config = Config(
        version="1.0",
        tables={
            "public.users": TableConfig(
                columns={
                    "notes": FakeAction(
                        action="fake",
                        provider="company",
                        when="status == 'has payload inside'",
                    )
                }
            )
        },
    )
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="notes", data_type="text", not_null=False),
            ColumnInfo(name="status", data_type="text", not_null=False),
            ColumnInfo(name="payload", data_type="jsonb", not_null=False),
        ),
    )
    catalog = CatalogResult(
        tables={"public.users": table},
        load_plan=LoadPlan(layers=(("public.users",),)),
    )

    # Act / Assert — must not raise
    validate_when_against_catalog(config, catalog)

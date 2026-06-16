"""Tests for catalog-wide auto-detect scanning."""

from __future__ import annotations

import pytest

from privaci.autodetect import scan_catalog, uncovered_strict_columns
from privaci.autodetect.resolve import resolve_effective_table_config
from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.actions import FakeAction, PassthroughAction
from privaci.config.models import Config, TableConfig
from privaci.errors import ConfigError
from privaci.preflight.checks import verify_strict_autodetect
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION


def _table(
    schema: str,
    name: str,
    columns: tuple[ColumnInfo, ...],
) -> TableInfo:
    return TableInfo(schema_name=schema, table_name=name, columns=columns)


def _catalog(*tables: TableInfo) -> CatalogResult:
    table_map = {t.identifier: t for t in tables}
    return CatalogResult(
        tables=table_map,
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=tuple(table_map)),)),
    )


def test_email_column_gets_high_confidence_fake() -> None:
    # Arrange
    users = _table(
        "public",
        "users",
        (
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="email", data_type="text", not_null=True),
        ),
    )
    config = Config(version=SUPPORTED_CONFIG_VERSION)

    # Act
    result = scan_catalog(_catalog(users), config)
    finding = result.finding_for("public.users", "email")

    # Assert
    assert finding is not None
    assert finding.confidence == "high"
    assert finding.action is not None
    assert finding.action.action == "fake"


def test_config_passthrough_overrides_email() -> None:
    # Arrange
    users = _table(
        "public",
        "users",
        (ColumnInfo(name="email", data_type="text", not_null=True),),
    )
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        tables={
            "public.users": TableConfig(
                columns={"email": PassthroughAction(action="passthrough")}
            )
        },
    )

    # Act
    effective = resolve_effective_table_config(
        users, config, scan_catalog(_catalog(users), config)
    )

    # Assert
    assert effective.columns["email"].action == "passthrough"


def test_strict_mode_raises_on_uncovered_email() -> None:
    # Arrange
    users = _table(
        "public",
        "users",
        (ColumnInfo(name="email", data_type="text", not_null=True),),
    )
    config = Config(version=SUPPORTED_CONFIG_VERSION, strict_autodetect=True)
    detection = scan_catalog(_catalog(users), config)

    # Act & Assert
    with pytest.raises(ConfigError) as exc_info:
        verify_strict_autodetect(config, detection)
    assert exc_info.value.exit_code == 3
    assert "users.email" in str(exc_info.value)


def test_strict_mode_allows_explicit_passthrough() -> None:
    # Arrange
    users = _table(
        "public",
        "users",
        (ColumnInfo(name="email", data_type="text", not_null=True),),
    )
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        strict_autodetect=True,
        tables={
            "public.users": TableConfig(
                columns={"email": PassthroughAction(action="passthrough")}
            )
        },
    )
    detection = scan_catalog(_catalog(users), config)

    # Act
    verify_strict_autodetect(config, detection)

    # Assert
    assert uncovered_strict_columns(config, detection) == ()


def test_merge_adds_autodetected_fake_action() -> None:
    # Arrange
    users = _table(
        "public",
        "users",
        (
            ColumnInfo(name="email", data_type="text", not_null=True),
            ColumnInfo(name="id", data_type="integer", not_null=True),
        ),
    )
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        tables={
            "public.users": TableConfig(
                columns={"id": FakeAction(action="fake", provider="uuid")}
            )
        },
    )
    detection = scan_catalog(_catalog(users), config)

    # Act
    effective = resolve_effective_table_config(users, config, detection)

    # Assert
    assert effective.columns["email"].action == "fake"
    assert effective.columns["id"].action == "fake"

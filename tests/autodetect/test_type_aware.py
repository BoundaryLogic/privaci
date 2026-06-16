"""Tests for type-aware auto-detect action selection."""

from __future__ import annotations

from privaci.autodetect import scan_catalog
from privaci.autodetect.actions import action_for_column
from privaci.autodetect.patterns import BUILTIN_PATTERNS
from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.models import Config
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION


def _rule(rule_id: str) -> object:
    for rule in BUILTIN_PATTERNS:
        if rule.rule_id == rule_id:
            return rule
    raise AssertionError(f"no rule {rule_id}")


def test_token_uuid_becomes_fake_uuid_not_hash() -> None:
    # Arrange
    column = ColumnInfo(name="token", data_type="uuid", not_null=True)

    # Act
    action = action_for_column(_rule("token"), column)

    # Assert
    assert action is not None
    assert action.action == "fake"
    assert action.provider == "uuid"


def test_hash_on_bytea_is_skipped() -> None:
    # Arrange
    column = ColumnInfo(name="secret", data_type="bytea", not_null=True)

    # Act
    action = action_for_column(_rule("secret"), column)

    # Assert
    assert action is None


def test_email_provider_on_integer_is_skipped() -> None:
    # Arrange
    column = ColumnInfo(name="email", data_type="integer", not_null=True)

    # Act
    action = action_for_column(_rule("email"), column)

    # Assert
    assert action is None


def test_dob_on_date_column_is_fake_dob() -> None:
    # Arrange
    column = ColumnInfo(name="dob", data_type="date", not_null=True)

    # Act
    action = action_for_column(_rule("dob"), column)

    # Assert
    assert action is not None
    assert action.action == "fake"
    assert action.provider == "dob"


def test_scanner_marks_incompatible_column_low() -> None:
    # Arrange
    table = TableInfo(
        schema_name="auth",
        table_name="sessions",
        columns=(ColumnInfo(name="secret", data_type="bytea", not_null=True),),
    )
    catalog = CatalogResult(
        tables={table.identifier: table},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=(table.identifier,)),)),
    )
    config = Config(version=SUPPORTED_CONFIG_VERSION)

    # Act
    finding = scan_catalog(catalog, config).finding_for("auth.sessions", "secret")

    # Assert
    assert finding is not None
    assert finding.confidence == "low"
    assert finding.action is None

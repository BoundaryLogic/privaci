"""Tests for :class:`MaskingEngine`."""

from __future__ import annotations

import pytest

from privaci.catalog.models import ColumnInfo, IndexInfo, TableInfo, table_id
from privaci.config.actions import (
    AiRefineAction,
    FakeAction,
    HashAction,
    PassthroughAction,
)
from privaci.config.models import TableConfig
from privaci.errors import L3NotInstalledError
from privaci.mask.engine import MaskingEngine
from tests.fixtures.constants import TEST_SALT


def _users_table() -> TableInfo:
    return TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="email", data_type="text", not_null=True),
            ColumnInfo(name="notes", data_type="text", not_null=False),
        ),
        primary_key=("id",),
        unique_constraints=(("email",),),
        indexes=(
            IndexInfo(
                name="users_email_key",
                is_unique=True,
                definition=(
                    'CREATE UNIQUE INDEX "users_email_key" ' "ON public.users (email)"
                ),
                columns=("email",),
            ),
        ),
    )


def test_mask_row_applies_configured_columns_only() -> None:
    # Arrange
    table = _users_table()
    cfg = TableConfig(
        columns={
            "email": FakeAction(action="fake", provider="email"),
            "notes": PassthroughAction(action="passthrough"),
        }
    )
    engine = MaskingEngine(TEST_SALT, table_id("public", "users"), table, cfg)
    row = {"id": 1, "email": "user@acme.example", "notes": "hello"}

    # Act
    masked = engine.mask_row(row)

    # Assert
    assert masked["id"] == 1
    assert masked["notes"] == "hello"
    assert masked["email"] != row["email"]
    assert "@" in masked["email"]


def test_mask_row_without_column_config_passthrough() -> None:
    # Arrange
    table = _users_table()
    cfg = TableConfig(columns={"email": HashAction(action="hash")})
    engine = MaskingEngine(TEST_SALT, table.identifier, table, cfg)

    # Act
    masked = engine.mask_row({"id": 2, "email": "a@b.com", "notes": "x"})

    # Assert
    assert masked["notes"] == "x"
    assert masked["email"] != "a@b.com"


def test_mask_row_reraises_masking_failure() -> None:
    # Arrange — ai_refine raises L3NotInstalledError inside the cell masker.
    table = _users_table()
    cfg = TableConfig(
        columns={
            "email": AiRefineAction(
                action="ai_refine", provider="aws_bedrock", model="m"
            )
        }
    )
    engine = MaskingEngine(TEST_SALT, table.identifier, table, cfg)

    # Act / Assert — the engine logs a PII-safe preview and re-raises.
    with pytest.raises(L3NotInstalledError):
        engine.mask_row({"id": 1, "email": "user@acme.example", "notes": "x"})


def test_masking_engine_repr() -> None:
    # Arrange
    table = _users_table()
    engine = MaskingEngine(TEST_SALT, table.identifier, table, TableConfig())

    # Assert
    assert "public.users" in repr(engine)

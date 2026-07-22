"""Article I: masking path works with no network egress."""

from __future__ import annotations

import socket

import pytest

from privaci.catalog.models import ColumnInfo, IndexInfo, TableInfo, table_id
from privaci.config.actions import FakeAction
from privaci.config.models import TableConfig
from privaci.mask.column_masker import mask_column_value
from privaci.mask.engine import MaskingEngine
from tests.fixtures.constants import TEST_SALT


def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_connect(*_args: object, **_kwargs: object) -> None:
        raise OSError("network blocked for Article I offline test")

    def _fail_create_connection(*_args: object, **_kwargs: object) -> None:
        raise OSError("network blocked for Article I offline test")

    def _fail_getaddrinfo(*_args: object, **_kwargs: object) -> list[object]:
        raise OSError("DNS blocked for Article I offline test")

    monkeypatch.setattr(socket.socket, "connect", _fail_connect)
    monkeypatch.setattr(socket, "create_connection", _fail_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", _fail_getaddrinfo)


def test_mask_column_value_offline_with_blocked_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _block_network(monkeypatch)
    action = FakeAction(action="fake", provider="email")
    original = "user@acme.example"

    # Act
    masked = mask_column_value(
        original,
        action,
        salt=TEST_SALT,
        column_path="public.users.email",
        is_unique=False,
    )

    # Assert
    assert isinstance(masked, str)
    assert masked != original
    assert "@" in masked
    assert masked.split("@", 1)[1]


def test_masking_engine_offline_with_blocked_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _block_network(monkeypatch)
    table = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="email", data_type="text", not_null=True),
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
    cfg = TableConfig(columns={"email": FakeAction(action="fake", provider="email")})
    engine = MaskingEngine(TEST_SALT, table_id("public", "users"), table, cfg)
    row = {"id": 1, "email": "user@acme.example"}

    # Act
    masked = engine.mask_row(row)

    # Assert
    assert masked["id"] == 1
    assert masked["email"] != row["email"]
    assert "@" in masked["email"]

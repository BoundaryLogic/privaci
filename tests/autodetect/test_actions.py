"""Tests for type-aware auto-detect action selection."""

from __future__ import annotations

import pytest

from privaci.autodetect.actions import action_for_column
from privaci.autodetect.patterns import PatternRule
from privaci.catalog.models import ColumnInfo
from privaci.config.actions import FakeAction, HashAction, NerMaskAction, StaticAction


def test_hash_on_uuid_becomes_fake_uuid() -> None:
    # Arrange
    rule = PatternRule("id", "suffix", "_id", "uuid", "hash")
    column = ColumnInfo(name="user_id", data_type="uuid", not_null=True)

    # Act
    action = action_for_column(rule, column)

    # Assert
    assert isinstance(action, FakeAction)
    assert action.provider == "uuid"


def test_hash_on_integer_returns_none() -> None:
    # Arrange
    rule = PatternRule("id", "suffix", "_id", None, "hash")
    column = ColumnInfo(name="user_id", data_type="integer", not_null=True)

    # Act & Assert
    assert action_for_column(rule, column) is None


def test_static_on_non_text_returns_none() -> None:
    # Arrange
    rule = PatternRule("pw", "substring", "password", None, "static")
    column = ColumnInfo(name="password_hash", data_type="bytea", not_null=True)

    # Act & Assert
    assert action_for_column(rule, column) is None


def test_static_on_text_returns_static_action() -> None:
    # Arrange
    rule = PatternRule("pw", "substring", "password", None, "static")
    column = ColumnInfo(name="password", data_type="text", not_null=True)

    # Act
    action = action_for_column(rule, column)

    # Assert
    assert isinstance(action, StaticAction)


def test_ner_on_non_text_returns_none() -> None:
    # Arrange
    rule = PatternRule("notes", "substring", "notes", None, "ner_mask")
    column = ColumnInfo(name="notes", data_type="integer", not_null=False)

    # Act & Assert
    assert action_for_column(rule, column) is None


def test_ner_on_text_returns_ner_action() -> None:
    # Arrange
    rule = PatternRule("notes", "substring", "notes", None, "ner_mask")
    column = ColumnInfo(name="notes", data_type="text", not_null=False)

    # Act
    action = action_for_column(rule, column)

    # Assert
    assert isinstance(action, NerMaskAction)


def test_fake_without_provider_raises() -> None:
    # Arrange
    rule = PatternRule("bad", "exact", "x", None, "fake")
    column = ColumnInfo(name="x", data_type="text", not_null=True)

    # Act & Assert
    with pytest.raises(ValueError, match="missing provider"):
        action_for_column(rule, column)


def test_hash_on_text_returns_hash_action() -> None:
    # Arrange
    rule = PatternRule("token", "substring", "token", None, "hash")
    column = ColumnInfo(name="token", data_type="varchar(64)", not_null=True)

    # Act
    action = action_for_column(rule, column)

    # Assert
    assert isinstance(action, HashAction)

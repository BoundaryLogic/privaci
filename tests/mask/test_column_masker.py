"""Tests for per-column masking actions."""

from __future__ import annotations

import pytest

from privaci.config.actions import (
    AiRefineAction,
    FakeAction,
    HashAction,
    NerMaskAction,
    NullAction,
    PassthroughAction,
    RegexMaskAction,
    StaticAction,
)
from privaci.errors import L3NotInstalledError, MaskingError
from privaci.mask.column_masker import is_unique_column, mask_column_value
from tests.fixtures.constants import SSN_PATTERN, SSN_REPLACEMENT, TEST_SALT

_COLUMN_PATH = "public.users.email"


def test_is_unique_column_detects_pk_and_unique_groups() -> None:
    # Assert
    assert is_unique_column(
        "id",
        primary_key=("id",),
        unique_groups=(("email",),),
        unique_index_columns=(),
    )
    assert is_unique_column(
        "email",
        primary_key=(),
        unique_groups=(("email",),),
        unique_index_columns=(),
    )
    assert is_unique_column(
        "slug",
        primary_key=(),
        unique_groups=(),
        unique_index_columns=(("slug",),),
    )
    assert not is_unique_column(
        "bio",
        primary_key=(),
        unique_groups=(),
        unique_index_columns=(),
    )


@pytest.mark.parametrize(
    ("value", "action", "expected"),
    [
        (None, PassthroughAction(action="passthrough"), None),
        ("", PassthroughAction(action="passthrough"), ""),
        ("", NullAction(action="null"), None),
        ("", StaticAction(action="static", value="x"), "x"),
        ("keep", PassthroughAction(action="passthrough"), "keep"),
        ("secret", NullAction(action="null"), None),
        ("fixed", StaticAction(action="static", value="masked"), "masked"),
    ],
)
def test_mask_column_value_null_and_empty_handling(
    value: object, action: object, expected: object
) -> None:
    # Act
    result = mask_column_value(
        value,
        action,  # type: ignore[arg-type]
        salt=TEST_SALT,
        column_path=_COLUMN_PATH,
        is_unique=False,
    )

    # Assert
    assert result == expected


def test_hash_action_is_deterministic() -> None:
    # Arrange
    action = HashAction(action="hash")

    # Act
    first = mask_column_value(
        "secret",
        action,
        salt=TEST_SALT,
        column_path=_COLUMN_PATH,
        is_unique=False,
    )
    second = mask_column_value(
        "secret",
        action,
        salt=TEST_SALT,
        column_path=_COLUMN_PATH,
        is_unique=False,
    )

    # Assert
    assert first == second
    assert first != "secret"


def test_fake_action_masks_value() -> None:
    # Arrange
    action = FakeAction(action="fake", provider="email")

    # Act
    result = mask_column_value(
        "user@acme.example",
        action,
        salt=TEST_SALT,
        column_path=_COLUMN_PATH,
        is_unique=False,
    )

    # Assert
    assert result != "user@acme.example"
    assert "@" in result


def test_regex_mask_replaces_ssn_pattern() -> None:
    # Arrange
    action = RegexMaskAction(
        action="regex_mask",
        pattern=SSN_PATTERN,
        replace=SSN_REPLACEMENT,
    )

    # Act
    result = mask_column_value(
        "123-45-6789",
        action,
        salt=TEST_SALT,
        column_path="public.users.ssn",
        is_unique=False,
    )

    # Assert
    assert result == SSN_REPLACEMENT


def test_regex_mask_honours_flags() -> None:
    # Arrange
    action = RegexMaskAction(
        action="regex_mask",
        pattern="secret",
        replace="[redacted]",
        flags=["IGNORECASE"],
    )

    # Act
    result = mask_column_value(
        "SECRET data",
        action,
        salt=TEST_SALT,
        column_path=_COLUMN_PATH,
        is_unique=False,
    )

    # Assert
    assert result == "[redacted] data"


def test_ner_mask_passthrough_without_spacy(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    action = NerMaskAction(action="ner_mask")
    monkeypatch.setattr(
        "privaci.mask.column_masker.mask_entities_in_text",
        lambda text, **kwargs: text,
    )

    # Act — when NER is unavailable, text is returned unchanged.
    result = mask_column_value(
        "Alice met Bob.",
        action,
        salt=TEST_SALT,
        column_path="public.notes.body",
        is_unique=False,
    )

    # Assert
    assert result == "Alice met Bob."


def test_ner_mask_requires_text_column() -> None:
    # Arrange
    action = NerMaskAction(action="ner_mask")

    # Act / Assert
    with pytest.raises(MaskingError, match="ner_mask requires a text"):
        mask_column_value(
            42,
            action,
            salt=TEST_SALT,
            column_path=_COLUMN_PATH,
            is_unique=False,
        )


def test_regex_mask_requires_text_column() -> None:
    # Arrange
    action = RegexMaskAction(
        action="regex_mask",
        pattern="^x$",
        replace="y",
    )

    # Act / Assert
    with pytest.raises(MaskingError, match="regex_mask requires a text"):
        mask_column_value(
            42,
            action,
            salt=TEST_SALT,
            column_path=_COLUMN_PATH,
            is_unique=False,
        )


def test_ai_refine_raises_l3_not_installed() -> None:
    # Arrange
    action = AiRefineAction(
        action="ai_refine",
        provider="aws_bedrock",
        model="m",
    )

    # Act / Assert
    with pytest.raises(L3NotInstalledError):
        mask_column_value(
            "text",
            action,
            salt=TEST_SALT,
            column_path=_COLUMN_PATH,
            is_unique=False,
        )

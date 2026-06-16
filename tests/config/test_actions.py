"""Tests for column-action models."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from privaci.config.actions import (
    DEFAULT_NER_ENTITIES,
    AiRefineAction,
    ColumnAction,
    FakeAction,
    HashAction,
    NerMaskAction,
    NullAction,
    PassthroughAction,
    RegexMaskAction,
    StaticAction,
)
from tests.fixtures.constants import SSN_PATTERN, SSN_REPLACEMENT

_adapter: TypeAdapter[ColumnAction] = TypeAdapter(ColumnAction)


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        ({"action": "fake", "provider": "first_name"}, FakeAction),
        ({"action": "hash"}, HashAction),
        ({"action": "passthrough"}, PassthroughAction),
        ({"action": "null"}, NullAction),
        ({"action": "static", "value": "x"}, StaticAction),
        ({"action": "ner_mask"}, NerMaskAction),
        (
            {"action": "ai_refine", "provider": "aws_bedrock", "model": "m"},
            AiRefineAction,
        ),
        (
            {
                "action": "regex_mask",
                "pattern": SSN_PATTERN,
                "replace": SSN_REPLACEMENT,
            },
            RegexMaskAction,
        ),
    ],
)
def test_discriminator_selects_action_type(
    payload: dict[str, str], expected_type: type
) -> None:
    # Act
    action = _adapter.validate_python(payload)

    # Assert
    assert isinstance(action, expected_type)


def test_ner_mask_defaults_to_standard_entities() -> None:
    # Act
    action = NerMaskAction(action="ner_mask")

    # Assert
    assert action.entities == list(DEFAULT_NER_ENTITIES)


def test_fake_action_accepts_seed_alias() -> None:
    # Act
    action = FakeAction(action="fake", provider="email", seed_alias="user_email")

    # Assert
    assert action.seed_alias == "user_email"


def test_unknown_action_tag_is_rejected() -> None:
    # Act & Assert
    with pytest.raises(ValidationError):
        _adapter.validate_python({"action": "regex_mas"})


def test_extra_key_on_action_is_forbidden() -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="Extra inputs"):
        _adapter.validate_python({"action": "hash", "oops": 1})


def test_fake_action_requires_provider() -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="provider"):
        _adapter.validate_python({"action": "fake"})


def test_regex_mask_rejects_uncompilable_pattern() -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="invalid regex"):
        RegexMaskAction(action="regex_mask", pattern="(", replace="x")


def test_regex_mask_rejects_redos_prone_pattern() -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="catastrophic backtracking"):
        RegexMaskAction(action="regex_mask", pattern="(a+)+$", replace="x")


def test_regex_mask_rejects_unknown_flag() -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="unknown regex flag"):
        RegexMaskAction(action="regex_mask", pattern="a", replace="b", flags=["NOPE"])


def test_regex_mask_accepts_known_flag() -> None:
    # Act
    action = RegexMaskAction(
        action="regex_mask", pattern="a", replace="b", flags=["IGNORECASE"]
    )

    # Assert
    assert action.flags == ["IGNORECASE"]

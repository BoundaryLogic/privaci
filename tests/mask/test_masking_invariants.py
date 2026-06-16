"""Property-based invariants for the per-cell masking actions.

These assert guarantees that must hold for *every* input across the value
space: determinism, hash format, salt isolation, total-function robustness on
arbitrary (UTF-8 encodable) Unicode, and the None/empty-string contract. They
complement the faker-specific properties in ``test_faker_properties.py`` and the
end-to-end PII-leakage checks in the integration suite.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from privaci.config.actions import (
    ColumnAction,
    FakeAction,
    HashAction,
    NullAction,
    PassthroughAction,
    RegexMaskAction,
    StaticAction,
)
from privaci.errors import MaskingError
from privaci.mask.column_masker import mask_column_value
from privaci.mask.regex_safe import _REGEX_MASK_MAX_INPUT_LEN
from tests.fixtures.constants import TEST_SALT

_COLUMN_PATH = "public.users.email"
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_EMAIL_SHAPE = re.compile(r"\A[^@\s]+@[^@\s]+\Z")

# Only generate characters that round-trip through UTF-8 (PostgreSQL text is
# UTF-8; lone surrogates cannot occur in real column values and would raise in
# any str.encode path). This keeps the properties faithful to real inputs.
_SAFE_TEXT = st.text(st.characters(codec="utf-8"))

# Providers whose output is a pure function of (salt, column_path, value).
# ``dob`` is excluded (reads date.today()); ``password`` is a fixed constant.
_DETERMINISTIC_PROVIDERS = (
    "email",
    "full_name",
    "first_name",
    "last_name",
    "username",
    "phone",
    "ssn",
    "credit_card",
    "uuid",
    "ip_address",
    "city",
    "company",
    "country",
    "postcode",
    "street",
    "job_title",
    "address",
)


def _mask(value: Any, action: ColumnAction, *, salt: str = TEST_SALT) -> Any:
    return mask_column_value(
        value, action, salt=salt, column_path=_COLUMN_PATH, is_unique=False
    )


@pytest.mark.parametrize("provider", _DETERMINISTIC_PROVIDERS)
@settings(max_examples=40)
@given(value=_SAFE_TEXT.filter(lambda s: s != ""))
def test_fake_is_deterministic_for_every_provider(provider: str, value: str) -> None:
    # Arrange
    action = FakeAction(action="fake", provider=provider)

    # Act / Assert — same inputs must always yield the same fake value.
    assert _mask(value, action) == _mask(value, action)


@settings(max_examples=80)
@given(value=_SAFE_TEXT.filter(lambda s: s != ""))
def test_hash_is_lowercase_hex_and_never_echoes_input(value: str) -> None:
    # Arrange
    action = HashAction(action="hash")

    # Act
    result = _mask(value, action)

    # Assert — SHA-256 hexdigest shape, and the cleartext never survives.
    assert _HEX64.match(result) is not None
    assert result != value


@settings(max_examples=50)
@given(
    value=_SAFE_TEXT.filter(lambda s: s != ""), suffix=st.text(min_size=1, max_size=16)
)
def test_hash_is_salt_isolated(value: str, suffix: str) -> None:
    # Arrange — two distinct salts over the same value.
    action = HashAction(action="hash")

    # Act
    with_base = _mask(value, action, salt=TEST_SALT)
    with_rotated = _mask(value, action, salt=TEST_SALT + suffix)

    # Assert — rotating the salt re-keys the output.
    assert with_base != with_rotated


@settings(max_examples=80)
@given(value=_SAFE_TEXT)
def test_fake_and_hash_are_total_functions_over_unicode(value: str) -> None:
    # Act — arbitrary Unicode (incl. empty, control chars, emoji) must not raise.
    hashed = _mask(value, HashAction(action="hash"))
    faked = _mask(value, FakeAction(action="fake", provider="full_name"))

    # Assert
    assert isinstance(hashed, str)
    assert isinstance(faked, str)


@settings(max_examples=40)
@given(value=_SAFE_TEXT.filter(lambda s: s != ""))
def test_fake_email_keeps_email_structure(value: str) -> None:
    # Arrange
    action = FakeAction(action="fake", provider="email")

    # Act
    result = _mask(value, action)

    # Assert — values that normalize to empty return ""; all others look like email.
    assume(result != "")
    assert _EMAIL_SHAPE.match(result) is not None


@settings(max_examples=40)
@given(value=_SAFE_TEXT)
def test_regex_mask_is_deterministic(value: str) -> None:
    # Arrange
    action = RegexMaskAction(action="regex_mask", pattern=r"\d+", replace="#")

    # Act / Assert
    assert _mask(value, action) == _mask(value, action)


def test_regex_mask_rejects_oversized_input() -> None:
    # Arrange
    action = RegexMaskAction(action="regex_mask", pattern=r"\d", replace="#")
    oversized = "1" * (_REGEX_MASK_MAX_INPUT_LEN + 1)

    # Act / Assert
    with pytest.raises(MaskingError, match="exceeds"):
        _mask(oversized, action)


_ALL_ACTIONS: list[ColumnAction] = [
    FakeAction(action="fake", provider="email"),
    HashAction(action="hash"),
    PassthroughAction(action="passthrough"),
    NullAction(action="null"),
    StaticAction(action="static", value="X"),
    RegexMaskAction(action="regex_mask", pattern=r"\d", replace="#"),
]


@pytest.mark.parametrize("action", _ALL_ACTIONS, ids=lambda a: a.action)
def test_none_is_preserved_for_every_action(action: ColumnAction) -> None:
    # Act / Assert — NULL stays NULL regardless of action.
    assert _mask(None, action) is None


def test_empty_string_null_action_returns_none() -> None:
    # Act / Assert
    assert _mask("", NullAction(action="null")) is None


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (StaticAction(action="static", value="REDACTED"), "REDACTED"),
        (HashAction(action="hash"), ""),
        (FakeAction(action="fake", provider="email"), ""),
        (PassthroughAction(action="passthrough"), ""),
        (RegexMaskAction(action="regex_mask", pattern=r"\d", replace="#"), ""),
    ],
    ids=["static", "hash", "fake", "passthrough", "regex_mask"],
)
def test_empty_string_contract(action: ColumnAction, expected: str) -> None:
    # Act / Assert — only ``static`` substitutes; the rest preserve emptiness.
    assert _mask("", action) == expected

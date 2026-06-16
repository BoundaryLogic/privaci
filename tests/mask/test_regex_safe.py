"""Tests for bounded regex_mask substitution."""

from __future__ import annotations

import pytest

from privaci.errors import MaskingError
from privaci.mask.regex_safe import (
    _REGEX_MASK_MAX_INPUT_LEN,
    _compiled_pattern,
    reject_redos_prone_pattern,
    safe_regex_sub,
)


@pytest.mark.parametrize(
    "pattern",
    [
        "(a+)+$",
        "(a*)*",
        "(.*)*",
        "(a|a)*",
        "(a|ab)+",
        "(ab+){2,}",
    ],
)
def test_reject_redos_prone_pattern_rejects_backtracking_shapes(pattern: str) -> None:
    # Act / Assert
    with pytest.raises(ValueError, match="catastrophic"):
        reject_redos_prone_pattern(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        r"\d+",
        r"(\d{3})-(\d{4})",
        r"[A-Z]{2}\d+",
        r"(foo){2,5}",
        # Quantified groups with a *benign* body: these exercise the screen's
        # inner-body check (the group IS followed by an unbounded quantifier,
        # but the captured body has no nested quantifier/alternation).
        r"(abc)+",
        r"(ab){3,}",
    ],
)
def test_reject_redos_prone_pattern_allows_safe_patterns(pattern: str) -> None:
    # Act / Assert
    assert reject_redos_prone_pattern(pattern) == pattern


def test_safe_regex_sub_applies_pattern() -> None:
    # Act
    result = safe_regex_sub(r"\d+", "X", "abc123def")

    # Assert
    assert result == "abcXdef"


def test_safe_regex_sub_reuses_compiled_pattern() -> None:
    # Act
    first = safe_regex_sub(r"\d+", "X", "a1")
    second = safe_regex_sub(r"\d+", "X", "b2")

    # Assert
    assert first == "aX"
    assert second == "bX"


def test_regex_mask_input_cap_is_64_kib() -> None:
    # Pin the documented per-value cap (64 KiB). Using a literal here — rather
    # than the imported constant — keeps the boundary tests below honest if the
    # constant is ever changed by accident.
    assert _REGEX_MASK_MAX_INPUT_LEN == 64 * 1024


def test_safe_regex_sub_allows_input_at_exactly_max_length() -> None:
    # Arrange — the cap is inclusive: a value of exactly the limit is allowed.
    at_limit = "a" * _REGEX_MASK_MAX_INPUT_LEN

    # Act
    result = safe_regex_sub("a", "b", at_limit)

    # Assert — no MaskingError; every char substituted.
    assert result == "b" * _REGEX_MASK_MAX_INPUT_LEN


def test_safe_regex_sub_rejects_input_over_max_length() -> None:
    # Arrange — one past the inclusive cap.
    long_value = "a" * (_REGEX_MASK_MAX_INPUT_LEN + 1)

    # Act / Assert
    with pytest.raises(MaskingError, match="character limit"):
        safe_regex_sub("a", "b", long_value)


def test_compiled_pattern_is_cached_by_identity() -> None:
    # Act — same (pattern, flags) must return the *same* compiled object.
    first = _compiled_pattern(r"\d+", 0)
    second = _compiled_pattern(r"\d+", 0)

    # Assert — proves the LRU cache is in effect (kills decorator removal).
    assert first is second

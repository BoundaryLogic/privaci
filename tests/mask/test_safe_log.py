"""Tests for PII-safe debug previews."""

from __future__ import annotations

import pytest

from privaci.mask.safe_log import safe_value_preview


def test_safe_value_preview_does_not_leak_prefix() -> None:
    # Act
    preview = safe_value_preview("super-secret-value")

    # Assert
    assert preview.startswith("<SENSITIVE:")
    assert "super" not in preview
    assert "secret-value" not in preview


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "<NULL>"),
        ("", "<EMPTY>"),
    ],
)
def test_safe_value_preview_sentinels(value: object, expected: str) -> None:
    # Act / Assert
    assert safe_value_preview(value) == expected

"""Package metadata tests."""

from __future__ import annotations

from privaci import __version__


def test_version_is_semver_like() -> None:
    # Act
    parts = __version__.split(".")

    # Assert
    assert len(parts) >= 2

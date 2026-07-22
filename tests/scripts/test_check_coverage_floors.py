"""Tests for scripts/check_coverage_floors.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.scripts.conftest_helpers import load_scripts_module

_mod = load_scripts_module("check_coverage_floors", "check_coverage_floors.py")


def test_load_floors_accepts_canonical_globs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    floors = tmp_path / "floors.toml"
    floors.write_text(
        '[floors]\n"src/privaci/mask/*" = 96\n"src/privaci/config/*" = 98\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(_mod, "FLOORS_PATH", floors)

    # Act
    loaded = _mod._load_floors()

    # Assert
    assert loaded == {
        "src/privaci/mask/*": 96,
        "src/privaci/config/*": 98,
    }


def test_load_floors_rejects_directory_style_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    floors = tmp_path / "floors.toml"
    floors.write_text(
        '[floors]\n"src/privaci/mask/" = 96\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(_mod, "FLOORS_PATH", floors)

    # Act / Assert
    with pytest.raises(ValueError, match=r"must be a coverage include glob"):
        _mod._load_floors()


def test_load_floors_rejects_missing_star_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    floors = tmp_path / "floors.toml"
    floors.write_text(
        '[floors]\n"src/privaci/mask" = 96\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(_mod, "FLOORS_PATH", floors)

    # Act / Assert
    with pytest.raises(ValueError, match="must be a coverage include glob"):
        _mod._load_floors()

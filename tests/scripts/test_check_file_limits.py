"""Tests for scripts/check_file_limits.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.scripts.conftest_helpers import load_scripts_module, write_py

_lib = load_scripts_module("file_limit_lib", "file_limit_lib.py")


def test_collect_violations_flags_oversized_file(tmp_path: Path) -> None:
    # Arrange
    lines = "\n".join(f"x = {idx}" for idx in range(401))
    write_py(tmp_path, "src/privaci/mask/huge.py", f"{lines}\n")
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "file_limit_waivers.txt").write_text("", encoding="utf-8")

    # Act
    violations = _lib.collect_violations(tmp_path)

    # Assert
    assert any(v.kind == "file" for v in violations)


def test_collect_violations_flags_oversized_function(tmp_path: Path) -> None:
    # Arrange
    body = "def big():\n" + "".join(f"    _ = {idx}\n" for idx in range(41))
    write_py(tmp_path, "src/privaci/mask/big.py", body)
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "file_limit_waivers.txt").write_text("", encoding="utf-8")

    # Act
    violations = _lib.collect_violations(tmp_path)

    # Assert
    assert any(v.kind == "function" and v.name == "big" for v in violations)


def test_file_waiver_suppresses_violation(tmp_path: Path) -> None:
    # Arrange
    lines = "\n".join(f"x = {idx}" for idx in range(401))
    write_py(tmp_path, "src/privaci/cli/app.py", f"{lines}\n")
    waivers = tmp_path / "scripts" / "file_limit_waivers.txt"
    waivers.parent.mkdir(parents=True, exist_ok=True)
    waivers.write_text("src/privaci/cli/app.py # issue #100\n", encoding="utf-8")

    # Act
    violations = _lib.collect_violations(tmp_path)

    # Assert
    assert violations == []


def test_file_waiver_does_not_suppress_function_violations(tmp_path: Path) -> None:
    # Arrange — path-only waiver covers file size, not oversized functions.
    body = "def big():\n" + "".join(f"    _ = {idx}\n" for idx in range(41))
    write_py(tmp_path, "src/privaci/mask/mod.py", body)
    waivers = tmp_path / "scripts" / "file_limit_waivers.txt"
    waivers.parent.mkdir(parents=True, exist_ok=True)
    waivers.write_text("src/privaci/mask/mod.py # issue #100\n", encoding="utf-8")

    # Act
    violations = _lib.collect_violations(tmp_path)

    # Assert
    assert any(v.kind == "function" and v.name == "big" for v in violations)


def test_inline_waiver_suppresses_function_violation(tmp_path: Path) -> None:
    # Arrange
    body = (
        "# FILE_LIMIT_WAIVER: issue #42\n"
        + "def big():\n"
        + "".join(f"    _ = {idx}\n" for idx in range(41))
    )
    write_py(tmp_path, "src/privaci/mask/big.py", body)
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "file_limit_waivers.txt").write_text("", encoding="utf-8")

    # Act
    violations = _lib.collect_violations(tmp_path)

    # Assert
    assert violations == []


def test_spikes_package_is_excluded(tmp_path: Path) -> None:
    # Arrange
    lines = "\n".join(f"x = {idx}" for idx in range(401))
    write_py(tmp_path, "src/privaci/spikes/huge.py", f"{lines}\n")
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "file_limit_waivers.txt").write_text("", encoding="utf-8")

    # Act
    violations = _lib.collect_violations(tmp_path)

    # Assert
    assert violations == []


def test_invalid_waiver_file_raises(tmp_path: Path) -> None:
    # Arrange
    waivers = tmp_path / "scripts" / "file_limit_waivers.txt"
    waivers.parent.mkdir(parents=True, exist_ok=True)
    waivers.write_text("not-a-waiver\n", encoding="utf-8")
    write_py(tmp_path, "src/privaci/mask/ok.py", "x = 1\n")

    # Act / Assert
    with pytest.raises(ValueError, match="invalid allowlist/waiver"):
        _lib.collect_violations(tmp_path)

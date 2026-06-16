"""Tests for env:// and file:// backends."""

from __future__ import annotations

from pathlib import Path

import pytest

from privaci.errors import SecretError
from privaci.secrets.backends.constants import MAX_SECRET_FILE_BYTES
from privaci.secrets.backends.env import resolve_env_uri
from privaci.secrets.backends.file import resolve_file_uri
from privaci.secrets.parser import parse_secret_uri
from tests.fixtures.constants import TEST_SALT


def test_env_missing_variable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.delenv("ABSENT_VAR", raising=False)
    parsed = parse_secret_uri("env://ABSENT_VAR")

    # Act & Assert
    with pytest.raises(SecretError, match="not set"):
        resolve_env_uri(parsed)


def test_env_empty_variable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("EMPTY_VAR", "   ")
    parsed = parse_secret_uri("env://EMPTY_VAR")

    # Act & Assert
    with pytest.raises(SecretError, match="empty"):
        resolve_env_uri(parsed)


def test_file_relative_path_raises() -> None:
    # Arrange
    parsed = parse_secret_uri("file://relative/salt.txt")

    # Act & Assert
    with pytest.raises(SecretError, match="absolute"):
        resolve_file_uri(parsed)


def test_file_missing_raises(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "missing-salt"
    parsed = parse_secret_uri(f"file://{missing}")

    # Act & Assert
    with pytest.raises(SecretError, match="does not exist"):
        resolve_file_uri(parsed)


def test_file_empty_raises(tmp_path: Path) -> None:
    # Arrange
    salt_file = tmp_path / "empty"
    salt_file.write_text("\n", encoding="utf-8")
    parsed = parse_secret_uri(f"file://{salt_file}")

    # Act & Assert
    with pytest.raises(SecretError, match="empty"):
        resolve_file_uri(parsed)


def test_file_os_error_raises(
    tmp_path: Path,
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    salt_file = tmp_path / "salt"
    salt_file.write_text(TEST_SALT, encoding="utf-8")
    parsed = parse_secret_uri(f"file://{salt_file}")
    mocker.patch.object(Path, "read_text", side_effect=OSError("denied"))

    # Act & Assert
    with pytest.raises(SecretError, match="Cannot read"):
        resolve_file_uri(parsed)


def test_file_outside_allowed_root_raises(tmp_path: Path) -> None:
    # Arrange
    parsed = parse_secret_uri("file:///etc/passwd")

    # Act & Assert
    with pytest.raises(SecretError, match="outside allowed"):
        resolve_file_uri(parsed)


def test_file_symlink_raises(tmp_path: Path) -> None:
    # Arrange
    target = tmp_path / "real"
    target.write_text(TEST_SALT, encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(target)
    parsed = parse_secret_uri(f"file://{link}")

    # Act & Assert
    with pytest.raises(SecretError, match="Symlink"):
        resolve_file_uri(parsed)


def test_file_too_large_raises(tmp_path: Path) -> None:
    # Arrange
    big = tmp_path / "big"
    big.write_bytes(b"x" * (MAX_SECRET_FILE_BYTES + 1))
    parsed = parse_secret_uri(f"file://{big}")

    # Act & Assert
    with pytest.raises(SecretError, match="byte limit"):
        resolve_file_uri(parsed)


def test_file_reads_and_strips_newline(tmp_path: Path) -> None:
    # Arrange
    salt_file = tmp_path / "salt"
    salt_file.write_text(f"{TEST_SALT}\n\n", encoding="utf-8")
    parsed = parse_secret_uri(f"file://{salt_file}")

    # Act
    value = resolve_file_uri(parsed)

    # Assert
    assert value == TEST_SALT

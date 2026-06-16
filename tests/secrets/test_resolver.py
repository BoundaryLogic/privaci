"""Tests for boot-time secret resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from privaci.secrets import (
    SecretKind,
    SecretResolutionError,
    resolve_secret,
    validate_salt_length,
)
from privaci.secrets.types import SecretRedactionFilter, SecretStr
from tests.fixtures.constants import MIN_SALT_LENGTH, TEST_SALT


def test_resolve_env_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    monkeypatch.setenv("PRIVACI_TEST_SALT", TEST_SALT)

    # Act
    secret = resolve_secret("env://PRIVACI_TEST_SALT", kind=SecretKind.SALT)

    # Assert
    assert secret is not None
    assert secret.get_secret_value() == TEST_SALT


def test_resolve_file_uri(tmp_path: Path) -> None:
    # Arrange
    salt_file = tmp_path / "salt.txt"
    salt_file.write_text(f"{TEST_SALT}\n", encoding="utf-8")
    uri = f"file://{salt_file}"

    # Act
    secret = resolve_secret(uri, kind=SecretKind.SALT)

    # Assert
    assert secret is not None
    assert secret.get_secret_value() == TEST_SALT


def test_resolve_literal_postgres_url_registers_password() -> None:
    # Arrange
    import logging

    url = "postgresql://user:super-secret-password@localhost/db"
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="connect failed: super-secret-password",
        args=(),
        exc_info=None,
    )

    # Act
    secret = resolve_secret(url, kind=SecretKind.DB_URL)
    SecretRedactionFilter().filter(record)

    # Assert
    assert secret is not None
    assert secret.get_secret_value() == url
    assert "super-secret-password" not in record.msg
    assert "<redacted>" in record.msg


def test_optional_secret_returns_none_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("MISSING_OPTIONAL", raising=False)

    # Act
    result = resolve_secret("env://MISSING_OPTIONAL", required=False)

    # Assert
    assert result is None


def test_required_secret_raises_with_db_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("MISSING_DB", raising=False)

    # Act & Assert
    with pytest.raises(SecretResolutionError) as exc_info:
        resolve_secret("env://MISSING_DB", kind=SecretKind.DB_URL)
    assert exc_info.value.exit_code == 2


def test_required_salt_raises_with_exit_code_four(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("MISSING_SALT", raising=False)

    # Act & Assert
    with pytest.raises(SecretResolutionError) as exc_info:
        resolve_secret("env://MISSING_SALT", kind=SecretKind.SALT)
    assert exc_info.value.exit_code == 4


def test_validate_salt_length_rejects_short_value() -> None:
    # Arrange
    secret = SecretStr("short")

    # Act & Assert
    with pytest.raises(SecretResolutionError) as exc_info:
        validate_salt_length(secret)
    assert exc_info.value.exit_code == 4
    assert str(MIN_SALT_LENGTH) in str(exc_info.value)


def test_resolve_generic_secret_uses_exit_code_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("MISSING_GENERIC", raising=False)

    # Act & Assert
    with pytest.raises(SecretResolutionError) as exc_info:
        resolve_secret("env://MISSING_GENERIC", kind=SecretKind.GENERIC)
    assert exc_info.value.exit_code == 2


def test_redact_uri_literal() -> None:
    # Arrange
    from privaci.secrets.resolver import _redact_uri

    # Act & Assert
    assert _redact_uri("not-a-uri") == "<literal>"


def test_redact_uri_masks_credentials() -> None:
    # Arrange
    from privaci.secrets.resolver import _redact_uri

    # Act
    db = _redact_uri("postgresql://user:pass@host:5432/db")
    aws = _redact_uri("aws-sm://prod/secret")

    # Assert
    assert "pass" not in db
    assert db == "postgresql://user@host:5432/db"
    assert aws == "aws-sm://<redacted>"


def test_short_secret_is_scrubbed_from_logs() -> None:
    # Arrange
    import logging

    SecretRedactionFilter.clear_registered_secrets()
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="password dev leaked",
        args=(),
        exc_info=None,
    )

    # Act
    resolve_secret("postgresql://u:dev@localhost/db", kind=SecretKind.DB_URL)
    SecretRedactionFilter().filter(record)

    # Assert
    assert "dev" not in record.msg
    assert "<redacted>" in record.msg


def test_validate_salt_length_accepts_long_value() -> None:
    # Arrange
    secret = SecretStr(TEST_SALT)

    # Act & Assert
    validate_salt_length(secret)

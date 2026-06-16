"""Tests for secret URI parsing."""

from __future__ import annotations

import pytest

from privaci.errors import SecretError
from privaci.secrets.parser import SecretUriKind, parse_secret_uri


@pytest.mark.parametrize(
    ("raw", "kind", "secret_id"),
    [
        (
            "aws-sm://prod/db-creds?region=us-east-1&key=url",
            SecretUriKind.AWS_SM,
            "prod/db-creds",
        ),
        ("env://PRIVACI_SALT", SecretUriKind.ENV, ""),
        ("file:///run/secrets/salt", SecretUriKind.FILE, ""),
        (
            "azure-kv://acme-vault/privaci-salt?version=abc",
            SecretUriKind.AZURE_KV,
            "",
        ),
        (
            "vault://kv/data/staging-db#connection_url",
            SecretUriKind.VAULT,
            "",
        ),
    ],
)
def test_parse_secret_uri_known_schemes(
    raw: str,
    kind: SecretUriKind,
    secret_id: str,
) -> None:
    # Act
    parsed = parse_secret_uri(raw)

    # Assert
    assert parsed.kind == kind
    if secret_id:
        assert parsed.secret_id == secret_id


def test_parse_literal_without_scheme() -> None:
    # Act
    parsed = parse_secret_uri("plain-salt-value-thirty-two-chars-min!!")

    # Assert
    assert parsed.kind == SecretUriKind.LITERAL
    assert parsed.raw == "plain-salt-value-thirty-two-chars-min!!"


def test_parse_postgres_url_as_literal() -> None:
    # Arrange
    url = "postgresql://user:pass@localhost:5432/db"

    # Act
    parsed = parse_secret_uri(url)

    # Assert
    assert parsed.kind == SecretUriKind.LITERAL
    assert parsed.raw == url


def test_parse_empty_raises() -> None:
    # Act & Assert
    with pytest.raises(SecretError, match="empty"):
        parse_secret_uri("   ")


def test_parse_unknown_scheme_raises() -> None:
    # Act & Assert
    with pytest.raises(SecretError, match="Unsupported"):
        parse_secret_uri("unknown://value")


def test_parse_azure_kv_extracts_vault_and_secret() -> None:
    # Act
    parsed = parse_secret_uri("azure-kv://my-vault/my-secret")

    # Assert
    assert parsed.vault_name == "my-vault"
    assert parsed.secret_name == "my-secret"


def test_parse_vault_extracts_mount_and_key() -> None:
    # Act
    parsed = parse_secret_uri("vault://kv/data/staging#salt")

    # Assert
    assert parsed.mount_path == "kv/data/staging"
    assert parsed.field_key == "salt"


def test_parse_env_var_from_path_form() -> None:
    # Act
    parsed = parse_secret_uri("env:///FALLBACK_VAR")

    # Assert
    assert parsed.env_var == "FALLBACK_VAR"


def test_parse_aws_sm_without_secret_id_raises() -> None:
    # Act & Assert
    with pytest.raises(SecretError, match="secret id"):
        parse_secret_uri("aws-sm://")


def test_parse_vault_without_key_raises() -> None:
    # Act & Assert
    with pytest.raises(SecretError, match="field key"):
        parse_secret_uri("vault://kv/data/staging")


def test_parse_file_without_path_raises() -> None:
    # Act & Assert
    with pytest.raises(SecretError, match="file path"):
        parse_secret_uri("file://")


def test_parse_env_rejects_invalid_variable_name() -> None:
    # Act & Assert
    with pytest.raises(SecretError, match="not valid"):
        parse_secret_uri("env://9INVALID")


def test_parsed_secret_uri_repr_never_contains_raw_dsn() -> None:
    # Arrange
    raw = "postgresql://user:secret-pass@host.example/db"
    parsed = parse_secret_uri(raw)

    # Act
    text = repr(parsed)

    # Assert
    assert raw not in text
    assert "secret-pass" not in text
    assert "ParsedSecretUri" in text

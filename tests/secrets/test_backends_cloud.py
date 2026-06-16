"""Tests for cloud secret backends (mocked SDKs)."""

from __future__ import annotations

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from privaci.errors import SecretError
from privaci.secrets.backends.aws_sm import resolve_aws_sm_uri
from privaci.secrets.backends.azure_kv import resolve_azure_kv_uri
from privaci.secrets.backends.constants import CONNECT_TIMEOUT_S, READ_TIMEOUT_S
from privaci.secrets.backends.hashicorp import resolve_vault_uri
from privaci.secrets.parser import parse_secret_uri


def _install_boto3_mock(mocker: pytest.MockFixture) -> MagicMock:
    boto3 = MagicMock()
    botocore = ModuleType("botocore")
    botocore_exceptions = ModuleType("botocore.exceptions")
    botocore_exceptions.BotoCoreError = Exception
    botocore_exceptions.ClientError = Exception
    botocore.exceptions = botocore_exceptions  # type: ignore[attr-defined]
    botocore_config = ModuleType("botocore.config")

    class _BotoConfig:
        def __init__(
            self,
            *,
            connect_timeout: int | None = None,
            read_timeout: int | None = None,
        ) -> None:
            self.connect_timeout = connect_timeout
            self.read_timeout = read_timeout

    botocore_config.Config = _BotoConfig  # type: ignore[attr-defined]
    mocker.patch.dict(
        sys.modules,
        {
            "boto3": boto3,
            "botocore": botocore,
            "botocore.exceptions": botocore_exceptions,
            "botocore.config": botocore_config,
        },
    )
    return boto3


def test_aws_sm_resolves_plain_string(mocker: pytest.MockFixture) -> None:
    # Arrange
    boto3 = _install_boto3_mock(mocker)
    client = MagicMock()
    boto3.client.return_value = client
    client.get_secret_value.return_value = {"SecretString": "postgresql://localhost/db"}
    parsed = parse_secret_uri("aws-sm://prod/db?region=us-east-1")

    # Act
    value = resolve_aws_sm_uri(parsed)

    # Assert
    assert value == "postgresql://localhost/db"
    boto3.client.assert_called_once()
    call_kwargs = boto3.client.call_args.kwargs
    assert call_kwargs["region_name"] == "us-east-1"
    assert call_kwargs["config"] is not None
    client.close.assert_called_once()
    config = call_kwargs["config"]
    assert config.connect_timeout == CONNECT_TIMEOUT_S
    assert config.read_timeout == READ_TIMEOUT_S


def test_aws_sm_extracts_json_key(mocker: pytest.MockFixture) -> None:
    # Arrange
    boto3 = _install_boto3_mock(mocker)
    client = MagicMock()
    boto3.client.return_value = client
    payload = json.dumps({"connection_string": "postgresql://db"})
    client.get_secret_value.return_value = {"SecretString": payload}
    parsed = parse_secret_uri("aws-sm://id?key=connection_string&version=v1")

    # Act
    value = resolve_aws_sm_uri(parsed)

    # Assert
    assert value == "postgresql://db"
    client.get_secret_value.assert_called_once_with(SecretId="id", VersionId="v1")


def test_aws_sm_missing_boto3_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    parsed = parse_secret_uri("aws-sm://secret")
    mocker.patch.dict(sys.modules, {"boto3": None})

    # Act & Assert
    with pytest.raises(SecretError, match="boto3"):
        resolve_aws_sm_uri(parsed)


def test_aws_sm_api_error_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    boto3 = _install_boto3_mock(mocker)
    client = MagicMock()
    boto3.client.return_value = client
    from botocore.exceptions import ClientError

    client.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}},
        "GetSecretValue",
    )
    parsed = parse_secret_uri("aws-sm://missing")

    # Act & Assert
    with pytest.raises(SecretError, match="Failed to resolve"):
        resolve_aws_sm_uri(parsed)


def test_aws_sm_invalid_json_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    boto3 = _install_boto3_mock(mocker)
    client = MagicMock()
    boto3.client.return_value = client
    client.get_secret_value.return_value = {"SecretString": "not-json"}
    parsed = parse_secret_uri("aws-sm://id?key=connection_string")

    # Act & Assert
    with pytest.raises(SecretError, match="not valid JSON"):
        resolve_aws_sm_uri(parsed)


def test_azure_kv_resolves_secret(mocker: pytest.MockFixture) -> None:
    # Arrange
    azure_identity = ModuleType("azure.identity")
    credential = MagicMock()
    azure_identity.DefaultAzureCredential = MagicMock(return_value=credential)
    azure_kv = ModuleType("azure.keyvault.secrets")
    azure_kv.SecretClient = MagicMock()
    azure_core = ModuleType("azure.core")
    azure_core_exceptions = ModuleType("azure.core.exceptions")
    azure_core_exceptions.AzureError = Exception
    azure_core.exceptions = azure_core_exceptions  # type: ignore[attr-defined]
    mocker.patch.dict(
        sys.modules,
        {
            "azure.identity": azure_identity,
            "azure.keyvault.secrets": azure_kv,
            "azure.core.exceptions": azure_core_exceptions,
            "azure.core": azure_core,
        },
    )
    bundle = MagicMock()
    bundle.value = "a" * 32
    azure_kv.SecretClient.return_value.get_secret.return_value = bundle
    parsed = parse_secret_uri("azure-kv://vault/name?version=v2")

    # Act
    value = resolve_azure_kv_uri(parsed)

    # Assert
    assert len(value) == 32
    azure_kv.SecretClient.return_value.get_secret.assert_called_once_with(
        "name",
        version="v2",
    )
    credential.close.assert_called_once()
    client_kwargs = azure_kv.SecretClient.call_args.kwargs
    assert client_kwargs["connection_timeout"] == CONNECT_TIMEOUT_S
    assert client_kwargs["read_timeout"] == READ_TIMEOUT_S


def test_azure_kv_missing_sdk_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    mocker.patch.dict(sys.modules, {"azure.identity": None})
    parsed = parse_secret_uri("azure-kv://vault/name")

    # Act & Assert
    with pytest.raises(SecretError, match="azure-identity"):
        resolve_azure_kv_uri(parsed)


def test_vault_resolves_field(mocker: pytest.MockFixture) -> None:
    # Arrange
    hvac = ModuleType("hvac")
    hvac_exceptions = ModuleType("hvac.exceptions")
    hvac_exceptions.VaultError = Exception
    hvac.exceptions = hvac_exceptions  # type: ignore[attr-defined]
    client = MagicMock()
    client.is_authenticated.return_value = True
    client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"salt": "b" * 32}},
    }
    hvac.Client = MagicMock(return_value=client)
    mocker.patch.dict(sys.modules, {"hvac": hvac, "hvac.exceptions": hvac_exceptions})
    parsed = parse_secret_uri("vault://kv/data/app#salt")

    # Act
    value = resolve_vault_uri(parsed)

    # Assert
    assert value == "b" * 32
    hvac.Client.assert_called_once_with(timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S))


def test_vault_unauthenticated_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    hvac = ModuleType("hvac")
    hvac_exceptions = ModuleType("hvac.exceptions")
    hvac_exceptions.VaultError = Exception
    hvac.exceptions = hvac_exceptions  # type: ignore[attr-defined]
    client = MagicMock()
    client.is_authenticated.return_value = False
    hvac.Client = MagicMock(return_value=client)
    mocker.patch.dict(sys.modules, {"hvac": hvac, "hvac.exceptions": hvac_exceptions})
    parsed = parse_secret_uri("vault://kv/data/app#salt")

    # Act & Assert
    with pytest.raises(SecretError, match="authenticated"):
        resolve_vault_uri(parsed)


def test_aws_sm_missing_json_key_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    boto3 = _install_boto3_mock(mocker)
    client = MagicMock()
    boto3.client.return_value = client
    client.get_secret_value.return_value = {"SecretString": "{}"}
    parsed = parse_secret_uri("aws-sm://id?key=missing")

    # Act & Assert
    with pytest.raises(SecretError, match="not found"):
        resolve_aws_sm_uri(parsed)


def test_azure_kv_api_error_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    azure_identity = ModuleType("azure.identity")
    azure_identity.DefaultAzureCredential = MagicMock()
    azure_kv = ModuleType("azure.keyvault.secrets")
    azure_core_exceptions = ModuleType("azure.core.exceptions")

    class AzureError(Exception):
        pass

    azure_core_exceptions.AzureError = AzureError
    azure_kv.SecretClient = MagicMock()
    azure_kv.SecretClient.return_value.get_secret.side_effect = AzureError("fail")
    mocker.patch.dict(
        sys.modules,
        {
            "azure.identity": azure_identity,
            "azure.keyvault.secrets": azure_kv,
            "azure.core.exceptions": azure_core_exceptions,
        },
    )
    parsed = parse_secret_uri("azure-kv://vault/name")

    # Act & Assert
    with pytest.raises(SecretError, match="Failed to resolve"):
        resolve_azure_kv_uri(parsed)


def test_vault_missing_hvac_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    mocker.patch.dict(sys.modules, {"hvac": None})
    parsed = parse_secret_uri("vault://kv/data/app#salt")

    # Act & Assert
    with pytest.raises(SecretError, match="hvac"):
        resolve_vault_uri(parsed)


def test_vault_bad_mount_path_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    hvac = ModuleType("hvac")
    hvac_exceptions = ModuleType("hvac.exceptions")
    hvac_exceptions.VaultError = Exception
    hvac.exceptions = hvac_exceptions  # type: ignore[attr-defined]
    hvac.Client = MagicMock(return_value=MagicMock(is_authenticated=lambda: True))
    mocker.patch.dict(sys.modules, {"hvac": hvac, "hvac.exceptions": hvac_exceptions})
    parsed = parse_secret_uri("vault://onlysegment#salt")

    # Act & Assert
    with pytest.raises(SecretError, match="mount path"):
        resolve_vault_uri(parsed)


def test_vault_read_error_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    hvac = ModuleType("hvac")
    hvac_exceptions = ModuleType("hvac.exceptions")

    class VaultError(Exception):
        pass

    hvac_exceptions.VaultError = VaultError
    hvac.exceptions = hvac_exceptions  # type: ignore[attr-defined]
    client = MagicMock()
    client.is_authenticated.return_value = True
    client.secrets.kv.v2.read_secret_version.side_effect = VaultError("denied")
    hvac.Client = MagicMock(return_value=client)
    mocker.patch.dict(sys.modules, {"hvac": hvac, "hvac.exceptions": hvac_exceptions})
    parsed = parse_secret_uri("vault://kv/data/app#salt")

    # Act & Assert
    with pytest.raises(SecretError, match="Failed to resolve"):
        resolve_vault_uri(parsed)


def test_vault_empty_field_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    hvac = ModuleType("hvac")
    hvac_exceptions = ModuleType("hvac.exceptions")
    hvac_exceptions.VaultError = Exception
    hvac.exceptions = hvac_exceptions  # type: ignore[attr-defined]
    client = MagicMock()
    client.is_authenticated.return_value = True
    client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"salt": "  "}},
    }
    hvac.Client = MagicMock(return_value=client)
    mocker.patch.dict(sys.modules, {"hvac": hvac, "hvac.exceptions": hvac_exceptions})
    parsed = parse_secret_uri("vault://kv/data/app#salt")

    # Act & Assert
    with pytest.raises(SecretError, match="non-empty string"):
        resolve_vault_uri(parsed)


def test_vault_missing_field_raises(mocker: pytest.MockFixture) -> None:
    # Arrange
    hvac = ModuleType("hvac")
    hvac_exceptions = ModuleType("hvac.exceptions")
    hvac_exceptions.VaultError = Exception
    hvac.exceptions = hvac_exceptions  # type: ignore[attr-defined]
    client = MagicMock()
    client.is_authenticated.return_value = True
    client.secrets.kv.v2.read_secret_version.return_value = {"data": {"data": {}}}
    hvac.Client = MagicMock(return_value=client)
    mocker.patch.dict(sys.modules, {"hvac": hvac, "hvac.exceptions": hvac_exceptions})
    parsed = parse_secret_uri("vault://kv/data/app#salt")

    # Act & Assert
    with pytest.raises(SecretError, match="field not found"):
        resolve_vault_uri(parsed)

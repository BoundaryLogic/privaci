"""Resolve azure-kv:// secret URIs via Azure Key Vault."""

from __future__ import annotations

import logging
from typing import Any

from privaci.errors import SecretError
from privaci.secrets.backends.constants import CONNECT_TIMEOUT_S, READ_TIMEOUT_S
from privaci.secrets.parser import ParsedSecretUri

logger = logging.getLogger(__name__)


def resolve_azure_kv_uri(parsed: ParsedSecretUri) -> str:
    """Fetch a secret from Azure Key Vault.

    Args:
        parsed: Parsed azure-kv:// URI with optional version query param.

    Returns:
        The secret value.

    Raises:
        SecretError: If Azure SDKs are missing or the fetch fails.
    """
    credential, client = _create_kv_client(parsed)
    try:
        bundle = _fetch_kv_secret(client, parsed)
    finally:
        credential.close()
    return _validate_kv_value(parsed, bundle)


def _create_kv_client(parsed: ParsedSecretUri) -> tuple[Any, Any]:
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        msg = "azure-kv:// requires azure-identity and azure-keyvault-secrets"
        raise SecretError(msg) from exc

    vault_url = f"https://{parsed.vault_name}.vault.azure.net"
    credential = DefaultAzureCredential()
    client = SecretClient(
        vault_url=vault_url,
        credential=credential,
        connection_timeout=CONNECT_TIMEOUT_S,
        read_timeout=READ_TIMEOUT_S,
    )
    return credential, client


def _fetch_kv_secret(client: Any, parsed: ParsedSecretUri) -> Any:
    from azure.core.exceptions import AzureError

    version = parsed.query_dict().get("version")
    try:
        if version:
            return client.get_secret(parsed.secret_name, version=version)
        return client.get_secret(parsed.secret_name)
    except AzureError as exc:
        logger.error(
            "Azure Key Vault resolution failed",
            extra={
                "vault_name": parsed.vault_name,
                "secret_name": parsed.secret_name,
            },
        )
        msg = f"Failed to resolve azure-kv://{parsed.vault_name}/{parsed.secret_name}"
        raise SecretError(msg) from exc


def _validate_kv_value(parsed: ParsedSecretUri, bundle: Any) -> str:
    if not bundle.value or not bundle.value.strip():
        msg = (
            f"azure-kv://{parsed.vault_name}/{parsed.secret_name} returned empty value"
        )
        raise SecretError(msg)
    return str(bundle.value).strip()

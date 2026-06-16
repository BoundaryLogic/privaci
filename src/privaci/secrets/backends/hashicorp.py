"""Resolve vault:// secret URIs via HashiCorp Vault KV v2."""

from __future__ import annotations

import logging
from typing import Any

from privaci.errors import SecretError
from privaci.secrets.backends.constants import CONNECT_TIMEOUT_S, READ_TIMEOUT_S
from privaci.secrets.parser import ParsedSecretUri

logger = logging.getLogger(__name__)


def resolve_vault_uri(parsed: ParsedSecretUri) -> str:
    """Fetch a field from a HashiCorp Vault KV v2 secret.

    Args:
        parsed: Parsed vault:// URI (mount/path#field).

    Returns:
        The requested field value.

    Raises:
        SecretError: If hvac is missing or the read fails.
    """
    client = _create_vault_client()
    try:
        data = _read_vault_secret(client, parsed)
    finally:
        _close_vault_client(client)
    return _extract_vault_field(parsed, data)


def _create_vault_client() -> Any:
    try:
        import hvac
    except ImportError as exc:
        msg = "vault:// requires the hvac package"
        raise SecretError(msg) from exc

    client = hvac.Client(timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S))
    if not client.is_authenticated():
        msg = "vault:// requires an authenticated Vault client (VAULT_TOKEN, etc.)"
        raise SecretError(msg)
    return client


def _read_vault_secret(client: Any, parsed: ParsedSecretUri) -> dict[str, Any]:
    import hvac

    mount, _, path = parsed.mount_path.partition("/")
    if not mount or not path:
        msg = (
            "vault:// mount path must be mount/secret/path, "
            f"got {parsed.mount_path!r}"
        )
        raise SecretError(msg)
    try:
        response = client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point=mount,
        )
    except hvac.exceptions.VaultError as exc:
        logger.error(
            "HashiCorp Vault resolution failed",
            extra={
                "mount_path": parsed.mount_path,
                "field_key": parsed.field_key,
            },
        )
        msg = f"Failed to resolve vault://{parsed.mount_path}#{parsed.field_key}"
        raise SecretError(msg) from exc
    data: dict[str, Any] = response.get("data", {}).get("data", {})
    return data


def _close_vault_client(client: Any) -> None:
    adapter = getattr(client, "adapter", None)
    if adapter is not None and hasattr(adapter, "close"):
        adapter.close()


def _extract_vault_field(parsed: ParsedSecretUri, data: dict[str, Any]) -> str:
    if parsed.field_key not in data:
        msg = f"vault://{parsed.mount_path}#{parsed.field_key} field not found"
        raise SecretError(msg)
    value = data[parsed.field_key]
    if not isinstance(value, str) or not value.strip():
        msg = (
            f"vault://{parsed.mount_path}#{parsed.field_key} "
            "is not a non-empty string"
        )
        raise SecretError(msg)
    return value.strip()

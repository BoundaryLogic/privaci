"""Resolve and validate the pseudonym HMAC key for keyed masking actions."""

from __future__ import annotations

import os
import re

from privaci.config.keyed import config_uses_keyed_actions
from privaci.config.models import Config
from privaci.secrets import SecretKind, resolve_secret, validate_salt_length
from privaci.secrets.resolver import SecretResolutionError

_ENV_REF_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def resolve_run_pseudonym_key(config: Config) -> str | None:
    """Resolve ``pseudonym_key`` when keyed actions are configured.

    Returns:
        The resolved key, or ``None`` when no keyed actions are present.

    Raises:
        SecretResolutionError: When keyed actions are configured but the key is
            missing or shorter than 32 bytes.
    """
    if not config_uses_keyed_actions(config):
        return None
    raw = _raw_pseudonym_key_reference(config)
    if raw is None:
        raise SecretResolutionError(
            "Resolving pseudonym_key for keyed masking actions",
            exit_code=4,
            uri="<pseudonym_key>",
            cause="No pseudonym_key was configured in pseudonym_key or PSEUDONYM_KEY.",
            remediation=(
                "Set pseudonym_key in mask-rules.yaml or export PSEUDONYM_KEY "
                "(minimum 32 bytes)."
            ),
        )
    resolved = _expand_env_reference(str(raw).strip())
    secret = resolve_secret(resolved, required=True, kind=SecretKind.GENERIC)
    if secret is None:  # pragma: no cover - required=True
        raise SecretResolutionError(
            "Resolving pseudonym_key for keyed masking actions",
            exit_code=4,
            uri="<pseudonym_key>",
            cause="The pseudonym_key reference could not be resolved.",
            remediation="Verify pseudonym_key or PSEUDONYM_KEY.",
        )
    validate_salt_length(secret)
    return secret.get_secret_value()


def _raw_pseudonym_key_reference(config: Config) -> str | None:
    raw = (
        config.pseudonym_key.get_secret_value()
        if config.pseudonym_key is not None
        else None
    )
    if raw is None or not raw.strip():
        return os.environ.get("PSEUDONYM_KEY")
    return raw


def _expand_env_reference(raw: str) -> str:
    """Map ``${VAR}`` to ``env://VAR`` for the secrets resolver."""
    match = _ENV_REF_PATTERN.match(raw)
    if match is None:
        return raw
    return f"env://{match.group(1)}"

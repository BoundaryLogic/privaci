"""Resolve and validate the anonymization salt for a run."""

from __future__ import annotations

import os
import re

from privaci.config.models import Config
from privaci.secrets import SecretKind, resolve_secret, validate_salt_length
from privaci.secrets.resolver import SecretResolutionError

_ENV_REF_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def resolve_run_salt(config: Config) -> str:
    """Resolve the run salt from config and environment.

    Resolution order:
    1. ``config.global_salt`` when set (supports ``${ENV_VAR}`` and secret URIs).
    2. The ``ANONYMIZATION_SALT`` environment variable.

    Raises:
        SecretResolutionError: When no salt is configured or length is invalid.
    """
    raw = _raw_salt_reference(config)
    if raw is None:
        raise SecretResolutionError(
            "Resolving the anonymization salt",
            exit_code=4,
            uri="<salt>",
            cause="No salt was configured in global_salt or ANONYMIZATION_SALT.",
            remediation=(
                "Set global_salt in mask-rules.yaml or export ANONYMIZATION_SALT; "
                "generate one with `privaci gen-salt`."
            ),
        )
    resolved = _expand_env_reference(str(raw).strip())
    secret = resolve_secret(resolved, required=True, kind=SecretKind.SALT)
    if secret is None:  # pragma: no cover - required=True
        raise SecretResolutionError(
            "Resolving the anonymization salt",
            exit_code=4,
            uri="<salt>",
            cause="The salt reference could not be resolved.",
            remediation="Verify global_salt or ANONYMIZATION_SALT.",
        )
    validate_salt_length(secret)
    return secret.get_secret_value()


def _raw_salt_reference(config: Config) -> str | None:
    raw = (
        config.global_salt.get_secret_value()
        if config.global_salt is not None
        else None
    )
    if raw is None or not raw.strip():
        return os.environ.get("ANONYMIZATION_SALT")
    return raw


def _expand_env_reference(raw: str) -> str:
    """Map ``${VAR}`` to ``env://VAR`` for the secrets resolver."""
    match = _ENV_REF_PATTERN.match(raw)
    if match is None:
        return raw
    return f"env://{match.group(1)}"

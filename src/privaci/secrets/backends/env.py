"""Resolve env:// secret URIs."""

from __future__ import annotations

import os

from privaci.errors import SecretError
from privaci.secrets.parser import ParsedSecretUri


def resolve_env_uri(parsed: ParsedSecretUri) -> str:
    """Read a secret from an environment variable.

    Args:
        parsed: Parsed env:// URI.

    Returns:
        The environment variable value.

    Raises:
        SecretError: If the variable is unset or empty.
    """
    value = os.environ.get(parsed.env_var)
    if value is None:
        msg = f"Environment variable {parsed.env_var!r} is not set"
        raise SecretError(msg)
    if not value.strip():
        msg = f"Environment variable {parsed.env_var!r} is empty"
        raise SecretError(msg)
    return value.strip()

"""Secret types, URI resolution, and log redaction."""

from __future__ import annotations

from privaci.secrets.parser import ParsedSecretUri, SecretUriKind, parse_secret_uri
from privaci.secrets.resolver import (
    MIN_SALT_LENGTH,
    SecretKind,
    SecretResolutionError,
    resolve_secret,
    validate_salt_length,
)
from privaci.secrets.types import SecretRedactionFilter, SecretStr

__all__ = [
    "MIN_SALT_LENGTH",
    "ParsedSecretUri",
    "SecretKind",
    "SecretRedactionFilter",
    "SecretResolutionError",
    "SecretStr",
    "SecretUriKind",
    "parse_secret_uri",
    "resolve_secret",
    "validate_salt_length",
]

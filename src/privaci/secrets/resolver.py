"""Boot-time secret resolution and validation."""

from __future__ import annotations

import logging
from enum import Enum
from urllib.parse import urlparse, urlunparse

from privaci.errors import SecretError
from privaci.secrets.backends.aws_sm import resolve_aws_sm_uri
from privaci.secrets.backends.azure_kv import resolve_azure_kv_uri
from privaci.secrets.backends.env import resolve_env_uri
from privaci.secrets.backends.file import resolve_file_uri
from privaci.secrets.backends.hashicorp import resolve_vault_uri
from privaci.secrets.parser import ParsedSecretUri, SecretUriKind, parse_secret_uri
from privaci.secrets.types import SecretRedactionFilter, SecretStr

logger = logging.getLogger(__name__)

MIN_SALT_LENGTH = 32

# Derived once at import so the defensive _resolve_parsed terminal can reference
# it without running logic inside its (type-checker-unreachable) branch.
_SECRET_URI_KIND_NAMES = ", ".join(member.name for member in SecretUriKind)


class SecretKind(str, Enum):
    """Classifies a secret for exit-code and validation behavior."""

    DB_URL = "db_url"
    SALT = "salt"
    GENERIC = "generic"


class SecretResolutionError(SecretError):
    """Resolution failed for a required secret."""

    def __init__(
        self,
        message: str,
        *,
        exit_code: int,
        uri: str,
        cause: str | None = None,
        remediation: str | None = None,
    ) -> None:
        anchor = (
            "exit-code-4-missing-or-invalid-salt"
            if exit_code == 4
            else "exit-code-2-pre-flight-failure"
        )
        super().__init__(
            message,
            cause=cause,
            remediation=remediation,
            exit_code=exit_code,
            doc_anchor=anchor,
        )
        self.uri = uri


def resolve_secret(
    raw: str,
    *,
    required: bool = True,
    kind: SecretKind = SecretKind.GENERIC,
) -> SecretStr | None:
    """Resolve a secret reference once at boot.

    Args:
        raw: URI, postgres URL, or plain string.
        required: When False, log a warning and return None on failure.
        kind: Drives exit code on failure (DB URL → 2, salt → 4).

    Returns:
        Wrapped secret, or None when optional resolution fails.

    Raises:
        SecretResolutionError: When a required secret cannot be resolved.
        SecretError: When the URI format is invalid.
    """
    try:
        parsed = parse_secret_uri(raw)
        plaintext = _resolve_parsed(parsed)
    except SecretError as exc:
        return _handle_resolution_failure(raw, exc, required=required, kind=kind)

    secret = SecretStr(plaintext)
    register_secret_for_redaction(secret)
    return secret


def validate_salt_length(secret: SecretStr) -> None:
    """Ensure resolved salt meets minimum length.

    Args:
        secret: Resolved salt value.

    Raises:
        SecretResolutionError: When length is below MIN_SALT_LENGTH (exit 4).
    """
    value = secret.get_secret_value()
    length = len(value)
    if length < MIN_SALT_LENGTH:
        raise SecretResolutionError(
            "Validating the resolved anonymization salt",
            exit_code=4,
            uri="<salt>",
            cause=f"Resolved salt has length {length}, minimum is {MIN_SALT_LENGTH}.",
            remediation="Generate a new salt with `privaci gen-salt`.",
        )


def register_secret_for_redaction(secret: SecretStr) -> None:
    """Register resolved material and URL passwords for log redaction."""
    value = secret.get_secret_value()
    SecretRedactionFilter.register_secret(value)
    if value.startswith(("postgresql://", "postgres://")):
        _register_postgres_password(value)


def _handle_resolution_failure(
    raw: str,
    exc: SecretError,
    *,
    required: bool,
    kind: SecretKind,
) -> SecretStr | None:
    """Log or raise when secret resolution fails."""
    if not required:
        logger.warning(
            "Optional secret resolution failed",
            extra={"uri_scheme": _scheme_hint(raw), "error": str(exc)},
        )
        return None
    raise SecretResolutionError(
        f"Resolving {kind.value} secret from {_redact_uri(raw)}",
        exit_code=_exit_code_for_kind(kind),
        uri=_redact_uri(raw),
        cause=str(exc),
        remediation=(
            "Verify the secret URI scheme, the backing store, and the "
            "container's credentials. See docs/secrets.md for each scheme."
        ),
    ) from exc


def _resolve_parsed(parsed: ParsedSecretUri) -> str:
    kind = parsed.kind
    if kind == SecretUriKind.LITERAL:
        return parsed.raw
    elif kind == SecretUriKind.ENV:
        return resolve_env_uri(parsed)
    elif kind == SecretUriKind.FILE:
        return resolve_file_uri(parsed)
    elif kind == SecretUriKind.AWS_SM:
        return resolve_aws_sm_uri(parsed)
    elif kind == SecretUriKind.AZURE_KV:
        return resolve_azure_kv_uri(parsed)
    elif kind == SecretUriKind.VAULT:
        return resolve_vault_uri(parsed)
    # Exhaustive over SecretUriKind, so mypy proves this terminal unreachable;
    # the explicit raise keeps it from being an implicit None fall-through and
    # guards against a future enum value being added without a branch here.
    msg = (  # type: ignore[unreachable]
        f"Unknown secret URI kind: {kind!r}. "
        f"Expected one of: {_SECRET_URI_KIND_NAMES}. "
        "Check the secret URI format and parser output."
    )
    raise ValueError(msg)


def _register_postgres_password(url: str) -> None:
    parsed = urlparse(url)
    if parsed.password:
        SecretRedactionFilter.register_secret(parsed.password)


_EXIT_CODE_BY_KIND: dict[SecretKind, int] = {
    SecretKind.DB_URL: 2,
    SecretKind.SALT: 4,
    SecretKind.GENERIC: 2,
}


def _exit_code_for_kind(kind: SecretKind) -> int:
    # All SecretKind members are mapped explicitly; a missing entry (a future
    # kind added without updating this map) raises KeyError rather than silently
    # defaulting to a wrong exit code.
    return _EXIT_CODE_BY_KIND[kind]


def _scheme_hint(raw: str) -> str:
    if "://" not in raw:
        return "literal"
    return raw.split("://", maxsplit=1)[0]


def _redact_uri(raw: str) -> str:
    if "://" not in raw:
        return "<literal>"
    parsed = urlparse(raw.strip())
    if parsed.scheme in {"postgresql", "postgres"}:
        host = parsed.hostname or ""
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        if parsed.username:
            netloc = f"{parsed.username}@{host}" if host else parsed.username
        else:
            netloc = host
        return urlunparse(
            (
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )
    scheme = parsed.scheme
    return f"{scheme}://<redacted>"

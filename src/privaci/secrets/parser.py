"""URI parser for secret reference strings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

from privaci.errors import SecretError

_ENV_VAR_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_DB_SCHEMES = frozenset({"postgres", "postgresql"})
_SECRET_SCHEMES = frozenset(
    {"aws-sm", "azure-kv", "vault", "env", "file", *_DB_SCHEMES}
)


class SecretUriKind(str, Enum):
    """How a secret reference should be resolved."""

    LITERAL = "literal"
    AWS_SM = "aws-sm"
    AZURE_KV = "azure-kv"
    VAULT = "vault"
    ENV = "env"
    FILE = "file"


@dataclass(frozen=True, slots=True)
class ParsedSecretUri:
    """Normalized secret URI components."""

    kind: SecretUriKind
    raw: str
    secret_id: str = ""
    vault_name: str = ""
    secret_name: str = ""
    mount_path: str = ""
    field_key: str = ""
    env_var: str = ""
    file_path: str = ""
    query: tuple[tuple[str, str], ...] = ()

    def query_dict(self) -> dict[str, str]:
        """Return query parameters as a single-value dict."""
        return dict(self.query)

    def __repr__(self) -> str:
        """Never expose the raw URI (may embed passwords or secret paths)."""
        return (
            f"ParsedSecretUri(kind={self.kind!r}, secret_id={self.secret_id!r}, "
            f"vault_name={self.vault_name!r}, secret_name={self.secret_name!r}, "
            f"mount_path={self.mount_path!r}, field_key={self.field_key!r}, "
            f"env_var={self.env_var!r}, file_path={self.file_path!r})"
        )


def parse_secret_uri(value: str) -> ParsedSecretUri:
    """Parse a secret reference string into a normalized structure.

    Args:
        value: Raw config or environment value (URI or plain string).

    Returns:
        Parsed URI metadata for dispatch to a backend resolver.

    Raises:
        SecretError: If the URI scheme is unknown or malformed.
    """
    stripped = value.strip()
    if not stripped:
        msg = "Secret reference cannot be empty"
        raise SecretError(msg)

    if "://" not in stripped:
        return ParsedSecretUri(kind=SecretUriKind.LITERAL, raw=stripped)

    parsed = urlparse(stripped)
    scheme = parsed.scheme.lower()
    if scheme not in _SECRET_SCHEMES:
        msg = f"Unsupported secret URI scheme: {scheme!r}"
        raise SecretError(msg)

    if scheme in _DB_SCHEMES:
        return ParsedSecretUri(kind=SecretUriKind.LITERAL, raw=stripped)

    query_pairs = _flatten_query(parse_qs(parsed.query))
    return _parse_scheme(scheme, stripped, parsed, query_pairs)


def _parse_scheme(
    scheme: str,
    raw: str,
    parsed: ParseResult,
    query_pairs: tuple[tuple[str, str], ...],
) -> ParsedSecretUri:
    """Dispatch a validated scheme to its parser helper."""
    if scheme == "aws-sm":
        return _parse_aws_sm(raw, parsed, query_pairs)
    if scheme == "azure-kv":
        return _parse_azure_kv(raw, parsed, query_pairs)
    if scheme == "vault":
        return _parse_vault(raw, parsed, query_pairs)
    if scheme == "env":
        return _parse_env(raw, parsed)
    if scheme == "file":
        return _parse_file(raw, parsed)
    msg = f"Unsupported secret URI scheme: {scheme!r}"
    raise SecretError(msg)


def _flatten_query(query: dict[str, list[str]]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for key, values in sorted(query.items()):
        if values:
            pairs.append((key, values[-1]))
    return tuple(pairs)


def _parse_aws_sm(
    raw: str,
    parsed: ParseResult,
    query: tuple[tuple[str, str], ...],
) -> ParsedSecretUri:
    secret_id = _join_netloc_path(parsed)
    if not secret_id:
        msg = "aws-sm:// URI requires a secret id"
        raise SecretError(msg)
    return ParsedSecretUri(
        kind=SecretUriKind.AWS_SM,
        raw=raw,
        secret_id=secret_id,
        query=query,
    )


def _parse_azure_kv(
    raw: str,
    parsed: ParseResult,
    query: tuple[tuple[str, str], ...],
) -> ParsedSecretUri:
    vault_name = unquote(parsed.netloc)
    secret_name = unquote(parsed.path.lstrip("/"))
    if not vault_name or not secret_name:
        msg = "azure-kv://<vault>/<secret> requires vault and secret name"
        raise SecretError(msg)
    return ParsedSecretUri(
        kind=SecretUriKind.AZURE_KV,
        raw=raw,
        vault_name=vault_name,
        secret_name=secret_name,
        query=query,
    )


def _parse_vault(
    raw: str,
    parsed: ParseResult,
    query: tuple[tuple[str, str], ...],
) -> ParsedSecretUri:
    mount_path = _join_netloc_path(parsed)
    field_key = unquote(parsed.fragment or "")
    if not mount_path or not field_key:
        msg = "vault://<mount>/<path>#<key> requires mount path and field key"
        raise SecretError(msg)
    return ParsedSecretUri(
        kind=SecretUriKind.VAULT,
        raw=raw,
        mount_path=mount_path,
        field_key=field_key,
        query=query,
    )


def _parse_env(raw: str, parsed: ParseResult) -> ParsedSecretUri:
    env_var = unquote(parsed.netloc or parsed.path.lstrip("/"))
    if not env_var:
        msg = "env://<VAR_NAME> requires a variable name"
        raise SecretError(msg)
    if not _ENV_VAR_PATTERN.fullmatch(env_var):
        raise SecretError(
            "Parsing env:// secret URI",
            cause=f"Environment variable name {env_var!r} is not valid.",
            remediation="Use names matching ^[A-Za-z_][A-Za-z0-9_]*$.",
        )
    return ParsedSecretUri(kind=SecretUriKind.ENV, raw=raw, env_var=env_var)


def _parse_file(raw: str, parsed: ParseResult) -> ParsedSecretUri:
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        file_path = unquote(f"{parsed.netloc}{parsed.path}")
    else:
        file_path = unquote(parsed.path)
    if not file_path:
        msg = "file://<absolute-path> requires a file path"
        raise SecretError(msg)
    return ParsedSecretUri(kind=SecretUriKind.FILE, raw=raw, file_path=file_path)


def _join_netloc_path(parsed: ParseResult) -> str:
    netloc = unquote(parsed.netloc or "")
    path = unquote(parsed.path or "").lstrip("/")
    if netloc and path:
        return f"{netloc}/{path}"
    return netloc or path

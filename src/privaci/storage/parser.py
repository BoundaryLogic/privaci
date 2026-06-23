"""URI parser for object storage destinations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

from privaci.errors import StorageError

_OBJECT_SCHEMES = frozenset({"file", "s3", "azure-blob"})


class ObjectUriKind(str, Enum):
    """Classification of an object destination URI."""

    LOCAL = "local"
    FILE = "file"
    S3 = "s3"
    AZURE_BLOB = "azure-blob"


@dataclass(frozen=True, slots=True)
class ParsedObjectUri:
    """Normalized object URI components."""

    kind: ObjectUriKind
    raw: str
    path: str = ""
    bucket: str = ""
    key: str = ""
    account: str = ""
    container: str = ""
    blob: str = ""
    query: tuple[tuple[str, str], ...] = ()

    def query_dict(self) -> dict[str, str]:
        """Return query parameters as a single-value dict."""
        return dict(self.query)

    def __repr__(self) -> str:
        """Never expose full cloud paths in debug output."""
        return (
            "ParsedObjectUri("
            f"kind={self.kind!r}, bucket={self.bucket!r}, key=<redacted>)"
        )


def parse_object_uri(value: str) -> ParsedObjectUri:
    """Parse an object destination string.

    Args:
        value: Local path or URI (`file://`, `s3://`, `azure-blob://`).

    Returns:
        Parsed URI metadata for write dispatch.

    Raises:
        StorageError: If the URI scheme is unknown or malformed.
    """
    stripped = value.strip()
    if not stripped:
        msg = "Object destination cannot be empty"
        raise StorageError(msg)

    if "://" not in stripped:
        return ParsedObjectUri(kind=ObjectUriKind.LOCAL, raw=stripped, path=stripped)

    parsed = urlparse(stripped)
    scheme = parsed.scheme.lower()
    if scheme not in _OBJECT_SCHEMES:
        msg = f"Unsupported object URI scheme: {scheme!r}"
        raise StorageError(
            "Parsing object destination URI",
            cause=msg,
            remediation=(
                "Use a local path, file://, s3://, or azure-blob:// URI. "
                "See docs/object-output.md."
            ),
        )

    query_pairs = _flatten_query(parse_qs(parsed.query))
    if scheme == "file":
        return _parse_file(stripped, parsed)
    if scheme == "s3":
        return _parse_s3(stripped, parsed, query_pairs)
    return _parse_azure_blob(stripped, parsed, query_pairs)


def _flatten_query(query: dict[str, list[str]]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for key, values in sorted(query.items()):
        if values:
            pairs.append((key, values[-1]))
    return tuple(pairs)


def _parse_file(raw: str, parsed: ParseResult) -> ParsedObjectUri:
    if parsed.netloc and parsed.netloc not in {"", "localhost"}:
        file_path = unquote(f"{parsed.netloc}{parsed.path}")
    else:
        file_path = unquote(parsed.path)
    if not file_path:
        msg = "file://<path> requires a file path"
        raise StorageError(msg)
    return ParsedObjectUri(kind=ObjectUriKind.FILE, raw=raw, path=file_path)


def _parse_s3(
    raw: str,
    parsed: ParseResult,
    query: tuple[tuple[str, str], ...],
) -> ParsedObjectUri:
    bucket = unquote(parsed.netloc or "")
    key = unquote(parsed.path.lstrip("/"))
    if not bucket or not key:
        msg = "s3://<bucket>/<key> requires bucket and key"
        raise StorageError(msg)
    return ParsedObjectUri(
        kind=ObjectUriKind.S3,
        raw=raw,
        bucket=bucket,
        key=key,
        query=query,
    )


def _parse_azure_blob(
    raw: str,
    parsed: ParseResult,
    query: tuple[tuple[str, str], ...],
) -> ParsedObjectUri:
    account = unquote(parsed.netloc or "")
    parts = unquote(parsed.path.lstrip("/")).split("/", 1)
    if not account or len(parts) != 2 or not parts[0] or not parts[1]:
        msg = "azure-blob://<account>/<container>/<blob> requires all parts"
        raise StorageError(msg)
    container, blob = parts
    return ParsedObjectUri(
        kind=ObjectUriKind.AZURE_BLOB,
        raw=raw,
        account=account,
        container=container,
        blob=blob,
        query=query,
    )

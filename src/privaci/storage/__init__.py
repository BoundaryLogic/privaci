"""Object storage writers for CLI compliance artifacts."""

from __future__ import annotations

from privaci.storage.parser import ObjectUriKind, ParsedObjectUri, parse_object_uri

__all__ = [
    "ObjectUriKind",
    "ParsedObjectUri",
    "parse_object_uri",
    "redact_object_uri",
    "write_object",
]


def write_object(uri: str, data: bytes, *, content_type: str | None = None) -> None:
    """Write ``data`` to ``uri`` via the active ``ObjectWriter`` plugin."""
    from privaci.storage.writer import write_object as _write_object

    _write_object(uri, data, content_type=content_type)


def redact_object_uri(raw: str) -> str:
    """Return a URI safe for logs and operator error messages."""
    from privaci.storage.writer import redact_object_uri as _redact

    return _redact(raw)

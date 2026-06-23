"""Dispatch small-object writes to the registered ``ObjectWriter`` plugin."""

from __future__ import annotations

from urllib.parse import urlparse

from privaci.contracts.plugins import load_plugins


def write_object(
    uri: str,
    data: bytes,
    *,
    content_type: str | None = None,
) -> None:
    """Write ``data`` to ``uri`` via the active ``ObjectWriter`` plugin."""
    load_plugins().object_writer.write(uri, data, content_type=content_type)


def redact_object_uri(raw: str) -> str:
    """Return a URI safe for logs and operator error messages."""
    stripped = raw.strip()
    if "://" not in stripped:
        return "<local-path>"
    parsed = urlparse(stripped)
    scheme = parsed.scheme.lower()
    if scheme in {"s3", "azure-blob"}:
        return f"{scheme}://<redacted>"
    if scheme == "file":
        return "file://<redacted>"
    return f"{scheme}://<redacted>"

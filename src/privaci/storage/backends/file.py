"""Local filesystem object writes."""

from __future__ import annotations

from pathlib import Path

from privaci.storage.parser import ObjectUriKind, ParsedObjectUri


def write_local_object(parsed: ParsedObjectUri, data: bytes) -> Path:
    """Write bytes to a local or file:// destination.

    Args:
        parsed: Parsed local or file URI.
        data: Payload to persist.

    Returns:
        Resolved filesystem path written.

    Raises:
        ValueError: If ``parsed`` is not a local/file URI.
    """
    if parsed.kind not in {ObjectUriKind.LOCAL, ObjectUriKind.FILE}:
        msg = f"Expected local URI, got {parsed.kind.value}"
        raise ValueError(msg)
    path = Path(parsed.path if parsed.kind is ObjectUriKind.FILE else parsed.raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path

"""PII-safe value formatting for masking-layer logs."""

from __future__ import annotations

from privaci.observability.redact import redact_value


def safe_value_preview(value: object) -> str:
    """Return a non-reversible hint safe for DEBUG logs.

    At INFO and above, callers must not log cell values at all. This helper
    is for DEBUG-only traces inside the masking layer.

    Args:
        value: A cell value that may contain PII.

    Returns:
        A redacted marker string, never the full raw value.
    """
    if value is None:
        return "<NULL>"
    text = str(value)
    if not text:
        return "<EMPTY>"
    return f"<SENSITIVE:{redact_value(text)}>"

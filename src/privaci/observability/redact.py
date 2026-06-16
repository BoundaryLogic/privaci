"""PII redaction for structured event payloads.

The observability layer never emits raw column values. Fields are
**safe-by-default**: any string-like value is collapsed to a non-reversible
hint unless the field name is on the structural allowlist (counts, ids,
status codes, etc.). See ``observability/spec.md`` "PII redaction in events".
"""

from __future__ import annotations

import hashlib
from typing import Any

_REDACT_PREFIX = "***"
_REDACT_PEPPER = "privaci-observability-redact-v1"
_HASH_HEX_CHARS = 8

# Field names whose string values are structural metadata, never raw PII.
STRUCTURAL_FIELDS: frozenset[str] = frozenset(
    {
        "action",
        "cause",
        "code",
        "column_name",
        "commercial_layer_present",
        "config_hash",
        "detail",
        "duration_ms",
        "engine_version",
        "errors",
        "estimated_rows",
        "event",
        "kind",
        "level",
        "matched_pattern",
        "message",
        "object_name",
        "provider",
        "reason",
        "remediation",
        "rows_affected",
        "rows_processed",
        "run_id",
        "salt_fingerprint",
        "schema_name",
        "source_column_path",
        "source_db_hash",
        "status",
        "strategy",
        "table",
        "table_id",
        "table_name",
        "tables_created",
        "tables_processed",
        "uri_scheme",
    }
)


def redact_value(value: Any) -> str:
    """Return a non-reversible hint for a possibly-sensitive value.

    Uses the value length plus a salted hash prefix so short PII such as SSN
    fragments cannot be reconstructed from the log line.

    Args:
        value: Any value that may contain PII.

    Returns:
        ``"***"`` for empty/None input, otherwise ``***len=N:hhhhhhhh``.
    """
    if value is None:
        return _REDACT_PREFIX
    text = str(value)
    if not text:
        return _REDACT_PREFIX
    digest = hashlib.sha256(f"{_REDACT_PEPPER}:{text}".encode()).hexdigest()
    return f"{_REDACT_PREFIX}len={len(text)}:{digest[:_HASH_HEX_CHARS]}"


def _is_structural_field(key: str, value: Any) -> bool:
    """Return whether ``value`` may pass through without redaction."""
    if value is None or isinstance(value, bool | int | float):
        return True
    return key in STRUCTURAL_FIELDS


def redact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``fields`` with sensitive entries redacted.

    Structural fields (see :data:`STRUCTURAL_FIELDS`) and numeric/boolean
    values pass through unchanged. All other values are replaced with
    :func:`redact_value` hints.

    Args:
        fields: Event-specific fields supplied by the caller.

    Returns:
        A new mapping safe to emit on stdout.
    """
    return {
        key: val if _is_structural_field(key, val) else redact_value(val)
        for key, val in fields.items()
    }

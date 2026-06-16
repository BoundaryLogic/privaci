"""Coerce masked string values to native types for binary COPY.

Masking actions return strings, but ``copy_records_to_table`` uses asyncpg's
binary protocol, which requires Python values whose types match the destination
column (e.g. ``datetime.date`` for a ``date`` column). This module converts
masked strings back to the native types asyncpg expects, leaving already-native
passthrough values untouched.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from privaci.errors import MaskingError

_TRUE_LITERALS = frozenset({"t", "true", "y", "yes", "1", "on"})
_FALSE_LITERALS = frozenset({"f", "false", "n", "no", "0", "off"})


def _to_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _TRUE_LITERALS:
        return True
    if lowered in _FALSE_LITERALS:
        return False
    raise ValueError(f"not a boolean: {value!r}")


def _to_bytes(value: str) -> bytes:
    text = value[2:] if value.startswith("\\x") else value
    return bytes.fromhex(text)


_CONVERTERS: dict[str, Callable[[str], Any]] = {
    "date": dt.date.fromisoformat,
    "timestamp without time zone": dt.datetime.fromisoformat,
    "timestamp with time zone": dt.datetime.fromisoformat,
    "time without time zone": dt.time.fromisoformat,
    "time with time zone": dt.time.fromisoformat,
    "boolean": _to_bool,
    "smallint": int,
    "integer": int,
    "bigint": int,
    "numeric": Decimal,
    "decimal": Decimal,
    "real": float,
    "double precision": float,
    "uuid": uuid.UUID,
    "bytea": _to_bytes,
}


# Types asyncpg cannot encode on the binary COPY path (see tasks §12.8).
TEXT_FALLBACK_TYPES: frozenset[str] = frozenset({"ltree"})


def base_type(data_type: str) -> str:
    """Strip a type modifier suffix (e.g. ``numeric(10,2)``)."""
    head, _, _ = data_type.strip().lower().partition("(")
    return head.strip()


def table_needs_text_fallback(column_types: dict[str, str]) -> bool:
    """Return True when any column requires text-mode INSERT instead of binary COPY."""
    return any(
        base_type(data_type) in TEXT_FALLBACK_TYPES
        for data_type in column_types.values()
    )


def parse_text_cursor(raw: str, *, data_type: str) -> object:
    """Convert a stored text checkpoint cursor to a native PK value.

    Args:
        raw: Text persisted in ``last_pk_value``.
        data_type: The primary-key column ``format_type`` string.

    Returns:
        A Python value suitable for asyncpg comparison in resume queries.
    """
    kind = base_type(data_type)
    converter = _CONVERTERS.get(kind)
    if converter is not None:
        return converter(raw)
    return raw


def coerce_value(value: Any, data_type: str, *, column_path: str) -> Any:
    """Return ``value`` converted to the native type for ``data_type``.

    Non-string values (native passthrough) and types without a converter are
    returned unchanged.

    Args:
        value: The (possibly masked) cell value.
        data_type: The destination column's ``format_type`` string.
        column_path: ``schema.table.column`` for error context.

    Raises:
        MaskingError: When a masked string cannot be coerced to the column type.
    """
    if value is None or not isinstance(value, str):
        return value
    converter = _CONVERTERS.get(base_type(data_type))
    if converter is None:
        return value
    try:
        return converter(value)
    except (ValueError, InvalidOperation) as exc:
        raise MaskingError(
            "Encoding a masked value for the target column",
            cause=(
                f"Masked value for {column_path} is not a valid {data_type}; "
                "the chosen action is incompatible with the column type."
            ),
            remediation=(
                "Configure a type-compatible action in mask-rules.yaml for this "
                "column, or exclude it from auto-detect."
            ),
        ) from exc

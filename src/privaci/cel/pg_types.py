"""PostgreSQL → CEL type mapping for ``when:`` activations."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from celpy import celtypes

from privaci.errors import ConfigError

# Normalized (lower, no spaces) PG type names → CEL annotation class.
_PG_TO_CEL: dict[str, type] = {
    "boolean": celtypes.BoolType,
    "bool": celtypes.BoolType,
    "smallint": celtypes.IntType,
    "integer": celtypes.IntType,
    "bigint": celtypes.IntType,
    "int2": celtypes.IntType,
    "int4": celtypes.IntType,
    "int8": celtypes.IntType,
    "real": celtypes.DoubleType,
    "double precision": celtypes.DoubleType,
    "float4": celtypes.DoubleType,
    "float8": celtypes.DoubleType,
    "text": celtypes.StringType,
    "character varying": celtypes.StringType,
    "varchar": celtypes.StringType,
    "character": celtypes.StringType,
    "char": celtypes.StringType,
    "uuid": celtypes.StringType,
    "timestamp without time zone": celtypes.StringType,
    "timestamp with time zone": celtypes.StringType,
    "timestamptz": celtypes.StringType,
    "timestamp": celtypes.StringType,
    "date": celtypes.StringType,
    "time without time zone": celtypes.StringType,
    "time with time zone": celtypes.StringType,
    "time": celtypes.StringType,
    "bytea": celtypes.BytesType,
}


class CelBindingError(ConfigError):
    """Raised when a column type cannot be bound into a CEL activation."""

    default_doc_anchor = "exit-code-3-config-validation-failure"


def normalize_pg_type(data_type: str) -> str:
    """Return a lowercased PG type name without typmod suffixes."""
    base = data_type.strip().lower()
    if "(" in base:
        base = base.split("(", 1)[0].strip()
    return base


def cel_annotation_for_pg_type(data_type: str, *, column_path: str) -> type:
    """Return the celpy annotation type for a PostgreSQL column type.

    Raises:
        CelBindingError: When the type is unsupported for ``when:`` (D9).
    """
    key = normalize_pg_type(data_type)
    annotation = _PG_TO_CEL.get(key)
    if annotation is not None:
        return annotation
    raise CelBindingError(
        f"Type-checking CEL when for {column_path}",
        cause=(
            f"Column type {data_type!r} is not supported in when: expressions "
            "(jsonb, arrays, numeric, and composites are excluded in v1)."
        ),
        remediation=(
            "Reference only bool/int/float/text/uuid/timestamp/bytea columns, "
            "or remove the when: guard; see "
            "docs/configuration.md#conditional-masking-when."
        ),
    )


def wrap_cel_value(value: Any, annotation: type) -> Any:
    """Wrap a Python cell value as a celpy typed value (or ``None``)."""
    if value is None:
        return None
    if annotation is celtypes.BoolType:
        return celtypes.BoolType(bool(value))
    if annotation is celtypes.IntType:
        return celtypes.IntType(int(value))
    if annotation is celtypes.DoubleType:
        return celtypes.DoubleType(float(value))
    if annotation is celtypes.BytesType:
        if isinstance(value, memoryview):
            value = value.tobytes()
        return celtypes.BytesType(bytes(value))
    # StringType — coerce temporal / UUID / Decimal edge cases from drivers.
    if isinstance(value, datetime | date | time):
        return celtypes.StringType(value.isoformat())
    if isinstance(value, UUID):
        return celtypes.StringType(str(value))
    if isinstance(value, Decimal):
        return celtypes.StringType(str(value))
    return celtypes.StringType(str(value))

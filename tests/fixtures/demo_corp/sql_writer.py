"""Helpers for emitting deterministic SQL INSERT batches."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def sql_literal(value: Any) -> str:
    """Render a Python value as a Postgres SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float | Decimal):
        return str(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        return f"'{value.isoformat()}'::date"
    if isinstance(value, datetime):
        return f"'{value.isoformat()}'::timestamptz"
    if isinstance(value, UUID):
        return f"'{value}'::uuid"
    if isinstance(value, bytes):
        # standard_conforming_strings is on by default: a single backslash
        # gives Postgres the hex-format bytea literal '\xDEAD'::bytea.
        return f"'\\x{value.hex()}'::bytea"
    if isinstance(value, list):
        inner = ", ".join(sql_literal(item) for item in value)
        return f"ARRAY[{inner}]"
    text = str(value).replace("'", "''")
    return f"'{text}'"


def insert_sql(
    table: str,
    columns: list[str],
    rows: list[tuple[Any, ...]],
    *,
    batch_size: int = 500,
) -> str:
    """Build multi-row INSERT statements for ``table``."""
    if not rows:
        return f"-- no rows for {table}\n"
    col_list = ", ".join(columns)
    chunks: list[str] = [f"-- {table}: {len(rows)} row(s)"]
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        values = ",\n    ".join(
            "(" + ", ".join(sql_literal(cell) for cell in row) + ")" for row in batch
        )
        chunks.append(f"INSERT INTO {table} ({col_list}) VALUES\n    {values};")
    return "\n".join(chunks) + "\n"

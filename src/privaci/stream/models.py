"""Shared streaming state for masked table loads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from privaci.catalog.models import TableInfo
from privaci.observability import ProgressThrottle
from privaci.schema.sequences import sequence_columns


@dataclass
class StreamContext:
    """Mutable streaming state for one masked table."""

    columns: list[str]
    column_types: dict[str, str]
    qual: str
    use_text_fallback: bool
    override_identity: bool
    pk_column: str | None
    max_values: dict[str, int | None]
    progress: ProgressThrottle
    table_started_at: float
    row_filter: str | None = None


def single_pk_column(table: TableInfo) -> str | None:
    """Return the sole PK column name when the table has a single-column PK."""
    if len(table.primary_key) == 1:
        return table.primary_key[0]
    return None


def initial_max_values(table: TableInfo) -> dict[str, int | None]:
    """Build per-sequence max trackers for ``sync_table_sequences``."""
    return {column.name: None for column in sequence_columns(table)}


def requires_overriding_system_value(table: TableInfo) -> bool:
    """Return whether inserts must use ``OVERRIDING SYSTEM VALUE``."""
    return any(
        column.is_identity and column.identity_generation == "ALWAYS"
        for column in table.columns
    )


def update_max_values(
    max_values: dict[str, int | None],
    rows: list[Any],
) -> None:
    """Track the highest observed value per sequence-backed column."""
    if not max_values:
        return
    for row in rows:
        payload = dict(row)
        for column_name, current in max_values.items():
            value = payload.get(column_name)
            if value is None:
                continue
            numeric = int(value)
            if current is None or numeric > current:
                max_values[column_name] = numeric


def checkpoint_cursor(value: Any | None) -> str | None:
    """Serialize a cursor value for checkpoint storage."""
    if value is None:
        return None
    return str(value)

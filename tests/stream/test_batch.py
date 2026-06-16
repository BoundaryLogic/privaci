"""Tests for batch-size resolution."""

from __future__ import annotations

from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.config.models import DEFAULT_BATCH_SIZE
from privaci.stream.batch import resolve_batch_size


def _wide_table(column_count: int) -> TableInfo:
    columns = tuple(
        ColumnInfo(name=f"c{i}", data_type="text", not_null=False)
        for i in range(column_count)
    )
    return TableInfo(
        schema_name="public",
        table_name="wide",
        columns=columns,
        estimated_rows=1_000_000,
    )


def test_resolve_batch_size_uses_global_default() -> None:
    # Arrange
    table = _wide_table(4)

    # Act
    size = resolve_batch_size(
        table,
        global_batch_size=DEFAULT_BATCH_SIZE,
        per_table_batch_size=None,
    )

    # Assert
    assert size == DEFAULT_BATCH_SIZE


def test_resolve_batch_size_prefers_per_table_override() -> None:
    # Arrange
    table = _wide_table(4)

    # Act
    size = resolve_batch_size(
        table,
        global_batch_size=DEFAULT_BATCH_SIZE,
        per_table_batch_size=500,
    )

    # Assert
    assert size == 500


def test_resolve_batch_size_caps_by_estimated_row_width() -> None:
    # Arrange — very wide rows should force a smaller batch than requested.
    table = _wide_table(10_000)

    # Act
    size = resolve_batch_size(
        table,
        global_batch_size=DEFAULT_BATCH_SIZE,
        per_table_batch_size=None,
    )

    # Assert
    assert size < DEFAULT_BATCH_SIZE
    assert size >= 100


def test_resolve_batch_size_uses_avg_width_for_heavy_columns() -> None:
    # Arrange — a single huge column (e.g. JSONB/BYTEA) drives the row width via
    # avg_width, so a flat per-column guess would not catch the memory blow-up.
    heavy = TableInfo(
        schema_name="public",
        table_name="docs",
        columns=(
            ColumnInfo(
                name="payload",
                data_type="jsonb",
                not_null=False,
                avg_width=20 * 1024 * 1024,
            ),
        ),
        estimated_rows=1_000,
    )

    # Act
    size = resolve_batch_size(
        heavy,
        global_batch_size=DEFAULT_BATCH_SIZE,
        per_table_batch_size=None,
    )

    # Assert — ~20 MiB rows cap the batch near 256 MiB / 20 MiB ~= 12 rows,
    # floored at the minimum batch size.
    assert size == 100

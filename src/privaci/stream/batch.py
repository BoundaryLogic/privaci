"""Batch-size selection and auto-tuning."""

from __future__ import annotations

from privaci.catalog.models import TableInfo

_MAX_BATCH_BYTES = 256 * 1024 * 1024
_MIN_BATCH_SIZE = 100
_DEFAULT_COLUMN_WIDTH = 64
_EMPTY_TABLE_ROW_WIDTH = 256


def resolve_batch_size(
    table: TableInfo,
    *,
    global_batch_size: int,
    per_table_batch_size: int | None,
) -> int:
    """Return the batch row count for one table.

    Auto-tunes downward when estimated row width would exceed the 256 MiB cap.
    """
    requested = per_table_batch_size or global_batch_size
    row_width = _estimate_row_width(table)
    if row_width <= 0:
        return requested
    max_rows = max(_MIN_BATCH_SIZE, _MAX_BATCH_BYTES // row_width)
    return max(_MIN_BATCH_SIZE, min(requested, max_rows))


def _estimate_row_width(table: TableInfo) -> int:
    """Estimate bytes-per-row from per-column catalog width statistics.

    Sums ``pg_stats.avg_width`` per column where available, which captures wide
    ``TEXT``/``JSONB``/``BYTEA`` columns that a flat per-column guess would
    badly underestimate (risking OOM before the batch cap engages). Columns
    without stats fall back to a fixed per-column width.
    """
    if not table.columns:
        return _EMPTY_TABLE_ROW_WIDTH
    total = 0
    for column in table.columns:
        if column.avg_width is not None and column.avg_width > 0:
            total += int(column.avg_width)
        else:
            total += _DEFAULT_COLUMN_WIDTH
    return max(_DEFAULT_COLUMN_WIDTH, total)

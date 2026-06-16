"""Throttled ``table.progress`` emission.

Long-running tables can stream millions of rows; emitting a progress event per
batch would flood stdout. This throttle enforces the spec's "at most once every
2 seconds per table" rule while always allowing a final flush at table end.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from privaci.observability.events import Event, emit

_DEFAULT_INTERVAL_SECONDS = 2.0


class ProgressThrottle:
    """Rate-limit ``table.progress`` events for a single table.

    Attributes:
        schema_name: Source schema of the table being streamed.
        table_name: Source table name.
        estimated_rows: Best-effort row estimate for percent-complete, or None.
    """

    __slots__ = (
        "_clock",
        "_estimated_rows",
        "_interval",
        "_last_emit",
        "_schema_name",
        "_started_at",
        "_table_name",
    )

    def __init__(
        self,
        schema_name: str,
        table_name: str,
        *,
        estimated_rows: int | None,
        interval_seconds: float = _DEFAULT_INTERVAL_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._schema_name = schema_name
        self._table_name = table_name
        self._estimated_rows = estimated_rows
        self._interval = interval_seconds
        self._clock = clock if clock is not None else time.monotonic
        now = self._clock()
        self._started_at = now
        self._last_emit = now

    def maybe_emit(self, rows_processed: int) -> bool:
        """Emit a ``table.progress`` event if the throttle interval has elapsed.

        Args:
            rows_processed: Cumulative rows streamed so far for this table.

        Returns:
            True when an event was emitted, False when throttled.
        """
        now = self._clock()
        if now - self._last_emit < self._interval:
            return False
        self._last_emit = now
        self._emit(rows_processed, now)
        return True

    def _emit(self, rows_processed: int, now: float) -> None:
        elapsed = max(now - self._started_at, 1e-9)
        emit(
            Event.TABLE_PROGRESS,
            schema_name=self._schema_name,
            table_name=self._table_name,
            rows_processed=rows_processed,
            rows_per_sec=round(rows_processed / elapsed, 2),
            percent_complete=self._percent(rows_processed),
        )

    def _percent(self, rows_processed: int) -> float | None:
        if not self._estimated_rows or self._estimated_rows <= 0:
            return None
        ratio = rows_processed / self._estimated_rows
        return round(min(ratio, 1.0) * 100.0, 2)

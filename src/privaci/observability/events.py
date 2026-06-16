"""Defined event-type catalog and the structured emit helper.

These identifiers mirror ``observability/spec.md`` "Defined event-type catalog".
Emitting an event routes a single structured record through the standard
``logging`` pipeline, where :class:`~privaci.observability.jsonlog.JsonLinesFormatter`
renders it as one JSON object per line on stdout.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from privaci.observability.redact import redact_fields

_EVENT_LOGGER_NAME = "privaci.events"

# Reserved keys that the formatter populates; callers must not pass them as
# event fields to avoid clobbering the envelope.
_RESERVED_FIELDS: frozenset[str] = frozenset({"timestamp", "level", "event"})


class Event(StrEnum):
    """Canonical top-level event identifiers emitted to stdout.

    Adding a new identifier requires a matching amendment to
    ``observability/spec.md``.
    """

    RUN_START = "run.start"
    PREFLIGHT_OK = "preflight.ok"
    PREFLIGHT_FAIL = "preflight.fail"
    SCHEMA_CLONED = "schema.cloned"
    TABLE_START = "table.start"
    TABLE_PROGRESS = "table.progress"
    TABLE_END = "table.end"
    COLUMN_MASKED = "column.masked"
    CYCLE_BREAK = "cycle_break"
    POLYMORPHIC_FK_WARNING = "polymorphic_fk_warning"
    IMPLIED_FK_WARNING = "implied_fk_warning"
    SKIPPED_OBJECT = "skipped_object"
    NEW_TABLE = "new_table"
    BINARY_FALLBACK = "binary_fallback"
    WARNING = "warning"
    ERROR = "error"
    RUN_END = "run.end"


_LEVEL_BY_EVENT: dict[Event, int] = {
    Event.PREFLIGHT_FAIL: logging.ERROR,
    Event.POLYMORPHIC_FK_WARNING: logging.WARNING,
    Event.IMPLIED_FK_WARNING: logging.WARNING,
    Event.BINARY_FALLBACK: logging.WARNING,
    Event.WARNING: logging.WARNING,
    Event.ERROR: logging.ERROR,
}


def get_event_logger() -> logging.Logger:
    """Return the dedicated logger used for structured events."""
    return logging.getLogger(_EVENT_LOGGER_NAME)


def emit(
    event: Event,
    *,
    level: int | None = None,
    **fields: Any,
) -> None:
    """Emit one structured event through the logging pipeline.

    Value-bearing fields are redacted before the record is created, so raw PII
    never reaches a handler. Reserved envelope keys are dropped if supplied.

    Args:
        event: The canonical event identifier.
        level: Optional explicit log level; defaults to a per-event level
            (``INFO`` unless the event is a warning/error).
        **fields: Event-specific fields documented in ``observability/spec.md``.
    """
    resolved_level = (
        level if level is not None else _LEVEL_BY_EVENT.get(event, logging.INFO)
    )
    safe_fields = redact_fields(
        {key: val for key, val in fields.items() if key not in _RESERVED_FIELDS}
    )
    logger = get_event_logger()
    logger.log(
        resolved_level,
        event.value,
        extra={"event": event.value, "event_fields": safe_fields},
    )

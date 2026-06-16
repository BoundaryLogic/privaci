"""Tests for the event catalog and emit helper."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from privaci.observability.events import Event, emit, get_event_logger


@contextmanager
def _capture_events() -> Iterator[list[logging.LogRecord]]:
    """Attach a capturing handler to the event logger for the block."""
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = get_event_logger()
    handler = _Capture()
    previous_propagate = logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.propagate = previous_propagate


def test_emit_routes_structured_fields_through_event_logger() -> None:
    # Act
    with _capture_events() as records:
        emit(Event.TABLE_END, table_name="users", rows_processed=5)

    # Assert
    assert len(records) == 1
    assert records[0].event == "table.end"  # type: ignore[attr-defined]
    assert records[0].event_fields == {  # type: ignore[attr-defined]
        "table_name": "users",
        "rows_processed": 5,
    }


def test_emit_assigns_warning_level_for_fk_warning() -> None:
    # Act
    with _capture_events() as records:
        emit(Event.IMPLIED_FK_WARNING, source_column_path="public.users.org_email")

    # Assert
    assert records[0].levelno == logging.WARNING


def test_emit_assigns_info_level_for_lifecycle_event() -> None:
    # Act
    with _capture_events() as records:
        emit(Event.TABLE_START, table_name="users")

    # Assert
    assert records[0].levelno == logging.INFO


def test_emit_drops_reserved_envelope_keys() -> None:
    # Act: a caller-supplied ``timestamp`` must never override the envelope.
    with _capture_events() as records:
        emit(Event.WARNING, timestamp="spoofed", message="real")

    # Assert
    fields = records[0].event_fields  # type: ignore[attr-defined]
    assert "timestamp" not in fields
    assert fields["message"] == "real"

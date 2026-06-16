"""Tests for the JSON-lines formatter and logging configuration."""

from __future__ import annotations

import io
import json
import logging
import re
import uuid

import pytest

from privaci.observability import Event, configure_logging, emit
from privaci.observability.jsonlog import JsonLinesFormatter

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_ISO_MICROS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$")


@pytest.fixture
def captured_stream() -> io.StringIO:
    """Configure root logging to a captured stream and restore afterwards."""
    stream = io.StringIO()
    configure_logging("debug", stream=stream)
    return stream


def _lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


def test_formatter_renders_iso8601_microsecond_timestamp() -> None:
    # Arrange
    formatter = JsonLinesFormatter()
    record = logging.LogRecord(
        "privaci.events", logging.INFO, __file__, 1, "run.start", None, None
    )
    record.event = "run.start"

    # Act
    payload = json.loads(formatter.format(record))

    # Assert
    assert _ISO_MICROS_RE.match(str(payload["timestamp"]))


def test_emitted_event_is_valid_json_line(captured_stream: io.StringIO) -> None:
    # Act
    emit(Event.TABLE_START, schema_name="public", table_name="users", estimated_rows=10)

    # Assert
    lines = _lines(captured_stream)
    assert len(lines) == 1
    assert lines[0]["event"] == "table.start"
    assert lines[0]["level"] == "info"
    assert lines[0]["schema_name"] == "public"
    assert lines[0]["estimated_rows"] == 10


def test_run_id_promoted_to_top_level(captured_stream: io.StringIO) -> None:
    # Arrange
    run_id = uuid.uuid4()

    # Act
    emit(Event.RUN_START, run_id=run_id, engine_version="0.1.0")

    # Assert
    line = _lines(captured_stream)[0]
    assert line["run_id"] == str(run_id)


def test_plain_log_is_rendered_as_log_event(captured_stream: io.StringIO) -> None:
    # Act
    logging.getLogger("privaci.test").info("hello %s", "world")

    # Assert
    line = _lines(captured_stream)[0]
    assert line["event"] == "log"
    assert line["message"] == "hello world"


def test_no_ansi_escapes_in_output(captured_stream: io.StringIO) -> None:
    # Act
    emit(Event.WARNING, message="something happened")

    # Assert
    assert not _ANSI_RE.search(captured_stream.getvalue())


def test_value_bearing_fields_are_redacted(captured_stream: io.StringIO) -> None:
    # Act
    emit(Event.COLUMN_MASKED, table_name="users", value="john@acme.com")

    # Assert
    line = _lines(captured_stream)[0]
    assert str(line["value"]).startswith("***len=")
    assert "john" not in captured_stream.getvalue()
    assert "acme.com" not in captured_stream.getvalue()


def test_configure_logging_replaces_existing_handlers() -> None:
    # Arrange
    first = io.StringIO()
    second = io.StringIO()
    configure_logging("info", stream=first)

    # Act
    configure_logging("info", stream=second)
    logging.getLogger().info("after reconfigure")

    # Assert
    assert first.getvalue() == ""
    assert second.getvalue() != ""


def test_log_level_filters_debug_when_info() -> None:
    # Arrange
    stream = io.StringIO()
    configure_logging("info", stream=stream)

    # Act
    logging.getLogger("privaci.test").debug("trace detail")

    # Assert
    assert stream.getvalue() == ""

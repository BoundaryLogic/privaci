"""JSON-lines stdout formatter and logging configuration.

Renders every ``logging`` record as one complete JSON object per line on
stdout, with no ANSI color codes or non-JSON decoration (see
``observability/spec.md`` "JSON-lines stdout event protocol"). Records emitted
via :func:`privaci.observability.events.emit` carry a structured ``event_fields``
payload; ordinary log calls are rendered as ``{"event": "log", ...}``.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from typing import Any, TextIO

# Standard LogRecord attributes that are never treated as event fields.
_STANDARD_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
        "event",
        "event_fields",
    }
)

_DEFAULT_EVENT = "log"


class JsonLinesFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record serialized as a compact JSON object."""
        payload: dict[str, Any] = {
            "timestamp": _iso_timestamp(record.created),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", _DEFAULT_EVENT),
        }
        fields = _record_fields(record)
        run_id = fields.pop("run_id", None)
        if run_id is not None:
            payload["run_id"] = str(run_id)
        if payload["event"] == _DEFAULT_EVENT:
            payload["message"] = record.getMessage()
        payload.update(fields)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _iso_timestamp(created: float) -> str:
    """Return an ISO-8601 UTC timestamp with microsecond precision."""
    moment = dt.datetime.fromtimestamp(created, tz=dt.UTC)
    return moment.isoformat(timespec="microseconds")


def _record_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Extract event-specific fields from a record (emit or plain log)."""
    structured = getattr(record, "event_fields", None)
    if isinstance(structured, dict):
        return dict(structured)
    return {
        key: val
        for key, val in record.__dict__.items()
        if key not in _STANDARD_RECORD_ATTRS
    }


def configure_logging(
    level: str,
    *,
    stream: TextIO | None = None,
    extra_filters: list[logging.Filter] | None = None,
) -> None:
    """Install the JSON-lines handler on the root logger.

    Replaces any existing handlers so stdout carries exactly one JSON object per
    line. Idempotent across calls (handlers are reset each time).

    Args:
        level: One of ``debug``, ``info``, ``warning``, ``error`` (any case).
        stream: Target stream; defaults to ``sys.stdout``.
        extra_filters: Additional filters to attach (e.g. secret redaction).
    """
    numeric = _resolve_level(level)
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(JsonLinesFormatter())
    for filt in extra_filters or []:
        handler.addFilter(filt)
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(numeric)


def _resolve_level(level: str) -> int:
    """Map a level name to its numeric value, defaulting to ``INFO``."""
    numeric = logging.getLevelNamesMapping().get(level.upper())
    return numeric if numeric is not None else logging.INFO

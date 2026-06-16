"""Structured observability: JSON-lines events, redaction, and metrics.

Public surface:

- :class:`Event` and :func:`emit` for the canonical event catalog.
- :func:`configure_logging` to install the JSON-lines stdout handler.
- :class:`ProgressThrottle` for rate-limited ``table.progress`` events.
- :func:`start_metrics_server` for the optional Prometheus endpoint.
"""

from __future__ import annotations

from privaci.observability.events import Event, emit, get_event_logger
from privaci.observability.jsonlog import JsonLinesFormatter, configure_logging
from privaci.observability.metrics import MetricsHandles, start_metrics_server
from privaci.observability.progress import ProgressThrottle
from privaci.observability.redact import redact_fields, redact_value

__all__ = [
    "Event",
    "JsonLinesFormatter",
    "MetricsHandles",
    "ProgressThrottle",
    "configure_logging",
    "emit",
    "get_event_logger",
    "redact_fields",
    "redact_value",
    "start_metrics_server",
]

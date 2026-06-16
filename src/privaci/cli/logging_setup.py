"""CLI logging configuration."""

from __future__ import annotations

from privaci.observability import configure_logging
from privaci.secrets import SecretRedactionFilter

_VALID_LOG_LEVELS = frozenset({"debug", "info", "warning", "error"})


def configure_cli_logging(level: str) -> None:
    """Configure JSON-lines stdout logging with secret redaction."""
    normalized = level.lower()
    if normalized not in _VALID_LOG_LEVELS:
        normalized = "info"
    configure_logging(normalized, extra_filters=[SecretRedactionFilter()])

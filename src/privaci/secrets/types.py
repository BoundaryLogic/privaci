"""Secret value types and log redaction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class SecretStr:
    """Wraps a secret value; never exposes it via repr or str."""

    _value: str

    def get_secret_value(self) -> str:
        """Return the underlying secret for authorized use only."""
        return self._value

    def __repr__(self) -> str:
        return "<redacted>"

    def __str__(self) -> str:
        return "<redacted>"


class SecretRedactionFilter(logging.Filter):
    """Strip known secret values from log records."""

    _patterns: ClassVar[list[re.Pattern[str]]] = []

    @classmethod
    def register_secret(cls, value: str) -> None:
        """Register a secret string to redact from future log lines."""
        if not value:
            return
        cls._patterns.append(re.compile(re.escape(value)))

    @classmethod
    def clear_registered_secrets(cls) -> None:
        """Clear registered patterns (test isolation only)."""
        cls._patterns.clear()

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact registered secrets from the log message."""
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub("<redacted>", message)
        record.msg = message
        record.args = ()
        return True

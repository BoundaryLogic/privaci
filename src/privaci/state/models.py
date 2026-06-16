"""Typed enums and records for the ``_privaci`` state schema.

These mirror the columns documented in ``state-and-audit/spec.md``. Statuses
are modeled as string enums so they serialize directly into the ``text`` +
``CHECK`` columns used by the DDL (see :mod:`privaci.state.ddl`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RunStatus(StrEnum):
    """Lifecycle status of a single masking run."""

    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class CheckpointStatus(StrEnum):
    """Per-table progress status within a run."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class AuditLevel(StrEnum):
    """Severity of an audit-log entry."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EventType(StrEnum):
    """Known ``audit_log.event_type`` values.

    The column is ``text`` so commercial layers may add their own types; these
    cover the open-source engine's events.
    """

    COLUMN_MASKED = "column.masked"
    COLUMN_PASSED_THROUGH = "column.passed_through"
    COLUMN_PII_DETECTED = "column.pii_detected"
    CYCLE_BREAK = "cycle_break"
    POLYMORPHIC_FK_WARNING = "polymorphic_fk_warning"
    IMPLIED_FK_WARNING = "implied_fk_warning"
    BINARY_FALLBACK = "binary_fallback"
    STRICT_MODE_VIOLATION = "strict_mode_violation"
    NEW_TABLE = "new_table"
    SKIPPED_OBJECT = "skipped_object"


@dataclass(frozen=True, slots=True)
class RunIdentity:
    """Immutable identity fields that gate resumability.

    Attributes:
        config_hash: sha256 of the canonicalized config JSON.
        salt_fingerprint: sha256(salt)[:16]; never the salt itself.
        source_db_hash: sha256("<host>:<port>/<dbname>").
    """

    config_hash: str
    salt_fingerprint: str
    source_db_hash: str

    def __repr__(self) -> str:
        return (
            f"RunIdentity(config_hash={self.config_hash[:8]}…, "
            f"salt_fingerprint={self.salt_fingerprint[:8]}…, "
            f"source_db_hash={self.source_db_hash[:8]}…)"
        )

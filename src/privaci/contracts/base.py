"""Stable ABC contracts for the ``privaci.plugins`` plugin layer."""

from __future__ import annotations

import abc
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

CONTRACT_VERSION = "1.0"

CellPostProcessor = Callable[[str, str, Any], Any]
"""Optional ``(table_id, column_name, value) -> final_value`` hook."""


@dataclass(frozen=True, slots=True)
class LicenseStatus:
    """Result of a license validation check."""

    tier: str
    is_valid: bool
    source_db_limit: int | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class ColumnContext:
    """Metadata for a column being processed by an LLM connector."""

    schema_name: str
    table_name: str
    column_name: str


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Output of an LLM redaction call."""

    text: str
    entities_replaced: int = 0


@dataclass(frozen=True, slots=True)
class RunCompletionEvent:
    """Payload for post-run notifications."""

    run_id: UUID
    status: str
    rows_processed: int
    duration_ms: int


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Summary of schema drift between two catalog snapshots."""

    has_drift: bool
    findings: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RunEnhancements:
    """RunEnhancer plugin filters/transforms (subsetting, JSONB paths)."""

    row_filters: dict[str, str] = field(default_factory=dict)
    """Schema-qualified table id → SQL ``WHERE`` fragment (trusted operator SQL)."""
    cell_post_processor: CellPostProcessor | None = None
    """Optional per-cell transform after column masking (e.g. JSONB path rules)."""
    subset_active: bool = False
    """When true, tables without a row filter are skipped (not streamed)."""


class LicenseValidator(abc.ABC):
    """Validate license entitlement via the installed plugin."""

    @abc.abstractmethod
    def validate(self) -> LicenseStatus:
        """Return the current license status for this run."""


class UsageMeter(abc.ABC):
    """Report usage via the UsageMeter plugin contract."""

    @abc.abstractmethod
    def register_run(self, *, source_db_hash: str, run_id: UUID) -> None:
        """Called at run start."""

    @abc.abstractmethod
    def report_usage(self, *, source_db_hash: str, run_id: UUID) -> None:
        """Called periodically or at significant milestones."""

    @abc.abstractmethod
    def final_meter(self, *, source_db_hash: str, run_id: UUID) -> None:
        """Called at run end."""


class LLMConnector(abc.ABC):
    """Level 3 BYO-LLM connector."""

    @abc.abstractmethod
    def name(self) -> str:
        """Return the connector identifier."""

    @abc.abstractmethod
    def redact_entities(
        self,
        text: str,
        *,
        salt: str,
        context: ColumnContext,
    ) -> RedactionResult:
        """Replace PII entities in freeform text."""


class ReportRenderer(abc.ABC):
    """Render a compliance report for a completed run."""

    @abc.abstractmethod
    def render(self, run_id: UUID, *, output_format: str) -> bytes:
        """Return the report bytes for the given format (e.g. json, pdf)."""


class Notifier(abc.ABC):
    """Send run-completion notifications."""

    @abc.abstractmethod
    def notify(self, event: RunCompletionEvent) -> None:
        """Deliver the notification (Slack, webhook, etc.)."""


class DriftDetector(abc.ABC):
    """Compare catalog snapshots and detect schema drift."""

    @abc.abstractmethod
    def detect(
        self,
        previous_snapshot: dict[str, Any],
        current_snapshot: dict[str, Any],
    ) -> DriftReport:
        """Return drift findings between two snapshots."""


class RunEnhancer(abc.ABC):
    """Build commercial run enhancements (subsetting filters, JSONB transforms)."""

    @abc.abstractmethod
    def build_enhancements(
        self,
        catalog: Any,
    ) -> RunEnhancements:
        """Return row filters and cell hooks for one masking run.

        Args:
            catalog: :class:`~privaci.catalog.models.CatalogResult` for the source.
        """


class ObjectWriter(abc.ABC):
    """Write small compliance artifacts to local or cloud object URIs."""

    @abc.abstractmethod
    def write(
        self,
        uri: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> None:
        """Persist ``data`` at ``uri`` (local path, ``file://``, or cloud scheme)."""

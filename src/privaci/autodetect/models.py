"""Detection finding models for PII auto-detect."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from privaci.config.actions import ColumnAction

DetectionConfidence = Literal["high", "medium", "low"]
DetectionSource = Literal["autodetect", "config"]


@dataclass(frozen=True, slots=True)
class DetectionFinding:
    """Outcome of inspecting one column for PII.

    Attributes:
        table_id: Schema-qualified table identifier.
        column_name: Column under inspection.
        confidence: ``high`` auto-masks; ``medium`` flags review; ``low`` passthrough.
        reasons: Human-readable scoring explanation (never contains cell values).
        action: Proposed masking action, or ``None`` for passthrough.
        provider: Inferred fake provider name when applicable.
        matched_pattern: Pattern rule id that fired, if any.
        source: Whether YAML or auto-detect produced the effective action.
    """

    table_id: str
    column_name: str
    confidence: DetectionConfidence
    reasons: tuple[str, ...]
    action: ColumnAction | None = None
    provider: str | None = None
    matched_pattern: str | None = None
    source: DetectionSource = "autodetect"

    def __repr__(self) -> str:
        return (
            f"DetectionFinding({self.table_id}.{self.column_name!r}, "
            f"confidence={self.confidence!r})"
        )


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """All findings from one catalog scan."""

    findings: tuple[DetectionFinding, ...]

    def by_table(self, table_id: str) -> tuple[DetectionFinding, ...]:
        """Return findings for ``table_id`` in column order."""
        return tuple(f for f in self.findings if f.table_id == table_id)

    def finding_for(self, table_id: str, column_name: str) -> DetectionFinding | None:
        """Return the finding for one column, if present."""
        for finding in self.findings:
            if finding.table_id == table_id and finding.column_name == column_name:
                return finding
        return None

    def __repr__(self) -> str:
        return f"DetectionResult(findings={len(self.findings)})"

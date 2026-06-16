"""PII column auto-detection."""

from __future__ import annotations

from privaci.autodetect.models import (
    DetectionConfidence,
    DetectionFinding,
    DetectionResult,
)
from privaci.autodetect.report import write_detection_report
from privaci.autodetect.resolve import (
    build_detection,
    resolve_effective_table_config,
    uncovered_strict_columns,
)
from privaci.autodetect.scanner import scan_catalog

__all__ = [
    "DetectionConfidence",
    "DetectionFinding",
    "DetectionResult",
    "build_detection",
    "resolve_effective_table_config",
    "scan_catalog",
    "uncovered_strict_columns",
    "write_detection_report",
]

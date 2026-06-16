"""Markdown report writer for ``privaci dry-run --report``."""

from __future__ import annotations

from pathlib import Path

from privaci.autodetect.models import DetectionFinding, DetectionResult
from privaci.catalog.models import CatalogResult
from privaci.config.models import Config


def write_detection_report(
    path: Path,
    *,
    catalog: CatalogResult,
    detection: DetectionResult,
    config: Config,
) -> None:
    """Write a human-readable markdown summary of detection outcomes."""
    lines = [
        "# PrivaCI auto-detect report",
        "",
        f"Tables inspected: {len(catalog.tables)}",
        f"Auto-detect: {'on' if config.auto_detect else 'off'}",
        f"Strict mode: {'on' if config.strict_autodetect else 'off'}",
        "",
    ]
    table_ids = sorted({f.table_id for f in detection.findings})
    for table_id in table_ids:
        lines.extend(_table_section(table_id, detection))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _table_section(table_id: str, detection: DetectionResult) -> list[str]:
    findings = detection.by_table(table_id)
    masked = [f for f in findings if f.action is not None and f.source == "autodetect"]
    passthrough = [f for f in findings if f.action is None and f.confidence != "medium"]
    uncertain = [f for f in findings if f.confidence == "medium"]
    explicit = [f for f in findings if f.source == "config"]

    lines = [f"## {table_id}", ""]
    lines.append("### Masked (auto-detect)")
    lines.extend(_finding_lines(masked))
    lines.append("")
    lines.append("### Explicit config")
    lines.extend(_finding_lines(explicit))
    lines.append("")
    lines.append("### Uncertain (manual review)")
    lines.extend(_finding_lines(uncertain))
    lines.append("")
    lines.append("### Passthrough")
    lines.extend(_finding_lines(passthrough))
    lines.append("")
    return lines


def _finding_lines(findings: list[DetectionFinding]) -> list[str]:
    if not findings:
        return ["- _(none)_"]
    lines: list[str] = []
    for finding in findings:
        action = finding.action.action if finding.action else "passthrough"
        provider = f", provider={finding.provider}" if finding.provider else ""
        pattern = (
            f", pattern={finding.matched_pattern}" if finding.matched_pattern else ""
        )
        lines.append(
            f"- `{finding.column_name}`: {action}{provider}{pattern} "
            f"({finding.confidence})"
        )
    return lines

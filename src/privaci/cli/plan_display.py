"""Shared masking-plan rendering for dry-run and plan commands."""

from __future__ import annotations

import typer

from privaci.autodetect.models import DetectionFinding
from privaci.preflight import PreflightReport


def render_plan_summary(report: PreflightReport, *, heading: str = "Plan") -> None:
    """Print the per-table masking plan to stdout."""
    masked = sum(
        1 for finding in report.detection.findings if finding.action is not None
    )
    uncertain = sum(
        1 for finding in report.detection.findings if finding.confidence == "medium"
    )
    typer.echo(f"{heading} ({len(report.catalog.tables)} table(s) in source):")
    typer.echo(
        f"Auto-detect: {masked} column(s) to mask, {uncertain} uncertain for review"
    )
    for table_id, strategy, estimate in report.dry_run_rows:
        rows = f"~{estimate} rows" if estimate > 0 else "~unknown rows"
        typer.echo(f"  {table_id}: strategy={strategy} ({rows})")
        for line in column_lines(report, table_id):
            typer.echo(line)


def column_lines(report: PreflightReport, table_id: str) -> list[str]:
    """Return per-column mask/review lines for one table."""
    lines: list[str] = []
    for finding in report.detection.by_table(table_id):
        if finding.action is not None:
            detail = action_detail(finding)
            lines.append(
                f"      mask: {finding.column_name} -> {detail} ({finding.source})"
            )
        elif finding.confidence == "medium":
            pattern = finding.matched_pattern or "heuristic"
            lines.append(
                f"      review: {finding.column_name} "
                f"(uncertain, matched {pattern})"
            )
    return lines


def action_detail(finding: DetectionFinding) -> str:
    """Render ``action`` (and provider, when present) for a finding."""
    action = finding.action
    if action is None:
        return "passthrough"
    if action.action == "fake":
        return f"fake/{action.provider}"
    return action.action

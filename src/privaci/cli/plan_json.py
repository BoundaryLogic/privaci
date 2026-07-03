"""JSON serialization for ``privaci plan`` output."""

from __future__ import annotations

import json
from typing import Any

from privaci.cli.plan_display import action_detail
from privaci.preflight import PreflightReport


def render_plan_json(report: PreflightReport) -> str:
    """Return a single JSON document describing the masking plan."""
    return json.dumps(plan_payload(report), indent=2, sort_keys=False) + "\n"


def plan_payload(report: PreflightReport) -> dict[str, Any]:
    """Build the plan JSON structure."""
    tables: list[dict[str, Any]] = []
    row_lookup = {table_id: estimate for table_id, _, estimate in report.dry_run_rows}
    strategy_lookup = {
        table_id: strategy for table_id, strategy, _ in report.dry_run_rows
    }
    for table_id in sorted(report.catalog.tables):
        if table_id not in strategy_lookup:
            continue
        tables.append(
            {
                "table": table_id,
                "strategy": strategy_lookup[table_id],
                "estimated_rows": row_lookup.get(table_id, 0),
                "columns": _column_entries(report, table_id),
            }
        )
    return {"tables": tables, "summary": _summary_counts(report)}


def _column_entries(report: PreflightReport, table_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for finding in report.detection.by_table(table_id):
        entry: dict[str, Any] = {
            "name": finding.column_name,
            "confidence": finding.confidence,
            "source": finding.source,
        }
        if finding.action is not None:
            entry["action"] = action_detail(finding)
        else:
            entry["action"] = None
        if finding.matched_pattern is not None:
            entry["matched_pattern"] = finding.matched_pattern
        entries.append(entry)
    return entries


def _summary_counts(report: PreflightReport) -> dict[str, int]:
    mask = 0
    review = 0
    copy = 0
    for finding in report.detection.findings:
        if finding.action is not None:
            mask += 1
        elif finding.confidence == "medium":
            review += 1
        else:
            copy += 1
    return {"mask": mask, "review": review, "copy": copy}

"""Implementation of ``privaci plan`` — source-only masking preview."""

from __future__ import annotations

from typing import Literal

import typer

from privaci.autodetect import build_detection
from privaci.cli.context import resolve_db_url, run_with_signal_handlers
from privaci.cli.plan_display import render_plan_summary
from privaci.cli.plan_json import render_plan_json
from privaci.cli.source_catalog import introspect_source_catalog
from privaci.config import load_config
from privaci.preflight import PreflightReport
from privaci.preflight.checks import collect_dry_run_rows, verify_config_tables_exist
from privaci.schema.elevated import elevated_objects_in_scope


def execute_plan(
    *,
    config_path: str,
    source: str | None,
    output_format: Literal["text", "json"],
) -> None:
    """Preview masking actions using the source database only.

    Args:
        config_path: Path to mask-rules.yaml.
        source: Source database URL or ``SOURCE_DB_URL`` env fallback.
        output_format: ``text`` for human output or ``json`` for CI consumption.
    """
    config = load_config(config_path)
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")

    async def _run() -> PreflightReport:
        catalog = await introspect_source_catalog(source_dsn)
        verify_config_tables_exist(config, catalog)
        detection = build_detection(config, catalog)
        dry_run_rows = collect_dry_run_rows(config, catalog)
        return PreflightReport(
            catalog=catalog,
            detection=detection,
            dry_run_rows=tuple(dry_run_rows),
        )

    report = run_with_signal_handlers(_run)
    if output_format == "json":
        typer.echo(render_plan_json(report), nl=False)
        return
    render_plan_summary(report)
    unresolved = [
        identifier
        for identifier, _kind in elevated_objects_in_scope(report.catalog, config)
        if identifier not in config.elevated_objects
    ]
    if unresolved:
        typer.echo("ACTION REQUIRED: set elevated_objects dispositions for:")
        for identifier in unresolved:
            typer.echo(f"  - {identifier}")

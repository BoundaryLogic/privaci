"""Implementation of ``privaci run`` and ``privaci dry-run``."""

from __future__ import annotations

from pathlib import Path

import typer

from privaci.autodetect import write_detection_report
from privaci.autodetect.models import DetectionFinding
from privaci.cli.context import (
    prepare_cli_run,
    resolve_db_url,
    run_with_signal_handlers,
)
from privaci.config import load_config
from privaci.config.models import Config
from privaci.pipeline import run_masking_pipeline
from privaci.pipeline.runner import PipelineSummary
from privaci.preflight import PreflightReport, run_preflight
from privaci.preflight.checks import verify_strict_autodetect
from privaci.verify import VerifyReport, run_verification
from privaci.verify.models import Verdict


def execute_run(
    *,
    config_path: str,
    source: str | None,
    target: str | None,
    dry_run: bool = False,
    audit_enabled: bool | None = None,
    report_path: str | None = None,
) -> None:
    """Load config, run pre-flight, and optionally execute the masking pipeline."""
    ctx = prepare_cli_run(config_path=config_path, source=source, target=target)
    summary: PipelineSummary | None = run_with_signal_handlers(
        lambda: _execute_async(
            config=ctx.config,
            source_dsn=ctx.source_dsn,
            target_dsn=ctx.target_dsn,
            salt=ctx.salt,
            dry_run=dry_run,
            audit_enabled=audit_enabled,
            report_path=report_path,
        )
    )
    if summary is None:
        return
    typer.echo(
        f"Run {summary.run_id} succeeded: "
        f"{summary.tables_processed} table(s), {summary.rows_processed} row(s)."
    )


async def _execute_async(
    *,
    config: Config,
    source_dsn: str,
    target_dsn: str,
    salt: str,
    dry_run: bool,
    audit_enabled: bool | None,
    report_path: str | None,
) -> PipelineSummary | None:
    report = await run_preflight(
        config=config,
        source_dsn=source_dsn,
        target_dsn=target_dsn,
        dry_run=dry_run,
        defer_strict=dry_run and report_path is not None,
    )
    _echo_preflight_warnings(report)
    if dry_run:
        _finish_dry_run(report, config, report_path)
        if report_path is not None:
            verify_strict_autodetect(config, report.detection)
        return None
    return await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        salt,
        audit_enabled=audit_enabled,
        catalog=report.catalog,
    )


def _echo_preflight_warnings(report: PreflightReport) -> None:
    for catalog_warning in report.catalog.warnings:
        typer.echo(
            f"Warning: [{catalog_warning.code}] {catalog_warning.message}", err=True
        )
    for warning in report.warnings:
        typer.echo(f"Warning: {warning}", err=True)


def _finish_dry_run(
    report: PreflightReport,
    config: Config,
    report_path: str | None,
) -> None:
    _render_dry_run_summary(report)
    if report_path is not None:
        write_detection_report(
            Path(report_path),
            catalog=report.catalog,
            detection=report.detection,
            config=config,
        )
        typer.echo(f"Wrote detection report to {report_path}")
    typer.echo("Dry run complete; no writes performed.")


def execute_verify(
    *,
    config_path: str,
    source: str | None,
    target: str | None,
    sample_size: int,
) -> None:
    """Verify a completed run by comparing target against source (value-free)."""
    config = load_config(config_path)
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    target_dsn = resolve_db_url(target, env_name="TARGET_DB_URL", role="target")
    report: VerifyReport = run_with_signal_handlers(
        lambda: run_verification(
            config=config,
            source_dsn=source_dsn,
            target_dsn=target_dsn,
            sample_size=sample_size,
        )
    )
    _render_verify_report(report)
    if not report.is_ok:
        raise typer.Exit(code=1)


def _render_verify_report(report: VerifyReport) -> None:
    """Print a value-free verification summary, failures first."""
    counts = report.counts()
    for result in report.failed:
        typer.echo(f"FAIL  {result.target}: {result.detail}", err=True)
    for result in report.warnings:
        typer.echo(f"WARN  {result.target}: {result.detail}", err=True)
    typer.echo(
        f"Verification: {counts[Verdict.PASS]} passed, "
        f"{counts[Verdict.WARN]} warning(s), {counts[Verdict.FAIL]} failure(s)."
    )


def _render_dry_run_summary(report: PreflightReport) -> None:
    """Print the per-table action summary for dry-run mode."""
    masked = sum(1 for f in report.detection.findings if f.action is not None)
    uncertain = sum(1 for f in report.detection.findings if f.confidence == "medium")
    typer.echo(f"Pre-flight OK ({len(report.catalog.tables)} table(s) in source):")
    typer.echo(
        f"Auto-detect: {masked} column(s) to mask, {uncertain} uncertain for review"
    )
    for table_id, strategy, estimate in report.dry_run_rows:
        rows = f"~{estimate} rows" if estimate > 0 else "~unknown rows"
        typer.echo(f"  {table_id}: strategy={strategy} ({rows})")
        for line in _column_lines(report, table_id):
            typer.echo(line)


def _column_lines(report: PreflightReport, table_id: str) -> list[str]:
    """Return per-column mask/review lines for one table."""
    lines: list[str] = []
    for finding in report.detection.by_table(table_id):
        if finding.action is not None:
            detail = _action_detail(finding)
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


def _action_detail(finding: DetectionFinding) -> str:
    """Render ``action`` (and provider, when present) for a finding."""
    action_name = finding.action.action if finding.action is not None else "passthrough"
    provider = finding.provider
    if provider:
        return f"{action_name}/{provider}"
    return action_name

"""Implementation of ``privaci init``."""

from __future__ import annotations

from pathlib import Path

import typer

from privaci.autodetect.models import DetectionFinding
from privaci.cli.context import resolve_db_url, run_with_signal_handlers
from privaci.cli.source_catalog import introspect_source_catalog
from privaci.config.export_yaml import export_config_yaml
from privaci.config.scaffold import build_scaffold_config
from privaci.errors import CatalogError


def execute_init(
    *,
    source: str | None,
    output: Path,
    schemas: tuple[str, ...],
    force: bool,
) -> None:
    """Scaffold a starter mask-rules.yaml from the source database schema.

    Args:
        source: Source database URL or ``SOURCE_DB_URL`` env fallback.
        output: Destination path for the generated YAML file.
        schemas: Optional schema names to include; empty means all schemas.
        force: Overwrite an existing output file when ``True``.

    Raises:
        CatalogError: When the output exists, source is missing, or introspection fails.
    """
    if output.exists() and not force:
        raise CatalogError(
            "Writing scaffold config",
            cause=f"Output file already exists: {output}",
            remediation=(
                "Pass --force to overwrite or choose a different --output path."
            ),
        )
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    schema_filter = frozenset(schemas) if schemas else None

    async def _run() -> None:
        catalog = await introspect_source_catalog(source_dsn)
        scaffold = build_scaffold_config(catalog, schema_filter=schema_filter)
        output.write_text(
            export_config_yaml(scaffold.config, init_header=True),
            encoding="utf-8",
        )
        _echo_init_summary(
            output, len(scaffold.config.tables), scaffold.review_findings
        )

    run_with_signal_handlers(_run)


def _echo_init_summary(
    output: Path,
    table_count: int,
    review_findings: tuple[DetectionFinding, ...],
) -> None:
    typer.echo(f"Wrote starter config to {output} ({table_count} table(s))")
    if review_findings:
        typer.echo(
            f"Review {len(review_findings)} uncertain column(s) "
            f"with: privaci plan --config {output}"
        )

"""Implementation of ``privaci catalog`` subcommands.

``inspect`` — human-readable schema summary.
``import-db-comments`` — bootstrap ``pii-catalog.yaml`` from column comments.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import asyncpg
import typer

from privaci.catalog import CatalogResult
from privaci.cli.context import resolve_db_url
from privaci.cli.source_catalog import (
    introspect_source_catalog,
    with_source_connection,
)
from privaci.errors import CatalogError
from privaci.pii_catalog import (
    catalog_from_comment_rows,
    fetch_column_comments,
    render_catalog_yaml,
)

logger = logging.getLogger(__name__)


def inspect_source(source: str | None) -> None:
    """Introspect the source database and print a summary to stdout.

    Args:
        source: A postgres URL or secret URI for the source database.

    Raises:
        CatalogError: When the source cannot be reached or introspected.
    """
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    catalog = asyncio.run(introspect_source_catalog(source_dsn))
    _render_summary(catalog)


def import_db_comments(
    source: str | None,
    *,
    output: str | None = None,
) -> None:
    """Emit ``pii-catalog.yaml`` from PostgreSQL column comments.

    Args:
        source: Source database URL or secret URI.
        output: Optional filesystem path; when omitted, write to stdout.

    Raises:
        CatalogError: When the source cannot be reached or queried.
    """
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    yaml_text = asyncio.run(_import_comments_yaml(source_dsn))
    if output is None:
        typer.echo(yaml_text, nl=False)
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_text, encoding="utf-8")
    typer.echo(f"Wrote {path}", err=True)


async def _import_comments_yaml(dsn: str) -> str:
    """Fetch comments and render catalog YAML (no row data)."""

    async def _work(conn: asyncpg.Connection) -> str:
        try:
            rows = await fetch_column_comments(conn)
        except asyncpg.PostgresError as exc:
            raise CatalogError(
                "Reading PostgreSQL column comments",
                cause="col_description query failed.",
                remediation=("Grant USAGE on schemas and SELECT on system catalogs."),
            ) from exc
        return render_catalog_yaml(catalog_from_comment_rows(rows))

    return await with_source_connection(dsn, _work)


def _render_summary(catalog: CatalogResult) -> None:
    """Print tables, load layers, and warnings."""
    typer.echo(
        f"Discovered {len(catalog.tables)} table(s)"
        f" and {len(catalog.views)} view(s):"
    )
    for identifier in sorted(catalog.tables):
        table = catalog.tables[identifier]
        flags = " [self-cycle]" if table.self_cycle else ""
        typer.echo(
            f"  {identifier} "
            f"({len(table.columns)} cols, {len(table.foreign_keys)} fks, "
            f"{_format_estimated_rows(table.estimated_rows)}){flags}"
        )

    if catalog.views:
        typer.echo("\nViews (not replicated):")
        for view in catalog.views:
            typer.echo(f"  {view.identifier} [{view.kind}]")

    typer.echo(f"\nLoad plan ({len(catalog.load_plan.layers)} layer(s)):")
    for index, layer in enumerate(catalog.load_plan.layers, start=1):
        typer.echo(f"  {index}. {', '.join(layer.table_ids)}")
    if catalog.load_plan.deferred_edges:
        typer.echo("\nDeferred FK edges (cycle break):")
        for edge in catalog.load_plan.deferred_edges:
            typer.echo(
                f"  {edge.referencing_table} -[{edge.foreign_key_name}]-> "
                f"{edge.referenced_table}"
            )

    if catalog.warnings:
        typer.echo(f"\nWarnings ({len(catalog.warnings)}):")
        for warning in catalog.warnings:
            typer.echo(f"  [{warning.code}] {warning.message}")


def _format_estimated_rows(estimated_rows: float) -> str:
    """Format planner row statistics for human-readable CLI output."""
    if estimated_rows < 0:
        return "~unknown rows"
    return f"~{int(estimated_rows)} rows"

"""Implementation of the ``privaci catalog inspect`` command.

Read-only: connects to the source database, introspects the schema, and prints
a human-readable summary of tables, the FK load plan, and warnings. Useful for
getting acquainted with a source before writing ``mask-rules.yaml``.
"""

from __future__ import annotations

import asyncio
import logging

import asyncpg
import typer

from privaci.catalog import CatalogResult, introspect_catalog
from privaci.cli.context import resolve_db_url
from privaci.errors import CatalogError

logger = logging.getLogger(__name__)


def inspect_source(source: str | None) -> None:
    """Introspect the source database and print a summary to stdout.

    Args:
        source: A postgres URL or secret URI for the source database.

    Raises:
        CatalogError: When the source cannot be reached or introspected.
    """
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    catalog = asyncio.run(_introspect(source_dsn))
    _render_summary(catalog)


async def _introspect(dsn: str) -> CatalogResult:
    """Open a short-lived connection and introspect the catalog."""
    try:
        conn = await asyncpg.connect(dsn)
    except (OSError, asyncpg.PostgresError) as exc:
        raise CatalogError(
            "Connecting to the source database",
            cause="The source database is not reachable.",
            remediation="Verify SOURCE_DB_URL and that the database is running.",
        ) from exc
    try:
        return await introspect_catalog(conn)
    finally:
        await conn.close()


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

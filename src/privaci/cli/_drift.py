"""Implementation of ``privaci detect-drift``."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg
import typer

from privaci.catalog import introspect_catalog
from privaci.catalog.snapshot import load_latest_schema_snapshot
from privaci.cli.context import resolve_db_url
from privaci.config import load_config
from privaci.contracts.base import DriftDetector, DriftReport
from privaci.contracts.plugins import PluginBundle, load_plugins
from privaci.errors import CatalogError, DriftError
from privaci.state.fingerprints import source_db_hash

logger = logging.getLogger(__name__)

_COMMERCIAL_REQUIRED_MSG = "detect-drift requires the commercial layer."


def execute_detect_drift(
    *,
    config_path: str,
    source: str | None,
    target: str | None,
    accept_drift: bool = False,
) -> None:
    """Compare the live source catalog to the last stored snapshot."""
    plugins = load_plugins()
    detector = _require_commercial_drift_detector(plugins)
    config = load_config(config_path)
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    target_dsn = resolve_db_url(target, env_name="TARGET_DB_URL", role="target")
    asyncio.run(
        _detect_drift_async(
            source_dsn=source_dsn,
            target_dsn=target_dsn,
            implied_fk_ignore=frozenset(config.implied_fk_ignore),
            drift_detector=detector,
            accept_drift=accept_drift,
        )
    )


def _require_commercial_drift_detector(plugins: PluginBundle) -> DriftDetector:
    if plugins.drift_detector is None:
        typer.echo(_COMMERCIAL_REQUIRED_MSG, err=True)
        raise typer.Exit(code=1)
    return plugins.drift_detector


async def _detect_drift_async(
    *,
    source_dsn: str,
    target_dsn: str,
    implied_fk_ignore: frozenset[str],
    drift_detector: DriftDetector,
    accept_drift: bool,
) -> None:
    current = await _introspect_snapshot(source_dsn, implied_fk_ignore)
    previous = await _load_baseline_snapshot(target_dsn, source_dsn)
    if previous is None:
        typer.echo("No baseline snapshot found; drift check skipped.")
        return
    report = drift_detector.detect(previous, current)
    if not report.has_drift:
        typer.echo("No schema drift detected.")
        return
    _render_findings(report)
    if accept_drift:
        typer.echo("Drift accepted (--accept-drift); exiting successfully.")
        return
    raise DriftError(
        "Checking schema drift against the last successful run",
        cause=f"Detected {len(report.findings)} structural change(s).",
        remediation=(
            "Review the findings above. Re-run with --accept-drift once "
            "changes are intentional."
        ),
    )


async def _introspect_snapshot(
    source_dsn: str,
    implied_fk_ignore: frozenset[str],
) -> dict[str, Any]:
    try:
        conn = await asyncpg.connect(source_dsn)
    except (OSError, asyncpg.PostgresError) as exc:
        raise CatalogError(
            "Connecting to the source database",
            cause="The source database is not reachable.",
            remediation="Verify SOURCE_DB_URL and that the database is running.",
        ) from exc
    try:
        catalog = await introspect_catalog(
            conn, implied_fk_ignore=implied_fk_ignore
        )
        return catalog.to_snapshot_dict()
    finally:
        await conn.close()


async def _load_baseline_snapshot(
    target_dsn: str,
    source_dsn: str,
) -> dict[str, Any] | None:
    db_hash = source_db_hash(source_dsn)
    try:
        conn = await asyncpg.connect(target_dsn)
    except (OSError, asyncpg.PostgresError) as exc:
        raise CatalogError(
            "Connecting to the target database",
            cause="The target database is not reachable.",
            remediation="Verify TARGET_DB_URL and that the database is running.",
        ) from exc
    try:
        snapshot = await load_latest_schema_snapshot(conn, source_db_hash=db_hash)
        return snapshot
    finally:
        await conn.close()


def _render_findings(report: DriftReport) -> None:
    typer.echo(f"Schema drift: {len(report.findings)} finding(s):")
    for finding in report.findings:
        typer.echo(json.dumps(finding, sort_keys=True))

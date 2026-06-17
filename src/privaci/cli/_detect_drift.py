"""``privaci detect-drift`` implementation."""

from __future__ import annotations

import asyncio
import json

import typer

from privaci.catalog import introspect_catalog
from privaci.catalog.snapshot import load_latest_schema_snapshot
from privaci.cli.context import resolve_db_url
from privaci.contracts import load_plugins
from privaci.contracts.base import DriftReport
from privaci.errors import DriftError, PreflightError
from privaci.state.fingerprints import source_db_hash


def execute_detect_drift(
    *,
    source: str | None,
    target: str | None,
    accept_drift: bool = False,
) -> None:
    """Compare live source catalog to the last stored snapshot on target."""
    source_dsn = resolve_db_url(source, env_name="SOURCE_DB_URL", role="source")
    target_dsn = resolve_db_url(target, env_name="TARGET_DB_URL", role="target")
    report = asyncio.run(_detect_async(source_dsn, target_dsn))
    if report.findings:
        typer.echo(
            json.dumps({"has_drift": True, "findings": report.findings}, indent=2)
        )
    if report.has_drift and not accept_drift:
        raise DriftError(
            "Schema drift detection",
            cause=f"{len(report.findings)} drift finding(s) detected.",
            remediation=(
                "Review findings, update mask-rules.yaml, then re-run or pass "
                "--accept-drift to emit findings only."
            ),
        )


async def _detect_async(source_dsn: str, target_dsn: str) -> DriftReport:
    plugins = load_plugins()
    if plugins.drift_detector is None:
        raise PreflightError(
            "Schema drift detection",
            cause="Drift detection requires the commercial layer.",
            remediation="Install privaci-commercial or use the Marketplace image.",
        )
    import asyncpg

    source = await asyncpg.connect(source_dsn)
    target = await asyncpg.connect(target_dsn)
    try:
        current = (await introspect_catalog(source)).to_snapshot_dict()
        previous = await load_latest_schema_snapshot(
            target, source_db_hash=source_db_hash(source_dsn)
        )
    finally:
        await source.close()
        await target.close()
    if previous is None:
        raise PreflightError(
            "Schema drift detection",
            cause="No baseline snapshot on target.",
            remediation="Run `privaci run` once to store a schema snapshot.",
        )
    return plugins.drift_detector.detect(previous, current)

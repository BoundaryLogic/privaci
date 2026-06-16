"""Orchestrate pre-flight checks before a masking run."""

from __future__ import annotations

from dataclasses import dataclass, field

import asyncpg

from privaci.autodetect import DetectionResult, build_detection
from privaci.catalog import introspect_catalog
from privaci.catalog.models import CatalogResult
from privaci.config.models import Config
from privaci.errors import CatalogError, PreflightError
from privaci.observability import Event, emit
from privaci.preflight.checks import (
    collect_dry_run_rows,
    run_target_checks,
    verify_config_tables_exist,
    verify_exclude_strategy,
    verify_null_actions,
    verify_partition_config,
    verify_source_readable,
    verify_strict_autodetect,
)


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """Outcome of a successful pre-flight phase."""

    catalog: CatalogResult
    detection: DetectionResult
    warnings: tuple[str, ...] = ()
    dry_run_rows: tuple[tuple[str, str, int], ...] = field(default_factory=tuple)


async def run_preflight(
    *,
    config: Config,
    source_dsn: str,
    target_dsn: str,
    dry_run: bool = False,
    for_resume: bool = False,
) -> PreflightReport:
    """Execute all pre-flight checks without writing masked data.

    Raises:
        CatalogError: When the source cannot be introspected.
        PreflightError: When a target or permission check fails.
        ConfigError: When config references invalid tables or actions.
    """
    source = await _connect(source_dsn, role="source")
    target = await _connect(target_dsn, role="target")
    try:
        return await _run_preflight_checks(
            source,
            target,
            config,
            dry_run=dry_run,
            for_resume=for_resume,
        )
    finally:
        await source.close()
        await target.close()


async def _run_preflight_checks(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    config: Config,
    *,
    dry_run: bool,
    for_resume: bool,
) -> PreflightReport:
    await verify_source_readable(source)
    catalog = await introspect_catalog(
        source, implied_fk_ignore=frozenset(config.implied_fk_ignore)
    )
    verify_config_tables_exist(config, catalog)
    verify_partition_config(config, catalog)
    verify_null_actions(config, catalog)
    verify_exclude_strategy(config, catalog)
    detection = build_detection(config, catalog)
    verify_strict_autodetect(config, detection)
    warnings = await run_target_checks(
        target, config, catalog, dry_run=dry_run, for_resume=for_resume
    )
    dry_run_rows = tuple(collect_dry_run_rows(config, catalog))
    emit(
        Event.PREFLIGHT_OK,
        checks=[{"name": "all", "status": "ok", "detail": None}],
        tables=len(catalog.tables),
    )
    return PreflightReport(
        catalog=catalog,
        detection=detection,
        warnings=tuple(warnings),
        dry_run_rows=dry_run_rows,
    )


async def _connect(dsn: str, *, role: str) -> asyncpg.Connection:
    try:
        return await asyncpg.connect(dsn)
    except (OSError, asyncpg.PostgresError) as exc:
        if role == "source":
            raise CatalogError(
                "Connecting to the source database",
                cause="The source database is not reachable.",
                remediation="Verify SOURCE_DB_URL and that the database is running.",
            ) from exc
        raise PreflightError(
            "Connecting to the target database",
            cause="The target database is not reachable.",
            remediation="Verify TARGET_DB_URL and that the database is running.",
        ) from exc

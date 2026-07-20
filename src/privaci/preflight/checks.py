"""Individual pre-flight checks against source and target databases."""

from __future__ import annotations

import logging

import asyncpg

from privaci.autodetect import DetectionResult, uncovered_strict_columns
from privaci.catalog.models import CatalogResult
from privaci.catalog.partitions import validate_no_subpartitioning
from privaci.config.conditional import (
    assert_require_binary_allows_when,
    validate_when_against_catalog,
)
from privaci.config.loader import check_null_actions
from privaci.config.models import Config
from privaci.errors import CatalogError, ConfigError, PreflightError
from privaci.preflight.passthrough_copy import (
    assert_require_binary_allows_orphan_nulling,
    verify_passthrough_copy_policy,
)
from privaci.preflight.target import (
    collision_warning_for_dry_run,
    ensure_target_ready,
    validate_target_policy,
)
from privaci.schema.assume_existing import (
    raise_validation_failed,
    validate_assume_existing,
)
from privaci.schema.elevated import (
    validate_elevated_dispositions,
    validate_function_excluded_deps,
)
from privaci.schema.replicate import validate_exclude_fks
from privaci.schema.table_policy import table_strategy

logger = logging.getLogger(__name__)


async def verify_source_readable(conn: asyncpg.Connection) -> None:
    """Confirm the source connection can read ``pg_catalog``."""
    try:
        allowed = await conn.fetchval(
            "SELECT has_schema_privilege(current_user, 'pg_catalog', 'USAGE')"
        )
        if not allowed:
            raise PreflightError(
                "Checking source database read permissions",
                cause="Current user cannot read pg_catalog.",
                remediation="Grant CONNECT and USAGE on pg_catalog to the source user.",
            )
        await conn.fetchval("SELECT 1 FROM pg_catalog.pg_class LIMIT 1")
    except asyncpg.PostgresError as exc:
        raise CatalogError(
            "Reading the source database catalog",
            cause="The source user cannot query pg_catalog.",
            remediation="Grant read access on the source database and retry.",
        ) from exc


async def verify_target_writable(conn: asyncpg.Connection) -> None:
    """Confirm the target user can create schemas."""
    try:
        can_create = await conn.fetchval(
            "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"
        )
        has_privaci = await conn.fetchval(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.schemata "
            "  WHERE schema_name = '_privaci'"
            ")"
        )
        if not can_create and not has_privaci:
            raise PreflightError(
                "Checking target database write permissions",
                cause="Current user cannot CREATE SCHEMA on the target database.",
                remediation=(
                    "Grant CREATE on the target database, or pre-create the "
                    "_privaci schema with sufficient privileges."
                ),
            )
    except asyncpg.PostgresError as exc:
        raise PreflightError(
            "Connecting to the target database",
            cause="The target database is not reachable or lacks privileges.",
            remediation="Verify TARGET_DB_URL and target user grants.",
        ) from exc


def verify_partition_config(config: Config, catalog: CatalogResult) -> None:
    """Reject sub-partitioning and per-child mask-rules entries."""
    validate_no_subpartitioning(catalog.tables)
    child_configs = sorted(
        table_id
        for table_id in config.tables
        if (table := catalog.tables.get(table_id)) is not None
        and table.parent_partition is not None
    )
    if not child_configs:
        return
    raise ConfigError(
        "Validating partition table configuration",
        cause=(
            "Per-partition strategy overrides are not supported: "
            + ", ".join(child_configs)
        ),
        remediation=(
            "Configure the partitioned parent table; children inherit its strategy."
        ),
    )


def verify_config_tables_exist(config: Config, catalog: CatalogResult) -> None:
    """Ensure every configured table exists in the source catalog."""
    missing = sorted(set(config.tables) - set(catalog.tables))
    if not missing:
        return
    raise ConfigError(
        "Validating configured tables against the source catalog",
        cause="Tables in config are absent from the source: " + ", ".join(missing),
        remediation="Fix table names in mask-rules.yaml or load the missing tables.",
    )


def verify_null_actions(config: Config, catalog: CatalogResult) -> None:
    """Reject ``null`` actions on ``NOT NULL`` columns using catalog metadata."""
    not_null_columns = {
        table_id: {column.name for column in table.columns if column.not_null}
        for table_id, table in catalog.tables.items()
    }
    check_null_actions(config, not_null_columns)


def verify_conditional_when(config: Config, catalog: CatalogResult) -> None:
    """Type-check ``when:`` CEL guards against the source catalog."""
    validate_when_against_catalog(config, catalog)


def verify_exclude_strategy(config: Config, catalog: CatalogResult) -> None:
    """Run the exclude + dangling FK validation from schema replication."""
    validate_exclude_fks(catalog, config)


def verify_strict_autodetect(
    config: Config,
    detection: DetectionResult,
) -> None:
    """Reject runs when strict mode finds uncovered PII columns."""
    uncovered = uncovered_strict_columns(config, detection)
    if not uncovered:
        return
    column_list = ", ".join(uncovered)
    raise ConfigError(
        "Validating strict auto-detect coverage",
        cause=f"Uncovered PII columns: {column_list}",
        remediation=(
            "Add each column to mask-rules.yaml or set strict_autodetect: false. "
            "Example: Add 'users.email' to mask-rules.yaml or pass "
            "--no-strict-autodetect to acknowledge."
        ),
    )


async def run_target_checks(
    conn: asyncpg.Connection,
    config: Config,
    catalog: CatalogResult,
    *,
    dry_run: bool = False,
    for_resume: bool = False,
    detection: DetectionResult | None = None,
) -> list[str]:
    """Verify target permissions and prepare greenfield replication targets."""
    await verify_target_writable(conn)
    warnings = warn_disk_capacity(catalog)
    assert_require_binary_allows_orphan_nulling(catalog, config)
    assert_require_binary_allows_when(config)
    if for_resume:
        return warnings
    if config.schema_mode == "replicate":
        validate_elevated_dispositions(catalog, config)
        validate_function_excluded_deps(catalog, config)
    if dry_run:
        if config.schema_mode == "assume_existing":
            await _run_assume_existing_dry_run_checks(
                conn,
                config,
                catalog,
                detection=detection,
            )
        warnings.extend(await _dry_run_target_warnings(conn, config, catalog))
        return warnings
    if config.schema_mode == "assume_existing":
        await validate_target_policy(conn, config, catalog)
        return warnings
    await ensure_target_ready(conn, config, catalog)
    return warnings


async def _run_assume_existing_dry_run_checks(
    conn: asyncpg.Connection,
    config: Config,
    catalog: CatalogResult,
    *,
    detection: DetectionResult | None,
) -> None:
    """Validate prebuilt schema for dry-run without writing audit rows."""
    validation = await validate_assume_existing(conn, catalog, config)
    if not validation.is_ok:
        raise_validation_failed(validation)
    if detection is not None:
        await verify_passthrough_copy_policy(conn, catalog, config, detection)


async def _dry_run_target_warnings(
    conn: asyncpg.Connection,
    config: Config,
    catalog: CatalogResult,
) -> list[str]:
    """Warn when a real run would fail on target collision without blocking dry-run."""
    warning = await collision_warning_for_dry_run(conn, config, catalog)
    return [] if warning is None else [warning]


def warn_disk_capacity(catalog: CatalogResult) -> list[str]:
    """Return warnings when estimated row volume is unusually large."""
    total_rows = sum(max(table.estimated_rows, 0) for table in catalog.tables.values())
    if total_rows <= 0:
        return []
    # Without target disk stats in MVP, warn on very large catalogs only.
    if total_rows < 50_000_000:
        return []
    message = (
        f"Estimated source rows ({int(total_rows):,}) exceed the MVP disk "
        f"advisory threshold; verify target free space before proceeding."
    )
    logger.warning(message, extra={"estimated_rows": int(total_rows)})
    return [message]


def collect_dry_run_rows(
    config: Config,
    catalog: CatalogResult,
) -> list[tuple[str, str, int]]:
    """Return per-table strategy and estimated row counts for dry-run output."""
    rows: list[tuple[str, str, int]] = []
    for table_id in sorted(catalog.tables):
        table = catalog.tables[table_id]
        if table.is_partitioned:
            continue
        strategy = table_strategy(table, config)
        estimate = max(int(table.estimated_rows), 0)
        rows.append((table_id, strategy, estimate))
    return rows

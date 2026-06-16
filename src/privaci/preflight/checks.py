"""Individual pre-flight checks against source and target databases."""

from __future__ import annotations

import logging

import asyncpg

from privaci.autodetect import DetectionResult, uncovered_strict_columns
from privaci.catalog.models import CatalogResult, TableInfo
from privaci.catalog.partitions import config_table_id, validate_no_subpartitioning
from privaci.config.loader import check_null_actions
from privaci.config.models import Config
from privaci.errors import CatalogError, ConfigError, PreflightError
from privaci.preflight.target import count_user_tables, ensure_target_ready
from privaci.schema.replicate import validate_exclude_fks

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
) -> list[str]:
    """Verify target permissions and apply ``on_existing_data`` policy."""
    await verify_target_writable(conn)
    warnings = warn_disk_capacity(catalog)
    if dry_run or for_resume:
        if dry_run:
            warnings.extend(await _dry_run_target_warnings(conn, config))
        return warnings
    await ensure_target_ready(conn, config, catalog)
    return warnings


async def _dry_run_target_warnings(
    conn: asyncpg.Connection,
    config: Config,
) -> list[str]:
    """Warn when a real run would fail on target collision without blocking dry-run."""
    if config.on_existing_data != "fail":
        return []
    user_tables = await count_user_tables(conn)
    if user_tables <= 0:
        return []
    return [
        (
            f"Target has {user_tables} user table(s) outside _privaci; "
            "a real run will fail with on_existing_data: fail unless the "
            "target is emptied or the policy is changed."
        )
    ]


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
        strategy = _table_strategy(table, config)
        estimate = max(int(table.estimated_rows), 0)
        rows.append((table_id, strategy, estimate))
    return rows


def _table_strategy(table: TableInfo, config: Config) -> str:
    table_cfg = config.tables.get(config_table_id(table))
    if table_cfg is None:
        return "transform"
    return table_cfg.strategy

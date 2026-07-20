"""Preflight enforcement for ``passthrough_copy: require_binary``."""

from __future__ import annotations

import asyncpg

from privaci.autodetect import resolve_effective_table_config
from privaci.autodetect.models import DetectionResult
from privaci.catalog.models import CatalogResult
from privaci.catalog.partitions import is_partition_child
from privaci.config.conditional import assert_require_binary_allows_when
from privaci.config.models import Config
from privaci.errors import PreflightError
from privaci.schema.assume_existing import (
    binary_copy_columns_match,
    fetch_target_columns,
)
from privaci.schema.orphan_fks import table_requires_orphan_nulling
from privaci.schema.replicate import tables_in_load_order
from privaci.stream.passthrough_eligibility import table_is_passthrough_candidate


def assert_require_binary_allows_orphan_nulling(
    catalog: CatalogResult,
    config: Config,
) -> None:
    """Fail when ``require_binary`` collides with orphan-FK nulling (any mode)."""
    if config.passthrough_copy != "require_binary":
        return
    orphan_null_tables = [
        table.identifier
        for table in tables_in_load_order(catalog)
        if not is_partition_child(table)
        and table_requires_orphan_nulling(table, catalog, config)
    ]
    if not orphan_null_tables:
        return
    raise PreflightError(
        "Checking passthrough_copy: require_binary eligibility",
        cause=(
            "null_orphan_fks requires row mutation (batch path) for: "
            + ", ".join(sorted(orphan_null_tables))
        ),
        remediation=(
            "Set passthrough_copy: auto or batch when null_orphan_fks is "
            "enabled on tables that reference excluded parents."
        ),
    )


async def verify_passthrough_copy_policy(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    detection: DetectionResult,
) -> None:
    """Enforce ``passthrough_copy: require_binary`` against the target schema."""
    if config.passthrough_copy != "require_binary":
        return
    assert_require_binary_allows_orphan_nulling(catalog, config)
    assert_require_binary_allows_when(config)
    ineligible: list[str] = []
    for table in tables_in_load_order(catalog):
        if is_partition_child(table):
            continue
        table_cfg = resolve_effective_table_config(table, config, detection)
        if table_cfg.strategy == "exclude":
            continue
        if not table_is_passthrough_candidate(table, table_cfg):
            continue
        target_cols = await fetch_target_columns(
            conn, table.schema_name, table.table_name
        )
        if not binary_copy_columns_match(table, target_cols):
            ineligible.append(table.identifier)
    if not ineligible:
        return
    raise PreflightError(
        "Checking passthrough_copy: require_binary eligibility",
        cause=(
            "Passthrough tables are not binary-COPY eligible (column order/type "
            f"mismatch or extras): {', '.join(sorted(ineligible))}"
        ),
        remediation=(
            "Align target column order with the source, or set "
            "passthrough_copy: auto or batch."
        ),
    )

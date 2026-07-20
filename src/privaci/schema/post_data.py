"""Post-data DDL: indexes, remaining functions/views, triggers, matview refresh."""

from __future__ import annotations

import asyncpg

from privaci.catalog.identifiers import quote_pg_identifier
from privaci.catalog.models import CatalogResult, FunctionInfo, TriggerInfo
from privaci.catalog.partitions import is_partition_child
from privaci.config.models import Config
from privaci.schema.ddl import emit_nonunique_indexes
from privaci.schema.elevated import disposition_for_function
from privaci.schema.execute import execute_ddl
from privaci.schema.function_hoist import functions_required_for_pre_data
from privaci.schema.objects import (
    ReplicatedObject,
    refresh_materialized_views,
    replicate_functions_and_views,
)
from privaci.schema.replicate import tables_in_load_order
from privaci.schema.table_policy import is_excluded_table

_POST_DATA_CONTEXT = "Applying post-data schema DDL on the target database"
_POST_DATA_REMEDIATION = (
    "Verify target permissions and object dependencies, then resume."
)


async def apply_post_data_ddl(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> tuple[tuple[ReplicatedObject, ...], tuple[tuple[str, str], ...]]:
    """Apply post-data DDL after streaming. Idempotent for resume retries.

    Returns:
        ``(created_objects, refreshed_matviews)`` where matview pairs are
        ``(schema_name, view_name)``. Does not mark run success; callers must
        invoke this before ``SUCCEEDED``. Per-table ``setval`` stays in stream.
    """
    if config.schema_mode != "replicate":
        return (), ()
    created: list[ReplicatedObject] = []
    if config.replicate_all_indexes:
        created.extend(await _create_nonunique_indexes(conn, catalog, config))
    pre_ids = frozenset(
        function.identifier
        for function in functions_required_for_pre_data(catalog, config)
    )
    created.extend(
        await replicate_functions_and_views(
            conn,
            catalog,
            config,
            skip_function_ids=pre_ids,
            ddl_phase="post-data",
        )
    )
    if config.replicate_triggers:
        created.extend(await _replicate_triggers(conn, catalog, config))
    refreshed = await refresh_materialized_views(conn, catalog, config)
    return tuple(created), refreshed


async def _create_nonunique_indexes(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> list[ReplicatedObject]:
    created: list[ReplicatedObject] = []
    for table in tables_in_load_order(catalog):
        if is_partition_child(table) or is_excluded_table(table, config):
            continue
        for index_name, stmt in emit_nonunique_indexes(table):
            await execute_ddl(
                conn,
                stmt,
                context=_POST_DATA_CONTEXT,
                remediation=_POST_DATA_REMEDIATION,
            )
            created.append(
                ReplicatedObject(
                    schema_name=table.schema_name,
                    object_name=index_name,
                    kind="index",
                    is_elevated=False,
                    depends_on=(table.identifier,),
                    ddl_phase="post-data",
                )
            )
    return created


async def _replicate_triggers(
    conn: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
) -> list[ReplicatedObject]:
    created: list[ReplicatedObject] = []
    for trigger in catalog.triggers:
        if not trigger_should_replicate(trigger, catalog, config):
            continue
        await execute_ddl(
            conn,
            _drop_trigger_sql(trigger),
            context=_POST_DATA_CONTEXT,
            remediation=_POST_DATA_REMEDIATION,
        )
        await execute_ddl(
            conn,
            trigger.create_sql,
            context=_POST_DATA_CONTEXT,
            remediation=_POST_DATA_REMEDIATION,
        )
        created.append(
            ReplicatedObject(
                schema_name=trigger.schema_name,
                object_name=trigger.table_name,
                kind="trigger",
                is_elevated=False,
                depends_on=(
                    (trigger.function_identity,) if trigger.function_identity else ()
                ),
                ddl_phase="post-data",
                payload_object_name=trigger.trigger_name,
            )
        )
    return created


def trigger_should_replicate(
    trigger: TriggerInfo,
    catalog: CatalogResult,
    config: Config,
) -> bool:
    """Return True when a trigger should be created in post-data."""
    if config.schema_mode != "replicate" or not config.replicate_triggers:
        return False
    if _trigger_table_excluded(trigger, catalog, config):
        return False
    return trigger_function_replicable(trigger, catalog, config)


def trigger_function_replicable(
    trigger: TriggerInfo,
    catalog: CatalogResult,
    config: Config,
) -> bool:
    """Return True when the trigger function will exist on the target."""
    if not trigger.function_identity:
        return True
    function = _function_by_identity(catalog, trigger.function_identity)
    if function is None:
        return False
    return disposition_for_function(function, config) == "replicate"


def _function_by_identity(catalog: CatalogResult, identity: str) -> FunctionInfo | None:
    for function in catalog.functions:
        if function.identifier == identity:
            return function
    return None


def _drop_trigger_sql(trigger: TriggerInfo) -> str:
    """Return ``DROP TRIGGER IF EXISTS`` for one catalog trigger."""
    schema = quote_pg_identifier(trigger.schema_name)
    table = quote_pg_identifier(trigger.table_name)
    name = quote_pg_identifier(trigger.trigger_name)
    return f"DROP TRIGGER IF EXISTS {name} ON {schema}.{table}"


def _trigger_table_excluded(
    trigger: TriggerInfo,
    catalog: CatalogResult,
    config: Config,
) -> bool:
    table = catalog.tables.get(f"{trigger.schema_name}.{trigger.table_name}")
    if table is None:
        return True
    return is_excluded_table(table, config)

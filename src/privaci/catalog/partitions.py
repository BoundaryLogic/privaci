"""Partition metadata attachment and helpers for catalog introspection."""

from __future__ import annotations

from dataclasses import replace

import asyncpg

from privaci.catalog.models import CatalogWarning, TableInfo, table_id
from privaci.catalog.queries import PARTITION_CHILDREN_SQL, PARTITIONED_PARENTS_SQL
from privaci.errors import CatalogError

_STRATEGY_CODES: dict[str, str] = {
    "r": "RANGE",
    "l": "LIST",
    "h": "HASH",
}


async def attach_partition_metadata(
    conn: asyncpg.Connection,
    tables: dict[str, TableInfo],
) -> tuple[CatalogWarning, ...]:
    """Enrich ``tables`` with native partitioning metadata from ``pg_catalog``."""
    await _attach_partitioned_parents(conn, tables)
    await _attach_partition_children(conn, tables)
    return tuple(_subpartition_warnings(tables))


async def _attach_partitioned_parents(
    conn: asyncpg.Connection,
    tables: dict[str, TableInfo],
) -> None:
    for row in await conn.fetch(PARTITIONED_PARENTS_SQL):
        identifier = table_id(row["schema_name"], row["parent_table"])
        parent = tables.get(identifier)
        if parent is None:
            parent = TableInfo(
                schema_name=row["schema_name"],
                table_name=row["parent_table"],
                columns=(),
                estimated_rows=-1.0,
            )
            tables[identifier] = parent
        strategy = _STRATEGY_CODES.get(row["partition_strategy"], "RANGE")
        tables[identifier] = replace(
            parent,
            is_partitioned=True,
            partition_strategy=strategy,
            partition_key_def=row["partition_key_def"],
        )


async def _attach_partition_children(
    conn: asyncpg.Connection,
    tables: dict[str, TableInfo],
) -> None:
    for row in await conn.fetch(PARTITION_CHILDREN_SQL):
        parent_id = table_id(row["schema_name"], row["parent_table"])
        child_id = table_id(row["schema_name"], row["child_table"])
        child = tables.get(child_id)
        if child is None:
            continue
        tables[child_id] = replace(
            child,
            parent_partition=parent_id,
            partition_bound=row["partition_bound"],
            is_partitioned=bool(row["is_sub_partitioned"]),
        )
        parent = tables.get(parent_id)
        if parent is not None and parent.is_partitioned:
            children = list(parent.partition_children)
            if child_id not in children:
                children.append(child_id)
            tables[parent_id] = replace(
                parent, partition_children=tuple(sorted(children))
            )


def validate_no_subpartitioning(tables: dict[str, TableInfo]) -> None:
    """Refuse multi-level partitioning at pre-flight (exit 2)."""
    offenders = [
        table.identifier
        for table in tables.values()
        if table.parent_partition and table.is_partitioned
    ]
    if not offenders:
        return
    raise CatalogError(
        "Checking native table partitioning",
        cause="Sub-partitioned tables are not supported: "
        + ", ".join(sorted(offenders)),
        remediation=(
            "Flatten partitioning to a single level or exclude sub-partitioned "
            "tables from the run."
        ),
    )


def config_table_id(table: TableInfo) -> str:
    """Return the table id used for mask-rules.yaml lookup."""
    return table.parent_partition or table.identifier


def is_partition_child(table: TableInfo) -> bool:
    """Return whether ``table`` is a partition child."""
    return table.parent_partition is not None


def should_skip_fk_edge(table: TableInfo) -> bool:
    """Skip per-child FK rows; the parent supplies load-order edges."""
    return is_partition_child(table)


def _subpartition_warnings(tables: dict[str, TableInfo]) -> list[CatalogWarning]:
    warnings: list[CatalogWarning] = []
    for table in tables.values():
        if table.parent_partition and table.is_partitioned:
            warnings.append(
                CatalogWarning(
                    code="sub_partitioning",
                    message=(
                        f"Table {table.identifier} is sub-partitioned; "
                        "v1.0 supports only single-level partitioning."
                    ),
                    table_id=table.identifier,
                )
            )
    return warnings

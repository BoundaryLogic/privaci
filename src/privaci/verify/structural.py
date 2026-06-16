"""Structural, value-free verification queries against source and target."""

from __future__ import annotations

from typing import Any

import asyncpg

from privaci.catalog.identifiers import qualify, quote_pg_identifier
from privaci.catalog.models import TableInfo
from privaci.verify.models import CheckResult, Verdict


async def check_row_count_parity(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    table: TableInfo,
) -> CheckResult:
    """Compare exact row counts between source and target for a table."""
    qual = _qual(table)
    src = await source.fetchval(f"SELECT count(*) FROM {qual}")  # noqa: S608
    tgt = await target.fetchval(f"SELECT count(*) FROM {qual}")  # noqa: S608
    if src == tgt:
        return CheckResult(
            "table.row_count",
            Verdict.PASS,
            table.identifier,
            f"Row count matches ({src}).",
        )
    return CheckResult(
        "table.row_count",
        Verdict.FAIL,
        table.identifier,
        f"Row count differs: source={src}, target={tgt}.",
    )


async def check_unique_preserved(
    target: asyncpg.Connection,
    table: TableInfo,
) -> list[CheckResult]:
    """Verify each unique/PK column group has no duplicates in the target."""
    groups = _unique_groups(table)
    results: list[CheckResult] = []
    for group in groups:
        cols = ", ".join(quote_pg_identifier(c) for c in group)
        not_null = " AND ".join(f"{quote_pg_identifier(c)} IS NOT NULL" for c in group)
        qual = _qual(table)
        query = (
            f"SELECT count(*) FROM (SELECT {cols} FROM {qual} "  # noqa: S608
            f"WHERE {not_null} GROUP BY {cols} HAVING count(*) > 1) d"
        )
        dupes = await target.fetchval(query)
        label = f"{table.identifier}({', '.join(group)})"
        if dupes:
            results.append(
                CheckResult(
                    "table.uniqueness",
                    Verdict.FAIL,
                    label,
                    f"{dupes} duplicate group(s) after masking.",
                )
            )
        else:
            results.append(
                CheckResult(
                    "table.uniqueness",
                    Verdict.PASS,
                    label,
                    "Uniqueness preserved.",
                )
            )
    return results


async def check_fk_integrity(
    target: asyncpg.Connection,
    table: TableInfo,
) -> list[CheckResult]:
    """Verify foreign keys in the target reference existing parent rows."""
    results: list[CheckResult] = []
    for fk in table.foreign_keys:
        orphans = await _count_orphans(target, table, fk)
        label = f"{table.identifier}({', '.join(fk.source_columns)})"
        if orphans:
            results.append(
                CheckResult(
                    "table.fk_integrity",
                    Verdict.FAIL,
                    label,
                    f"{orphans} orphaned foreign-key row(s) in target.",
                )
            )
        else:
            results.append(
                CheckResult(
                    "table.fk_integrity",
                    Verdict.PASS,
                    label,
                    "Foreign-key integrity preserved.",
                )
            )
    return results


async def _count_orphans(
    target: asyncpg.Connection,
    table: TableInfo,
    fk: Any,
) -> int:
    child = _qual(table)
    parent = qualify(fk.referenced_schema, fk.referenced_table)
    on = " AND ".join(
        f"c.{quote_pg_identifier(s)} = p.{quote_pg_identifier(r)}"
        for s, r in zip(fk.source_columns, fk.referenced_columns, strict=True)
    )
    not_null = " AND ".join(
        f"c.{quote_pg_identifier(s)} IS NOT NULL" for s in fk.source_columns
    )
    query = (
        f"SELECT count(*) FROM {child} c "  # noqa: S608
        f"LEFT JOIN {parent} p ON {on} "
        f"WHERE {not_null} AND p.* IS NULL"
    )
    result = await target.fetchval(query)
    return int(result or 0)


def _unique_groups(table: TableInfo) -> tuple[tuple[str, ...], ...]:
    groups: list[tuple[str, ...]] = []
    if table.primary_key:
        groups.append(table.primary_key)
    groups.extend(table.unique_constraints)
    for index in table.indexes:
        if index.is_unique and index.columns and index.columns not in groups:
            groups.append(index.columns)
    return tuple(dict.fromkeys(groups))


def _qual(table: TableInfo) -> str:
    return table.sql_ref

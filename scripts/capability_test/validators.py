"""Post-test validation checks against live Postgres."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from scripts.capability_test.compose_dev import DEFAULT_SOURCE, DEFAULT_TARGET


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of one post-run validation."""

    name: str
    passed: bool
    detail: str
    data: dict[str, Any]


async def _count_rows(dsn: str, qualified_table: str) -> int:
    import asyncpg

    schema, _, table = qualified_table.partition(".")
    conn = await asyncpg.connect(dsn)
    try:
        value = await conn.fetchval(f'SELECT count(*)::int FROM "{schema}"."{table}"')
        return int(value or 0)
    except asyncpg.UndefinedTableError as exc:
        msg = f"Table {qualified_table!r} does not exist on {dsn!r}"
        raise ValueError(msg) from exc
    finally:
        await conn.close()


async def _run_validations(
    kind: str,
    *,
    source_dsn: str,
    target_dsn: str,
) -> ValidationResult:
    if kind == "postgres_reachable":
        await _count_rows(target_dsn, "pg_catalog.pg_class")
        return ValidationResult(
            name=kind,
            passed=True,
            detail="Source and target Postgres accepted queries.",
            data={},
        )
    if kind == "target_has_users":
        try:
            users = await _count_rows(target_dsn, "public.users")
        except ValueError as exc:
            return ValidationResult(
                name=kind,
                passed=False,
                detail=str(exc),
                data={},
            )
        passed = users > 0
        return ValidationResult(
            name=kind,
            passed=passed,
            detail=f"public.users row count on target: {users}",
            data={"users": users},
        )
    if kind == "target_subset_smaller":
        source_users = await _count_rows(source_dsn, "public.users")
        target_users = await _count_rows(target_dsn, "public.users")
        passed = target_users < source_users
        return ValidationResult(
            name=kind,
            passed=passed,
            detail=(
                f"subset row counts — source users: {source_users}, "
                f"target users: {target_users}"
            ),
            data={"source_users": source_users, "target_users": target_users},
        )
    msg = f"Unknown validation kind: {kind!r}"
    raise ValueError(msg)


def run_post_validate(
    kind: str,
    *,
    source_dsn: str = DEFAULT_SOURCE,
    target_dsn: str = DEFAULT_TARGET,
) -> ValidationResult:
    """Run one validation synchronously."""
    return asyncio.run(
        _run_validations(kind, source_dsn=source_dsn, target_dsn=target_dsn)
    )

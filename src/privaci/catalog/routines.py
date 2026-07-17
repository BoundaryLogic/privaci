"""Function and procedure introspection for schema replication."""

from __future__ import annotations

from collections import defaultdict

import asyncpg

from privaci.catalog.models import FunctionInfo, table_id
from privaci.catalog.queries import (
    FUNCTION_DEPENDENCIES_SQL,
    FUNCTION_TABLE_DEPENDENCIES_SQL,
    FUNCTIONS_SQL,
)


def function_key(schema: str, name: str, identity_args: str) -> str:
    """Return a stable schema-qualified function id for config and deps."""
    base = table_id(schema, name)
    args = identity_args.strip()
    if args:
        return f"{base}({args})"
    return base


async def fetch_functions(conn: asyncpg.Connection) -> tuple[FunctionInfo, ...]:
    """Return user-defined functions/procedures with dependency edges."""
    rows = await conn.fetch(FUNCTIONS_SQL)
    if not rows:
        return ()

    func_deps = await _function_to_function_deps(conn)
    table_deps = await _function_to_table_deps(conn)
    functions: list[FunctionInfo] = []
    for row in rows:
        schema = row["schema_name"]
        name = row["function_name"]
        identity_args = row["identity_args"] or ""
        key = function_key(schema, name, identity_args)
        functions.append(
            FunctionInfo(
                schema_name=schema,
                function_name=name,
                identity_args=identity_args,
                create_sql=row["create_sql"],
                language=row["language"],
                is_elevated=bool(row["is_security_definer"]),
                depends_on_functions=tuple(sorted(func_deps.get(key, ()))),
                depends_on_tables=tuple(sorted(table_deps.get(key, ()))),
            )
        )
    return tuple(sorted(functions, key=lambda item: item.identifier))


async def _function_to_function_deps(
    conn: asyncpg.Connection,
) -> dict[str, set[str]]:
    deps: dict[str, set[str]] = defaultdict(set)
    for row in await conn.fetch(FUNCTION_DEPENDENCIES_SQL):
        source = function_key(
            row["schema_name"],
            row["function_name"],
            row["identity_args"] or "",
        )
        target = function_key(
            row["ref_schema"],
            row["ref_function_name"],
            row["ref_identity_args"] or "",
        )
        if source != target:
            deps[source].add(target)
    return deps


async def _function_to_table_deps(
    conn: asyncpg.Connection,
) -> dict[str, set[str]]:
    deps: dict[str, set[str]] = defaultdict(set)
    for row in await conn.fetch(FUNCTION_TABLE_DEPENDENCIES_SQL):
        source = function_key(
            row["schema_name"],
            row["function_name"],
            row["identity_args"] or "",
        )
        deps[source].add(table_id(row["ref_schema"], row["ref_table"]))
    return deps


def functions_in_dependency_order(
    functions: tuple[FunctionInfo, ...],
) -> list[FunctionInfo]:
    """Return functions ordered so callees appear before callers."""
    by_id = {fn.identifier: fn for fn in functions}
    pending = set(by_id)
    ordered: list[FunctionInfo] = []
    while pending:
        ready = [
            fid
            for fid in sorted(pending)
            if all(dep not in pending for dep in by_id[fid].depends_on_functions)
        ]
        if not ready:
            ordered.extend(by_id[fid] for fid in sorted(pending))
            break
        for fid in ready:
            pending.remove(fid)
            ordered.append(by_id[fid])
    return ordered

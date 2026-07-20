"""Shared DDL execution with consistent PreflightError wrapping."""

from __future__ import annotations

import asyncpg

from privaci.errors import PreflightError

_DEFAULT_CONTEXT = "Replicating schema to the target database"
_DEFAULT_REMEDIATION = "Verify target permissions, required extensions, and retry."


async def execute_ddl(
    conn: asyncpg.Connection,
    sql: str,
    *,
    context: str = _DEFAULT_CONTEXT,
    remediation: str = _DEFAULT_REMEDIATION,
) -> None:
    """Execute one DDL statement; wrap Postgres failures as ``PreflightError``.

    Args:
        conn: Target connection.
        sql: DDL to run (already identifier-safe from catalog emitters).
        context: Operator-facing context for the error block.
        remediation: Operator-facing next step.
    """
    try:
        await conn.execute(sql)
    except asyncpg.PostgresError as exc:
        raise PreflightError(
            context,
            cause=(
                f"DDL execution failed on the target " f"({type(exc).__name__}: {exc})."
            ),
            remediation=remediation,
        ) from exc

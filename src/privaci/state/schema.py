"""Idempotent creation and version-gating of the ``_privaci`` schema.

On every run the engine ensures the schema exists, then records or verifies the
schema version. It refuses to run against a schema written by a newer engine,
satisfying the "Existing schema, incompatible" scenario in the spec.
"""

from __future__ import annotations

import asyncpg

from privaci import __version__
from privaci.errors import StateError
from privaci.state.ddl import (
    DDL_STATEMENTS,
    STATE_SCHEMA_VERSION,
)

_READ_VERSION_SQL = """
SELECT schema_version
FROM _privaci.schema_metadata
WHERE singleton
"""

_WRITE_VERSION_SQL = """
INSERT INTO _privaci.schema_metadata (singleton, schema_version, engine_version)
VALUES (true, $1, $2)
ON CONFLICT (singleton) DO NOTHING
"""


async def ensure_state_schema(conn: asyncpg.Connection) -> None:
    """Create the ``_privaci`` schema if absent and verify its version.

    Idempotent: safe to call on every run. Runs all DDL inside a single
    transaction so a partially created schema is never left behind.

    Args:
        conn: Target-database connection with ``CREATE SCHEMA`` privilege.

    Raises:
        StateError: If the schema was written by a newer engine, or the role
            lacks the required privileges.
    """
    try:
        async with conn.transaction():
            for statement in DDL_STATEMENTS:
                await conn.execute(statement)
            await conn.execute(_WRITE_VERSION_SQL, STATE_SCHEMA_VERSION, __version__)
    except asyncpg.InsufficientPrivilegeError as exc:
        raise _privilege_error() from exc
    except asyncpg.PostgresError as exc:
        raise StateError(
            "Creating the _privaci state schema",
            cause="The state schema could not be created.",
            remediation=("Verify the target role can CREATE SCHEMA and CREATE TABLE."),
        ) from exc

    await _verify_version(conn)


async def _verify_version(conn: asyncpg.Connection) -> None:
    """Refuse to run against a future-version state schema."""
    found = await conn.fetchval(_READ_VERSION_SQL)
    if found is None or found <= STATE_SCHEMA_VERSION:
        return
    raise StateError(
        "Verifying the _privaci state schema version",
        cause=(
            f"target was initialized by a newer engine "
            f"(schema v{found} > supported v{STATE_SCHEMA_VERSION})."
        ),
        remediation=("Pin to the matching engine version or run migrations."),
        exit_code=2,
    )


def _privilege_error() -> StateError:
    """Build the permission-denied error for schema creation."""
    return StateError(
        "Creating the _privaci state schema",
        cause="The target role lacks CREATE privilege on the database.",
        remediation=(
            "Grant CREATE on the target database, e.g. "
            "GRANT CREATE ON DATABASE <db> TO <role>;"
        ),
        exit_code=2,
    )

"""Run-lifecycle writes against ``_privaci.runs``.

One row is inserted at run start with ``status = 'in_progress'`` and updated
exactly once at run end (``succeeded``/``failed``/``interrupted``). The run_id
is a UUIDv7 so rows sort by start time.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import asyncpg

from privaci import __version__
from privaci.errors import StateError
from privaci.state.fingerprints import generate_uuid7
from privaci.state.models import RunIdentity, RunStatus

logger = logging.getLogger(__name__)

_INSERT_RUN_SQL = """
INSERT INTO _privaci.runs (
    run_id, status, engine_version,
    config_hash, salt_fingerprint, source_db_hash
)
VALUES ($1, $2, $3, $4, $5, $6)
"""

_FINISH_RUN_SQL = """
UPDATE _privaci.runs
SET status = $2, ended_at = now(), summary = $3::jsonb
WHERE run_id = $1
"""


async def start_run(conn: asyncpg.Connection, identity: RunIdentity) -> uuid.UUID:
    """Insert a new ``in_progress`` run row and return its id.

    Args:
        conn: Target-database connection.
        identity: Config/salt/source fingerprints for this run.

    Returns:
        The generated UUIDv7 run identifier.

    Raises:
        StateError: If the run row cannot be inserted.
    """
    run_id = generate_uuid7()
    try:
        await conn.execute(
            _INSERT_RUN_SQL,
            run_id,
            RunStatus.IN_PROGRESS.value,
            __version__,
            identity.config_hash,
            identity.salt_fingerprint,
            identity.source_db_hash,
        )
    except asyncpg.PostgresError as exc:
        raise StateError(
            "Recording run start in _privaci.runs",
            cause="The run row could not be inserted.",
            remediation="Ensure the _privaci schema exists and is writable.",
        ) from exc
    logger.info("Run started", extra={"run_id": str(run_id)})
    return run_id


async def finish_run(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
    status: RunStatus,
    summary: dict[str, Any] | None = None,
) -> None:
    """Mark a run terminal and stamp ``ended_at`` and ``summary``.

    Args:
        conn: Target-database connection.
        run_id: The run to finalize.
        status: A terminal status (succeeded/failed/interrupted).
        summary: Optional aggregate counts serialized to ``summary`` jsonb.

    Raises:
        StateError: If ``status`` is not terminal, or the update fails.
    """
    if status is RunStatus.IN_PROGRESS:
        raise StateError(
            "Finalizing a run in _privaci.runs",
            cause="A terminal status is required to finish a run.",
            remediation="Pass succeeded, failed, or interrupted.",
        )
    payload = json.dumps(summary) if summary is not None else None
    try:
        await conn.execute(_FINISH_RUN_SQL, run_id, status.value, payload)
    except asyncpg.PostgresError as exc:
        raise StateError(
            "Recording run completion in _privaci.runs",
            cause="The run row could not be updated.",
            remediation="Ensure the run row exists and is writable.",
        ) from exc
    logger.info(
        "Run finished",
        extra={"run_id": str(run_id), "status": status.value},
    )

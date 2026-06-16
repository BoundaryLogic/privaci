"""Resume gate and checkpoint loading for interrupted runs."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import NoReturn

import asyncpg

from privaci.catalog.models import table_id
from privaci.errors import PreflightError, StateError
from privaci.state.models import CheckpointStatus, RunIdentity, RunStatus
from privaci.stream.coerce import parse_text_cursor

logger = logging.getLogger(__name__)

# A run is resumable while it has not reached a successful terminal state. A
# clean interrupt (SIGINT/SIGTERM) records ``interrupted`` and a crash records
# ``failed``; both leave durable checkpoints, so the gate must accept them
# alongside an ``in_progress`` row left by a hard kill.
_RESUMABLE_STATUS_VALUES = [
    RunStatus.IN_PROGRESS.value,
    RunStatus.INTERRUPTED.value,
    RunStatus.FAILED.value,
]

_FIND_RESUMABLE_RUN_SQL = """
SELECT run_id
FROM _privaci.runs
WHERE status = ANY($1::text[])
  AND config_hash = $2
  AND source_db_hash = $3
  AND salt_fingerprint = $4
ORDER BY started_at DESC
LIMIT 1
"""

_LATEST_RESUMABLE_RUN_SQL = """
SELECT config_hash, source_db_hash, salt_fingerprint
FROM _privaci.runs
WHERE status = ANY($1::text[])
ORDER BY started_at DESC
LIMIT 1
"""

_REOPEN_RUN_SQL = """
UPDATE _privaci.runs
SET status = $2, ended_at = NULL
WHERE run_id = $1
"""

_LOAD_CHECKPOINTS_SQL = """
SELECT schema_name, table_name, status, last_pk_value, rows_processed
FROM _privaci.table_checkpoints
WHERE run_id = $1
"""


@dataclass(frozen=True, slots=True)
class TableCheckpoint:
    """Per-table progress loaded from ``_privaci.table_checkpoints``."""

    schema_name: str
    table_name: str
    status: CheckpointStatus
    last_pk_value: str | None
    rows_processed: int

    @property
    def identifier(self) -> str:
        return table_id(self.schema_name, self.table_name)


async def find_resumable_run(
    conn: asyncpg.Connection,
    identity: RunIdentity,
) -> uuid.UUID | None:
    """Return the latest resumable run id matching ``identity``, if any.

    A run is resumable when its status is ``in_progress``, ``interrupted``, or
    ``failed`` (see :data:`_RESUMABLE_STATUS_VALUES`) and every identity field
    matches the current config, source, and salt.
    """
    row = await conn.fetchrow(
        _FIND_RESUMABLE_RUN_SQL,
        _RESUMABLE_STATUS_VALUES,
        identity.config_hash,
        identity.source_db_hash,
        identity.salt_fingerprint,
    )
    if row is None:
        return None
    run_id: uuid.UUID = row["run_id"]
    return run_id


async def load_checkpoints(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
) -> dict[str, TableCheckpoint]:
    """Load all checkpoint rows for ``run_id`` keyed by table identifier."""
    rows = await conn.fetch(_LOAD_CHECKPOINTS_SQL, run_id)
    return {
        table_id(row["schema_name"], row["table_name"]): TableCheckpoint(
            schema_name=row["schema_name"],
            table_name=row["table_name"],
            status=CheckpointStatus(row["status"]),
            last_pk_value=row["last_pk_value"],
            rows_processed=int(row["rows_processed"]),
        )
        for row in rows
    }


async def resolve_resumable_run(
    conn: asyncpg.Connection,
    identity: RunIdentity,
) -> uuid.UUID:
    """Return the resumable run id for ``identity`` without mutating any row.

    This is the read-only half of the resume gate: it validates that a matching
    run exists but does not re-open it. Callers can run further read-only checks
    (e.g. schema-drift validation) before committing to the resume.

    Raises:
        PreflightError: When no resumable run matches, with a cause that
            distinguishes "no run" from config, source, or salt drift.
    """
    run_id = await find_resumable_run(conn, identity)
    if run_id is None:
        await _raise_no_resumable_run(conn, identity)
    return run_id


async def reopen_resumable_run(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
) -> dict[str, TableCheckpoint]:
    """Re-open a resolved run and return its checkpoints.

    Resets the run status to ``in_progress`` and clears ``ended_at`` atomically
    with the checkpoint load. Call only after every read-only resume check has
    passed, so a failed check never leaves the run flipped to ``in_progress``.
    """
    async with conn.transaction():
        await conn.execute(_REOPEN_RUN_SQL, run_id, RunStatus.IN_PROGRESS.value)
        checkpoints = await load_checkpoints(conn, run_id)
    logger.info(
        "Resuming run",
        extra={"run_id": str(run_id), "tables_with_progress": len(checkpoints)},
    )
    return checkpoints


async def require_resumable_run(
    conn: asyncpg.Connection,
    identity: RunIdentity,
) -> tuple[uuid.UUID, dict[str, TableCheckpoint]]:
    """Validate the resume gate, re-open the run, and return its checkpoints.

    Convenience wrapper over :func:`resolve_resumable_run` and
    :func:`reopen_resumable_run` for callers that perform no intervening checks.

    Raises:
        PreflightError: When no resumable run matches, with a cause that
            distinguishes "no run" from config, source, or salt drift.
    """
    run_id = await resolve_resumable_run(conn, identity)
    checkpoints = await reopen_resumable_run(conn, run_id)
    return run_id, checkpoints


async def _raise_no_resumable_run(
    conn: asyncpg.Connection,
    identity: RunIdentity,
) -> NoReturn:
    """Raise a :class:`PreflightError` explaining why no run could be resumed."""
    latest = await conn.fetchrow(_LATEST_RESUMABLE_RUN_SQL, _RESUMABLE_STATUS_VALUES)
    cause, remediation = _diagnose_resume_gap(latest, identity)
    raise PreflightError(
        "Validating resume prerequisites",
        cause=cause,
        remediation=remediation,
    )


def _diagnose_resume_gap(
    latest: asyncpg.Record | None,
    identity: RunIdentity,
) -> tuple[str, str]:
    """Return a (cause, remediation) pair pinpointing the resume mismatch."""
    if latest is None:
        return (
            "No incomplete run was found in the target database.",
            "Start a fresh run with `privaci run`.",
        )
    if latest["config_hash"] != identity.config_hash:
        return (
            "The mask-rules config changed since the incomplete run.",
            "Restore the original mask-rules.yaml, or start a fresh run.",
        )
    if latest["source_db_hash"] != identity.source_db_hash:
        return (
            "The source database identity changed since the incomplete run.",
            "Point --source at the original database, or start a fresh run.",
        )
    if latest["salt_fingerprint"] != identity.salt_fingerprint:
        return (
            "The anonymization salt changed since the incomplete run.",
            "Restore the original ANONYMIZATION_SALT, or start a fresh run.",
        )
    return (
        "No incomplete run matches the current config, source, and salt.",
        "Start a fresh run with `privaci run`.",
    )


def parse_checkpoint_cursor(
    raw: str | None,
    *,
    data_type: str,
) -> object | None:
    """Convert a stored checkpoint cursor back to a Python value."""
    if raw is None:
        return None
    return parse_text_cursor(raw, data_type=data_type)


def ensure_table_resumable(
    table_pk_columns: tuple[str, ...], checkpoint: TableCheckpoint
) -> None:
    """Reject resume when a table lacks a single-column PK but has partial progress."""
    if len(table_pk_columns) == 1:
        return
    if checkpoint.status is CheckpointStatus.DONE:
        return
    if checkpoint.rows_processed == 0:
        return
    raise StateError(
        "Resuming a table without a single-column primary key",
        cause=(
            f"Table {checkpoint.identifier} has partial progress but no resumable "
            "cursor."
        ),
        remediation=(
            "Truncate the partial table data and restart with `privaci run "
            "--force-restart`, or add a single-column primary key."
        ),
    )

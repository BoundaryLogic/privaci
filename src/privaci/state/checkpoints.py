"""Per-table checkpoint writes against ``_privaci.table_checkpoints``.

The checkpoint upsert is designed to run inside the same transaction as the
batch data write, so a committed batch and its checkpoint advance atomically.
Callers therefore pass an already-open connection/transaction; these helpers
never open their own transaction.
"""

from __future__ import annotations

import uuid

import asyncpg

from privaci.errors import StateError
from privaci.state.models import CheckpointStatus

_UPSERT_CHECKPOINT_SQL = """
INSERT INTO _privaci.table_checkpoints (
    run_id, schema_name, table_name, status,
    last_pk_value, rows_processed, last_update_at
)
VALUES ($1, $2, $3, $4, $5, $6, now())
ON CONFLICT (run_id, schema_name, table_name) DO UPDATE
SET status = EXCLUDED.status,
    last_pk_value = EXCLUDED.last_pk_value,
    rows_processed = _privaci.table_checkpoints.rows_processed
        + EXCLUDED.rows_processed,
    last_update_at = now()
"""

_MARK_DONE_SQL = """
UPDATE _privaci.table_checkpoints
SET status = $4, last_update_at = now()
WHERE run_id = $1 AND schema_name = $2 AND table_name = $3
"""


async def write_checkpoint(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
    schema_name: str,
    table_name: str,
    *,
    last_pk_value: str | None,
    rows_in_batch: int,
    status: CheckpointStatus = CheckpointStatus.IN_PROGRESS,
) -> None:
    """Advance a table's checkpoint by one committed batch.

    Raises:
        StateError: If the checkpoint row cannot be written.
    """
    try:
        await conn.execute(
            _UPSERT_CHECKPOINT_SQL,
            run_id,
            schema_name,
            table_name,
            status.value,
            last_pk_value,
            rows_in_batch,
        )
    except asyncpg.PostgresError as exc:
        raise StateError(
            "Writing a table checkpoint",
            cause="The checkpoint row could not be written.",
            remediation="Ensure the _privaci schema exists and the run row exists.",
        ) from exc


async def mark_table_done(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
    schema_name: str,
    table_name: str,
    *,
    status: CheckpointStatus = CheckpointStatus.DONE,
) -> None:
    """Set a table's terminal checkpoint status.

    Raises:
        StateError: If the checkpoint row cannot be updated.
    """
    table_ref = f"{schema_name}.{table_name}"
    try:
        result = await conn.execute(
            _MARK_DONE_SQL, run_id, schema_name, table_name, status.value
        )
    except asyncpg.PostgresError as exc:
        raise StateError(
            "Finalizing a table checkpoint",
            cause="The checkpoint row could not be updated.",
            remediation="Ensure the checkpoint row exists.",
        ) from exc
    if int(result.split()[-1]) == 0:
        raise StateError(
            "Finalizing a table checkpoint",
            cause=f"No checkpoint row matched table {table_ref!r}.",
            remediation=(
                "Ensure streaming wrote an initial checkpoint before marking done."
            ),
        )

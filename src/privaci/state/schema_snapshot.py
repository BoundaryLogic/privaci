"""Persist and load source-schema snapshots on ``_privaci.runs``.

Serialize helpers stay in :mod:`privaci.catalog.snapshot`; this module owns the
SQL boundary so catalog does not depend on run status or state DDL.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import asyncpg

from privaci.catalog.models import CatalogResult
from privaci.catalog.snapshot import (
    canonical_snapshot_json,
    normalize_snapshot_for_resume_compare,
)
from privaci.errors import PreflightError, StateError
from privaci.state.models import RunStatus

_LOAD_LATEST_SNAPSHOT_SQL = """
SELECT source_schema_snapshot
FROM _privaci.runs
WHERE source_db_hash = $1
  AND status = $2
  AND source_schema_snapshot IS NOT NULL
  AND ($3::uuid IS NULL OR run_id != $3)
ORDER BY started_at DESC
LIMIT 1
"""

_LOAD_RUN_SNAPSHOT_SQL = """
SELECT source_schema_snapshot
FROM _privaci.runs
WHERE run_id = $1
"""


def snapshot_payload(raw: object) -> dict[str, Any] | None:
    """Normalize a jsonb column value to a dict."""
    if raw is None:
        return None
    if isinstance(raw, str):
        parsed: dict[str, Any] = json.loads(raw)
        return parsed
    if isinstance(raw, dict):
        return dict(raw)
    msg = f"unexpected snapshot payload type: {type(raw).__name__}"
    raise StateError(
        "Loading source schema snapshot",
        cause=msg,
        remediation="Re-run with a fresh `privaci run`.",
    )


async def validate_resume_schema_snapshot(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
    catalog: CatalogResult,
    *,
    schema_mode: str = "replicate",
) -> None:
    """Fail resume when the schema snapshot is missing or drifted.

    In ``schema_mode: replicate``, a missing snapshot means schema cloning did
    not finish; resume must not stream into a partial target.

    Raises:
        PreflightError: When the snapshot is absent (replicate), or exists and
            differs from ``catalog``.
    """
    row = await conn.fetchrow(_LOAD_RUN_SNAPSHOT_SQL, run_id)
    stored = None if row is None else snapshot_payload(row["source_schema_snapshot"])
    if stored is None:
        if schema_mode != "replicate":
            return
        raise PreflightError(
            "Validating resume prerequisites",
            cause=(
                "The incomplete run has no persisted source schema snapshot "
                "(schema replication likely did not finish)."
            ),
            remediation=(
                "Start a fresh run with `privaci run --force-restart` "
                "(requires on_existing_data: truncate or drop_create), "
                "or rebuild the target and run again."
            ),
        )
    current = json.loads(canonical_snapshot_json(catalog))
    if normalize_snapshot_for_resume_compare(
        stored
    ) == normalize_snapshot_for_resume_compare(current):
        return
    raise PreflightError(
        "Validating resume prerequisites",
        cause="The source database schema changed since the incomplete run.",
        remediation=(
            "Restore the original source schema, truncate affected target tables, "
            "and start a fresh run with `privaci run --force-restart`."
        ),
    )


async def load_latest_schema_snapshot(
    conn: asyncpg.Connection,
    *,
    source_db_hash: str,
    exclude_run_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    """Load the newest succeeded run snapshot for one source database."""
    row = await conn.fetchrow(
        _LOAD_LATEST_SNAPSHOT_SQL,
        source_db_hash,
        RunStatus.SUCCEEDED.value,
        exclude_run_id,
    )
    if row is None:
        return None
    return snapshot_payload(row["source_schema_snapshot"])


async def persist_source_schema_snapshot(
    conn: asyncpg.Connection,
    run_id: uuid.UUID,
    catalog: CatalogResult,
) -> None:
    """Write the canonical snapshot JSON to ``_privaci.runs``.

    Raises:
        StateError: When the snapshot cannot be written.
    """
    snapshot = canonical_snapshot_json(catalog)
    try:
        await conn.execute(
            """
            UPDATE _privaci.runs
            SET source_schema_snapshot = $2::jsonb
            WHERE run_id = $1
            """,
            run_id,
            snapshot,
        )
    except asyncpg.PostgresError as exc:
        raise StateError(
            "Persisting source schema snapshot",
            cause="Could not write source_schema_snapshot to _privaci.runs.",
            remediation=(
                "Ensure the _privaci schema exists and the run row was created."
            ),
        ) from exc

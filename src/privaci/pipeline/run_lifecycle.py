"""Run open / stream / close seam shared by CLI fresh and resume paths.

Wraps identity, UsageMeter register/final, schema prepare, and dual
audit+emit recording so fresh and resume share one policy surface.
"""

from __future__ import annotations

import time
import uuid

import asyncpg

from privaci.autodetect import build_detection
from privaci.catalog.models import CatalogResult
from privaci.config.models import Config
from privaci.contracts import load_plugins
from privaci.observability import Event, emit
from privaci.pipeline.lifecycle import (
    emit_run_end,
    initialize_fresh_run,
    prepare_target_schema,
    record_event,
)
from privaci.pipeline.object_audits import (
    emit_created_object_audit,
    emit_definition_only_audit,
)
from privaci.pipeline.streaming import stream_all_tables
from privaci.schema.post_data import apply_post_data_ddl
from privaci.state import (
    AuditWriter,
    RunIdentity,
    RunStatus,
    TableCheckpoint,
    config_hash,
    finish_run,
    salt_fingerprint,
    source_db_hash,
    start_run,
)

__all__ = [
    "close_aborted_run",
    "emit_run_end",
    "open_run",
    "record_event",
    "stream_and_finish",
]


def notify_meter_run_start(source_db_hash_value: str, run_id: uuid.UUID) -> None:
    """Invoke the ``UsageMeter`` plugin contract after the run row exists."""
    plugins = load_plugins()
    plugins.usage_meter.register_run(
        source_db_hash=source_db_hash_value,
        run_id=run_id,
    )


def notify_meter_run_end(source_db_hash_value: str, run_id: uuid.UUID) -> None:
    """Finalize ``UsageMeter`` plugin contract after a terminal run status."""
    plugins = load_plugins()
    plugins.usage_meter.final_meter(
        source_db_hash=source_db_hash_value,
        run_id=run_id,
    )


async def open_run(
    target: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    *,
    source_dsn: str,
    salt: str,
    resume_run_id: uuid.UUID | None,
    audit_enabled: bool,
) -> tuple[uuid.UUID, AuditWriter]:
    """Start or resume a run and prepare target schema.

    Fresh runs register the UsageMeter with the persisted ``run_id``. Resume
    does not re-register; it re-applies idempotent schema prepare.
    """
    if resume_run_id is not None:
        audit = AuditWriter(resume_run_id, enabled=audit_enabled)
        await prepare_target_schema(target, catalog, config, resume_run_id, audit)
        return resume_run_id, audit
    identity = RunIdentity(
        config_hash=config_hash(config),
        salt_fingerprint=salt_fingerprint(salt),
        source_db_hash=source_db_hash(source_dsn),
    )
    run_id = await start_run(target, identity)
    notify_meter_run_start(identity.source_db_hash, run_id)
    audit = await initialize_fresh_run(
        target,
        catalog,
        config,
        source_dsn=source_dsn,
        salt=salt,
        run_id=run_id,
        audit_enabled=audit_enabled,
    )
    return run_id, audit


async def stream_and_finish(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    salt: str,
    run_id: uuid.UUID,
    audit: AuditWriter,
    started_at: float,
    *,
    source_dsn: str,
    checkpoints: dict[str, TableCheckpoint] | None,
    pseudonym_key: str | None = None,
) -> tuple[int, int, dict[str, int], int]:
    """Stream tables, mark the run succeeded, and finalize the UsageMeter."""
    detection = build_detection(config, catalog)
    tables_done, total_rows, counts, total_bytes = await stream_all_tables(
        source,
        target,
        catalog,
        config,
        salt,
        run_id,
        audit,
        detection,
        checkpoints=checkpoints or {},
        pseudonym_key=pseudonym_key,
    )
    await _apply_post_data_and_audit(target, catalog, config, audit)
    duration_s = time.monotonic() - started_at
    await finish_run(
        target,
        run_id,
        RunStatus.SUCCEEDED,
        summary={
            "tables": tables_done,
            "rows": total_rows,
            "bytes": total_bytes,
            "duration_s": round(duration_s, 3),
        },
    )
    notify_meter_run_end(source_db_hash(source_dsn), run_id)
    emit_run_end(
        run_id,
        RunStatus.SUCCEEDED.value,
        started_at,
        tables_processed=tables_done,
        rows_processed=total_rows,
        errors=0,
    )
    return tables_done, total_rows, counts, total_bytes


async def _apply_post_data_and_audit(
    target: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    audit: AuditWriter,
) -> None:
    """Run post-data DDL and audit created/refreshed objects before SUCCEEDED."""
    created, refreshed = await apply_post_data_ddl(target, catalog, config)
    for obj in created:
        if obj.definition_only:
            await emit_definition_only_audit(target, audit, obj)
        else:
            await emit_created_object_audit(target, audit, obj)
    if refreshed:
        await audit.mark_definition_only_refreshed(target, refreshed)
        for schema_name, object_name in refreshed:
            emit(
                Event.DEFINITION_ONLY_OBJECT,
                schema_name=schema_name,
                object_name=object_name,
                kind="materialized_view",
                contents_copied=False,
                refreshed=True,
                ddl_phase="post-data",
            )


async def close_aborted_run(
    target: asyncpg.Connection,
    run_id: uuid.UUID | None,
    started_at: float,
    status: RunStatus,
    *,
    source_dsn: str | None = None,
    errors: int = 1,
) -> None:
    """Mark an interrupted or failed run and finalize metering when terminal.

    ``INTERRUPTED`` runs are resumable: finish the run row but do **not** call
    ``final_meter`` so a later successful resume can finalize once. ``FAILED``
    (and other non-interrupted abort statuses) finalize the UsageMeter.
    """
    if run_id is None:
        return
    await finish_run(
        target,
        run_id,
        status,
        summary={"errors": errors},
    )
    if source_dsn is not None and status != RunStatus.INTERRUPTED:
        notify_meter_run_end(source_db_hash(source_dsn), run_id)
    emit_run_end(
        run_id,
        status.value,
        started_at,
        tables_processed=0,
        rows_processed=0,
        errors=errors,
    )

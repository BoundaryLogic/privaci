"""Programmatic end-to-end masking pipeline (pre-CLI ``privaci run``)."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import asyncpg

from privaci.autodetect import build_detection
from privaci.catalog import introspect_catalog
from privaci.catalog.models import CatalogResult
from privaci.config.models import Config
from privaci.contracts import load_plugins
from privaci.errors import RunInterruptedError
from privaci.pipeline.lifecycle import emit_run_end, initialize_fresh_run
from privaci.pipeline.streaming import stream_all_tables
from privaci.state import (
    AuditWriter,
    RunIdentity,
    RunStatus,
    TableCheckpoint,
    config_hash,
    ensure_state_schema,
    finish_run,
    salt_fingerprint,
    source_db_hash,
    start_run,
)


@dataclass(frozen=True, slots=True)
class PipelineSummary:
    """Aggregate counts from one masking pipeline run."""

    run_id: uuid.UUID
    tables_processed: int = 0
    rows_processed: int = 0
    bytes_processed: int = 0
    table_row_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class PipelineSession:
    """Mutable run state shared across pipeline phases for abort handling."""

    run_id: uuid.UUID | None = None


async def run_masking_pipeline(
    source_dsn: str,
    target_dsn: str,
    config: Config,
    salt: str,
    *,
    audit_enabled: bool | None = None,
    catalog: CatalogResult | None = None,
    resume_run_id: uuid.UUID | None = None,
    checkpoints: dict[str, TableCheckpoint] | None = None,
    pseudonym_key: str | None = None,
) -> PipelineSummary:
    """Introspect, replicate schema, and stream masked rows to the target."""
    return await _execute_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        salt,
        audit_enabled=audit_enabled,
        catalog=catalog,
        resume_run_id=resume_run_id,
        checkpoints=checkpoints,
        pseudonym_key=pseudonym_key,
    )


async def _execute_masking_pipeline(
    source_dsn: str,
    target_dsn: str,
    config: Config,
    salt: str,
    *,
    audit_enabled: bool | None,
    catalog: CatalogResult | None,
    resume_run_id: uuid.UUID | None,
    checkpoints: dict[str, TableCheckpoint] | None,
    pseudonym_key: str | None = None,
) -> PipelineSummary:
    started_at = time.monotonic()
    session = PipelineSession(run_id=resume_run_id)
    resolved_audit = config.audit_log if audit_enabled is None else audit_enabled
    async with _pipeline_db_connections(source_dsn, target_dsn) as (source, target):
        try:
            return await _run_connected_pipeline(
                source,
                target,
                source_dsn,
                config,
                salt,
                resolved_audit,
                started_at,
                catalog=catalog,
                checkpoints=checkpoints,
                session=session,
                pseudonym_key=pseudonym_key,
            )
        except RunInterruptedError:
            await _finish_aborted_run(
                target, session.run_id, started_at, RunStatus.INTERRUPTED
            )
            raise
        except Exception:
            await _finish_aborted_run(
                target, session.run_id, started_at, RunStatus.FAILED, errors=1
            )
            raise


@asynccontextmanager
async def _pipeline_db_connections(
    source_dsn: str,
    target_dsn: str,
) -> AsyncIterator[tuple[asyncpg.Connection, asyncpg.Connection]]:
    source = await asyncpg.connect(source_dsn)
    target = await asyncpg.connect(target_dsn)
    try:
        yield source, target
    finally:
        await source.close()
        await target.close()


async def _run_connected_pipeline(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    source_dsn: str,
    config: Config,
    salt: str,
    audit_enabled: bool,
    started_at: float,
    *,
    catalog: CatalogResult | None,
    checkpoints: dict[str, TableCheckpoint] | None,
    session: PipelineSession,
    pseudonym_key: str | None = None,
) -> PipelineSummary:
    if catalog is None:
        catalog = await introspect_catalog(
            source, implied_fk_ignore=frozenset(config.implied_fk_ignore)
        )
    await ensure_state_schema(target)
    run_id, audit = await _open_run(
        target,
        catalog,
        config,
        source_dsn=source_dsn,
        salt=salt,
        resume_run_id=session.run_id,
        audit_enabled=audit_enabled,
    )
    session.run_id = run_id
    return await _stream_to_summary(
        source,
        target,
        catalog,
        config,
        salt,
        run_id,
        audit,
        started_at,
        source_dsn=source_dsn,
        checkpoints=checkpoints,
        pseudonym_key=pseudonym_key,
    )


async def _open_run(
    target: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    *,
    source_dsn: str,
    salt: str,
    resume_run_id: uuid.UUID | None,
    audit_enabled: bool,
) -> tuple[uuid.UUID, AuditWriter]:
    if resume_run_id is not None:
        return resume_run_id, AuditWriter(resume_run_id, enabled=audit_enabled)
    identity = RunIdentity(
        config_hash=config_hash(config),
        salt_fingerprint=salt_fingerprint(salt),
        source_db_hash=source_db_hash(source_dsn),
    )
    _notify_meter_run_start(identity.source_db_hash)
    run_id = await start_run(target, identity)
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


def _notify_meter_run_start(source_db_hash: str) -> None:
    """Invoke the ``UsageMeter`` plugin contract before persisting a new run row."""
    plugins = load_plugins()
    plugins.usage_meter.register_run(
        source_db_hash=source_db_hash,
        run_id=uuid.uuid4(),
    )


def _notify_meter_run_end(source_db_hash: str, run_id: uuid.UUID) -> None:
    """Finalize ``UsageMeter`` plugin contract after a terminal run status."""
    plugins = load_plugins()
    plugins.usage_meter.final_meter(source_db_hash=source_db_hash, run_id=run_id)


async def _stream_to_summary(
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
) -> PipelineSummary:
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
    summary = PipelineSummary(
        run_id=run_id,
        tables_processed=tables_done,
        rows_processed=total_rows,
        bytes_processed=total_bytes,
        table_row_counts=counts,
    )
    await _finish_successful_run(
        target,
        run_id,
        started_at,
        summary,
        source_db_hash_value=source_db_hash(source_dsn),
    )
    return summary


async def _finish_successful_run(
    target: asyncpg.Connection,
    run_id: uuid.UUID,
    started_at: float,
    summary: PipelineSummary,
    *,
    source_db_hash_value: str,
) -> None:
    await finish_run(
        target,
        run_id,
        RunStatus.SUCCEEDED,
        summary={
            "tables": summary.tables_processed,
            "rows": summary.rows_processed,
            "bytes": summary.bytes_processed,
        },
    )
    _notify_meter_run_end(source_db_hash_value, run_id)
    emit_run_end(
        run_id,
        RunStatus.SUCCEEDED.value,
        started_at,
        tables_processed=summary.tables_processed,
        rows_processed=summary.rows_processed,
        errors=0,
    )


async def _finish_aborted_run(
    target: asyncpg.Connection,
    run_id: uuid.UUID | None,
    started_at: float,
    status: RunStatus,
    *,
    errors: int = 0,
) -> None:
    if run_id is None:
        return
    await finish_run(target, run_id, status)
    emit_run_end(
        run_id,
        status.value,
        started_at,
        tables_processed=0,
        rows_processed=0,
        errors=errors,
    )

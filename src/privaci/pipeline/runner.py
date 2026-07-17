"""Programmatic end-to-end masking pipeline (pre-CLI ``privaci run``)."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import asyncpg

from privaci.catalog import introspect_catalog
from privaci.catalog.models import CatalogResult
from privaci.config.models import Config
from privaci.errors import RunInterruptedError
from privaci.pipeline.run_lifecycle import (
    close_aborted_run,
    open_run,
    stream_and_finish,
)
from privaci.state import (
    RunStatus,
    TableCheckpoint,
    ensure_state_schema,
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
    source_dsn: str | None = None


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
    session = PipelineSession(run_id=resume_run_id, source_dsn=source_dsn)
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
            await close_aborted_run(
                target,
                session.run_id,
                started_at,
                RunStatus.INTERRUPTED,
                source_dsn=session.source_dsn,
                errors=0,
            )
            raise
        except Exception:
            await close_aborted_run(
                target,
                session.run_id,
                started_at,
                RunStatus.FAILED,
                source_dsn=session.source_dsn,
                errors=1,
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
    run_id, audit = await open_run(
        target,
        catalog,
        config,
        source_dsn=source_dsn,
        salt=salt,
        resume_run_id=session.run_id,
        audit_enabled=audit_enabled,
    )
    session.run_id = run_id
    tables_done, total_rows, counts, total_bytes = await stream_and_finish(
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
    return PipelineSummary(
        run_id=run_id,
        tables_processed=tables_done,
        rows_processed=total_rows,
        bytes_processed=total_bytes,
        table_row_counts=counts,
    )

"""Fresh-run setup and pipeline lifecycle events."""

from __future__ import annotations

import logging
import time
import uuid

import asyncpg

from privaci import __version__
from privaci.autodetect import build_detection
from privaci.catalog.audit_skipped import iter_skipped_object_audits
from privaci.catalog.models import CatalogResult
from privaci.catalog.snapshot import (
    find_new_partition_children,
    load_latest_schema_snapshot,
    persist_source_schema_snapshot,
)
from privaci.config.models import Config
from privaci.errors import StateError
from privaci.observability import Event, emit
from privaci.pipeline.table_plan import table_strategy
from privaci.preflight.passthrough_copy import verify_passthrough_copy_policy
from privaci.preflight.target import ensure_target_ready
from privaci.schema import replicate_schema
from privaci.schema.assume_existing import (
    AssumeExistingValidation,
    raise_validation_failed,
    validate_assume_existing,
    validation_failed_payload,
    validation_ok_payload,
)
from privaci.state import (
    AuditWriter,
    RunIdentity,
    config_hash,
    salt_fingerprint,
    source_db_hash,
)
from privaci.state.models import AuditLevel, EventType

logger = logging.getLogger(__name__)


def streamable_table_count(catalog: CatalogResult, config: Config) -> int:
    """Count tables replicated to the target (excluding ``exclude`` strategy)."""
    return sum(
        1
        for table in catalog.tables.values()
        if table_strategy(table, config) != "exclude"
    )


def emit_catalog_warning_events(catalog: CatalogResult) -> None:
    """Emit stdout warning events for catalog-detected FK risks."""
    for warning in catalog.warnings:
        if warning.code == "polymorphic_fk_warning":
            emit(
                Event.POLYMORPHIC_FK_WARNING,
                table_id=warning.table_id,
                message=warning.message,
            )
        elif warning.code == "implied_fk_warning":
            emit(
                Event.IMPLIED_FK_WARNING,
                source_column_path=warning.table_id,
                message=warning.message,
            )


def emit_run_end(
    run_id: uuid.UUID,
    status: str,
    started_at: float,
    *,
    tables_processed: int,
    rows_processed: int,
    errors: int,
) -> None:
    """Emit the terminal ``run.end`` event with duration and counts."""
    emit(
        Event.RUN_END,
        run_id=run_id,
        status=status,
        duration_ms=round((time.monotonic() - started_at) * 1000, 3),
        tables_processed=tables_processed,
        rows_processed=rows_processed,
        errors=errors,
    )


async def initialize_fresh_run(
    target: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    *,
    source_dsn: str,
    salt: str,
    run_id: uuid.UUID,
    audit_enabled: bool,
) -> AuditWriter:
    """Replicate schema, audit catalog objects, and persist the snapshot."""
    identity = RunIdentity(
        config_hash=config_hash(config),
        salt_fingerprint=salt_fingerprint(salt),
        source_db_hash=source_db_hash(source_dsn),
    )
    audit = AuditWriter(run_id, enabled=audit_enabled)
    previous_snapshot = await _replicate_and_emit_start(
        target, catalog, config, run_id, identity, audit
    )
    emit_catalog_warning_events(catalog)
    await _audit_catalog_objects(
        target, audit, catalog, previous_snapshot, config=config
    )
    await persist_source_schema_snapshot(target, run_id, catalog)
    return audit


async def _replicate_and_emit_start(
    target: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    run_id: uuid.UUID,
    identity: RunIdentity,
    audit: AuditWriter,
) -> dict[str, object] | None:
    emit(
        Event.RUN_START,
        run_id=run_id,
        engine_version=__version__,
        config_hash=identity.config_hash,
        salt_fingerprint=identity.salt_fingerprint,
        source_db_hash=identity.source_db_hash,
        commercial_layer_present=False,
    )
    previous_snapshot = await load_latest_schema_snapshot(
        target,
        source_db_hash=identity.source_db_hash,
        exclude_run_id=run_id,
    )
    if config.schema_mode == "assume_existing":
        await _prepare_assume_existing(target, audit, catalog, config)
        return previous_snapshot
    await replicate_schema(target, catalog, config)
    emit(
        Event.SCHEMA_CLONED,
        run_id=run_id,
        tables_created=streamable_table_count(catalog, config),
        schemas_created=len({t.schema_name for t in catalog.tables.values()}),
    )
    return previous_snapshot


async def _prepare_assume_existing(
    target: asyncpg.Connection,
    audit: AuditWriter,
    catalog: CatalogResult,
    config: Config,
) -> None:
    """Validate, audit, and prepare a customer-managed target before streaming."""
    validation = await validate_assume_existing(target, catalog, config)
    if not validation.is_ok:
        await _write_validation_failure(target, audit, validation, config)
        raise_validation_failed(validation)
    await audit.write(
        target,
        EventType.SCHEMA_VALIDATED,
        payload=validation_ok_payload(
            validation, passthrough_copy=config.passthrough_copy
        ),
    )
    detection = build_detection(config, catalog)
    await verify_passthrough_copy_policy(target, catalog, config, detection)
    await ensure_target_ready(target, config, catalog)


async def _write_validation_failure(
    target: asyncpg.Connection,
    audit: AuditWriter,
    validation: AssumeExistingValidation,
    config: Config,
) -> None:
    """Best-effort audit a refusal without hiding the schema mismatch."""
    try:
        await audit.write(
            target,
            EventType.SCHEMA_VALIDATION_FAILED,
            level=AuditLevel.ERROR,
            payload=validation_failed_payload(
                validation, passthrough_copy=config.passthrough_copy
            ),
        )
    except StateError:
        logger.exception(
            "Could not persist schema validation failure audit",
            extra={"mismatch_count": len(validation.mismatches)},
        )


async def _audit_catalog_objects(
    target: asyncpg.Connection,
    audit: AuditWriter,
    catalog: CatalogResult,
    previous_snapshot: dict[str, object] | None,
    *,
    config: Config,
) -> None:
    if config.schema_mode == "assume_existing":
        return
    for child in find_new_partition_children(previous_snapshot, catalog):
        await audit.write(
            target,
            EventType.NEW_TABLE,
            schema_name=child.schema_name,
            table_name=child.table_name,
            payload={"reason": "new_partition"},
        )
        emit(
            Event.NEW_TABLE,
            schema_name=child.schema_name,
            table_name=child.table_name,
            reason="new_partition",
        )
    for schema_name, table_name, payload in iter_skipped_object_audits(catalog):
        await audit.write(
            target,
            EventType.SKIPPED_OBJECT,
            schema_name=schema_name,
            table_name=table_name,
            payload=payload,
        )
        emit(
            Event.SKIPPED_OBJECT,
            schema_name=schema_name,
            object_name=table_name,
            kind=payload.get("kind"),
        )

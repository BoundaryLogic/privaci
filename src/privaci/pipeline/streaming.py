"""Table streaming loop for the masking pipeline."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

import asyncpg

from privaci.autodetect import DetectionResult, resolve_effective_table_config
from privaci.catalog.graph import deferred_edge_components
from privaci.catalog.models import CatalogResult, DeferredEdge, TableInfo
from privaci.catalog.partitions import config_table_id
from privaci.config.models import Config
from privaci.contracts import load_plugins
from privaci.contracts.base import RunEnhancements
from privaci.mask.engine import MaskingEngine
from privaci.pipeline.table_plan import TableAction, plan_table
from privaci.schema.orphan_fks import orphan_fk_columns_to_null
from privaci.schema.strategies import finalize_empty_strategy_table
from privaci.schema.table_policy import table_strategy
from privaci.state import (
    AuditWriter,
    TableCheckpoint,
    parse_checkpoint_cursor,
)
from privaci.state.models import EventType
from privaci.stream.batch import resolve_batch_size
from privaci.stream.fetch import raise_if_interrupted
from privaci.stream.table import stream_table

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineStreamContext:
    """Stable bundle threaded through the per-table streaming loop."""

    source: asyncpg.Connection
    target: asyncpg.Connection
    catalog: CatalogResult
    config: Config
    salt: str
    run_id: uuid.UUID
    audit: AuditWriter
    detection: DetectionResult
    checkpoints: dict[str, TableCheckpoint]
    enhancements: RunEnhancements
    pseudonym_key: str | None = None


async def stream_all_tables(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    catalog: CatalogResult,
    config: Config,
    salt: str,
    run_id: uuid.UUID,
    audit: AuditWriter,
    detection: DetectionResult,
    checkpoints: dict[str, TableCheckpoint],
    *,
    pseudonym_key: str | None = None,
) -> tuple[int, int, dict[str, int], int]:
    """Stream every table in load order and return aggregate counts."""
    enhancer = load_plugins().run_enhancer
    build_async = getattr(enhancer, "build_enhancements_async", None)
    if build_async is not None:
        enhancements = await build_async(catalog, source=source)
    else:
        enhancements = enhancer.build_enhancements(catalog)
    ctx = PipelineStreamContext(
        source=source,
        target=target,
        catalog=catalog,
        config=config,
        salt=salt,
        pseudonym_key=pseudonym_key,
        run_id=run_id,
        audit=audit,
        detection=detection,
        checkpoints=checkpoints,
        enhancements=enhancements,
    )
    counts: dict[str, int] = {}
    total_rows = 0
    total_bytes = 0
    tables_done = 0
    cycle_components = _multi_table_cycle_components(catalog.load_plan.deferred_edges)
    for layer in catalog.load_plan.layers:
        for batch in _commit_batches(layer.table_ids, cycle_components):
            async with target.transaction():
                await target.execute("SET CONSTRAINTS ALL DEFERRED")
                for layer_table_id in batch:
                    done, rows, batch_bytes = await _process_layer_table(
                        ctx, layer_table_id
                    )
                    if done:
                        tables_done += 1
                        counts[layer_table_id] = rows
                        total_rows += rows
                        total_bytes += batch_bytes
    return tables_done, total_rows, counts, total_bytes


def _multi_table_cycle_components(
    deferred_edges: tuple[DeferredEdge, ...],
) -> tuple[frozenset[str], ...]:
    """Return deferred-edge SCCs that require a shared transaction."""
    return tuple(
        frozenset(component)
        for component in deferred_edge_components(deferred_edges)
        if len(component) > 1
    )


def _commit_batches(
    table_ids: tuple[str, ...],
    cycle_components: tuple[frozenset[str], ...],
) -> list[tuple[str, ...]]:
    """Group layer tables into commit units (one table, or one cycle SCC)."""
    remaining = list(table_ids)
    batches: list[tuple[str, ...]] = []
    while remaining:
        table_id = remaining[0]
        mates = next(
            (component for component in cycle_components if table_id in component),
            None,
        )
        if mates is None:
            batches.append((remaining.pop(0),))
            continue
        batch = tuple(tid for tid in remaining if tid in mates)
        remaining = [tid for tid in remaining if tid not in mates]
        batches.append(batch)
    return batches


async def _process_layer_table(
    ctx: PipelineStreamContext,
    layer_table_id: str,
) -> tuple[bool, int, int]:
    table = ctx.catalog.tables[layer_table_id]
    if (
        ctx.enhancements.subset_active
        and layer_table_id not in ctx.enhancements.row_filters
    ):
        _log_skip(table, reason="subset_outside_closure")
        return False, 0, 0
    checkpoint = ctx.checkpoints.get(layer_table_id)
    action = plan_table(table, ctx.config, checkpoint)
    if action is TableAction.SKIP_DONE:
        _log_skip(table, reason="checkpoint_done")
        return False, 0, 0
    if action is TableAction.SKIP_STRATEGY:
        _log_skip(table, strategy=table_strategy(table, ctx.config))
        return False, 0, 0
    if action is TableAction.FINALIZE_EMPTY:
        done, rows = await _finalize_empty_table(ctx, table)
        return done, rows, 0
    rows, batch_bytes = await stream_one_table(ctx, table, checkpoint=checkpoint)
    await _audit_table_streamed(ctx, table, rows)
    return True, rows, batch_bytes


async def _finalize_empty_table(
    ctx: PipelineStreamContext,
    table: TableInfo,
) -> tuple[bool, int]:
    strategy = table_strategy(table, ctx.config)
    rows = await finalize_empty_strategy_table(
        ctx.target,
        table,
        ctx.run_id,
        strategy=strategy,
    )
    await ctx.audit.write(
        ctx.target,
        EventType.COLUMN_MASKED,
        table_name=table.table_name,
        schema_name=table.schema_name,
        payload={"rows_affected": rows, "action": strategy},
    )
    return True, rows


async def _audit_table_streamed(
    ctx: PipelineStreamContext,
    table: TableInfo,
    rows: int,
) -> None:
    await ctx.audit.write(
        ctx.target,
        EventType.COLUMN_MASKED,
        table_name=table.table_name,
        schema_name=table.schema_name,
        payload={"rows_affected": rows, "action": "pipeline"},
    )


def _log_skip(
    table: TableInfo,
    *,
    reason: str | None = None,
    strategy: str | None = None,
) -> None:
    if reason == "checkpoint_done":
        logger.info(
            "Skipping %s (already done)",
            table.identifier,
            extra={
                "event": "table.skip",
                "table": table.identifier,
                "reason": reason,
            },
        )
        return
    logger.info(
        "Skipping %s (strategy=%s)",
        table.identifier,
        strategy,
        extra={
            "event": "table.skip",
            "table": table.identifier,
            "strategy": strategy,
        },
    )


async def stream_one_table(
    ctx: PipelineStreamContext,
    table: TableInfo,
    *,
    checkpoint: TableCheckpoint | None = None,
    outer_transaction: bool = False,
) -> tuple[int, int]:
    """Mask and stream one table; return ``(rows, estimated_bytes)``."""
    raise_if_interrupted()
    config_table = ctx.catalog.tables.get(config_table_id(table), table)
    table_cfg = resolve_effective_table_config(config_table, ctx.config, ctx.detection)
    await _write_detection_audit(ctx.target, config_table, ctx.detection, ctx.audit)
    engine = MaskingEngine(
        ctx.salt,
        table.identifier,
        table,
        table_cfg,
        cell_post_processor=ctx.enhancements.cell_post_processor,
        pseudonym_key=ctx.pseudonym_key,
        null_columns=orphan_fk_columns_to_null(table, ctx.catalog, ctx.config),
    )
    batch_size = resolve_batch_size(
        table,
        global_batch_size=ctx.config.batch_size,
        per_table_batch_size=table_cfg.batch_size,
    )
    last_pk = _resume_cursor(table, checkpoint)
    row_filter = ctx.enhancements.row_filters.get(table.identifier)
    rows = await stream_table(
        ctx.source,
        ctx.target,
        table,
        engine,
        run_id=ctx.run_id,
        batch_size=batch_size,
        last_pk_value=last_pk,
        outer_transaction=outer_transaction,
        table_config=table_cfg,
        audit=ctx.audit,
        row_filter=row_filter,
        config=ctx.config,
    )
    return rows, _estimate_row_bytes(table, rows)


def _resume_cursor(
    table: TableInfo,
    checkpoint: TableCheckpoint | None,
) -> object | None:
    if checkpoint is None or len(table.primary_key) != 1:
        return None
    pk_column = table.primary_key[0]
    pk_type = next(
        (col.data_type for col in table.columns if col.name == pk_column),
        "text",
    )
    return parse_checkpoint_cursor(checkpoint.last_pk_value, data_type=pk_type)


def _estimate_row_bytes(table: TableInfo, rows: int) -> int:
    """Rough byte estimate from catalog avg_width metadata."""
    if rows <= 0:
        return 0
    width = sum(column.avg_width or 0 for column in table.columns)
    return int(width * rows)


async def _write_detection_audit(
    conn: asyncpg.Connection,
    table: TableInfo,
    detection: DetectionResult,
    audit: AuditWriter,
) -> None:
    """Record auto-detect findings for one table before streaming rows."""
    for finding in detection.by_table(table.identifier):
        payload = {
            "confidence": finding.confidence,
            "matched_pattern": finding.matched_pattern,
            "provider": finding.provider,
            "action": finding.action.action if finding.action else None,
            "source": finding.source,
            "reasons": list(finding.reasons),
        }
        await audit.write(
            conn,
            EventType.COLUMN_PII_DETECTED,
            table_name=table.table_name,
            schema_name=table.schema_name,
            column_name=finding.column_name,
            payload=payload,
        )

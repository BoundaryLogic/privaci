"""Orchestrate value-free masking verification across source and target."""

from __future__ import annotations

import logging

import asyncpg

from privaci.autodetect import build_detection, resolve_effective_table_config
from privaci.catalog import introspect_catalog
from privaci.catalog.identifiers import quote_pg_identifier
from privaci.catalog.models import TableInfo
from privaci.config.models import Config
from privaci.verify.compare import compare_sampled_rows
from privaci.verify.models import CheckResult, Verdict, VerifyReport
from privaci.verify.structural import (
    check_fk_integrity,
    check_row_count_parity,
    check_unique_preserved,
)

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_SIZE = 1_000


async def run_verification(
    *,
    config: Config,
    source_dsn: str,
    target_dsn: str,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> VerifyReport:
    """Compare a completed run's target against its source, value-free."""
    source = await asyncpg.connect(source_dsn)
    target = await asyncpg.connect(target_dsn)
    try:
        report = await _build_verification_report(
            source, target, config, sample_size=sample_size
        )
        _log_report(report)
        return report
    finally:
        await source.close()
        await target.close()


async def _build_verification_report(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    config: Config,
    *,
    sample_size: int,
) -> VerifyReport:
    catalog = await introspect_catalog(source)
    detection = build_detection(config, catalog)
    results: list[CheckResult] = []
    for table_id, table in sorted(catalog.tables.items()):
        if not _is_transform(table_id, config):
            continue
        effective = resolve_effective_table_config(table, config, detection)
        masked = {
            name
            for name, action in effective.columns.items()
            if action.action != "passthrough"
        }
        passthrough = {c.name for c in table.columns} - masked
        results.extend(
            await _verify_table(source, target, table, masked, passthrough, sample_size)
        )
    return VerifyReport(results=tuple(results))


async def _verify_table(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    table: TableInfo,
    masked: set[str],
    passthrough: set[str],
    sample_size: int,
) -> list[CheckResult]:
    results: list[CheckResult] = [await check_row_count_parity(source, target, table)]
    results.extend(await check_unique_preserved(target, table))
    results.extend(await check_fk_integrity(target, table))
    results.extend(
        await _verify_rows(source, target, table, masked, passthrough, sample_size)
    )
    return results


async def _verify_rows(
    source: asyncpg.Connection,
    target: asyncpg.Connection,
    table: TableInfo,
    masked: set[str],
    passthrough: set[str],
    sample_size: int,
) -> list[CheckResult]:
    if len(table.primary_key) != 1:
        return [
            CheckResult(
                "table.no_single_pk",
                Verdict.WARN,
                table.identifier,
                "No single-column primary key; row-level checks skipped.",
            )
        ]
    pk = table.primary_key[0]
    qual = table.sql_ref
    pk_ref = quote_pg_identifier(pk)
    src_rows = await source.fetch(
        f"SELECT * FROM {qual} ORDER BY {pk_ref} LIMIT $1", sample_size  # noqa: S608
    )
    if not src_rows:
        return []
    keys = [row[pk] for row in src_rows]
    tgt_rows = await target.fetch(
        f"SELECT * FROM {qual} WHERE {pk_ref} = ANY($1)", keys  # noqa: S608
    )
    return compare_sampled_rows(
        table.identifier,
        [dict(row) for row in src_rows],
        [dict(row) for row in tgt_rows],
        pk=table.primary_key,
        masked_columns=masked,
        passthrough_columns=passthrough,
    )


def _is_transform(table_id: str, config: Config) -> bool:
    table_cfg = config.tables.get(table_id)
    if table_cfg is None:
        return True
    return table_cfg.strategy == "transform"


def _log_report(report: VerifyReport) -> None:
    counts = report.counts()
    logger.info(
        "Verification complete",
        extra={
            "event": "verify.done",
            "pass": counts[Verdict.PASS],
            "warn": counts[Verdict.WARN],
            "fail": counts[Verdict.FAIL],
        },
    )

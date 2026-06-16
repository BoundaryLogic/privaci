"""Implementation of ``privaci resume``."""

from __future__ import annotations

import asyncpg
import typer

from privaci.catalog.snapshot import validate_resume_schema_snapshot
from privaci.cli.context import prepare_cli_run, run_with_signal_handlers
from privaci.config.models import Config
from privaci.pipeline import run_masking_pipeline
from privaci.pipeline.runner import PipelineSummary
from privaci.preflight import run_preflight
from privaci.state import (
    RunIdentity,
    config_hash,
    ensure_state_schema,
    reopen_resumable_run,
    resolve_resumable_run,
    salt_fingerprint,
    source_db_hash,
)


def execute_resume(
    *,
    config_path: str,
    source: str | None,
    target: str | None,
    no_audit_table: bool = False,
) -> None:
    """Resume an interrupted run from checkpoints after pre-flight."""
    ctx = prepare_cli_run(config_path=config_path, source=source, target=target)
    summary: PipelineSummary = run_with_signal_handlers(
        lambda: _resume_async(
            config=ctx.config,
            source_dsn=ctx.source_dsn,
            target_dsn=ctx.target_dsn,
            salt=ctx.salt,
            audit_enabled=None if not no_audit_table else False,
        )
    )
    typer.echo(
        f"Run {summary.run_id} resumed: "
        f"{summary.tables_processed} table(s), {summary.rows_processed} row(s)."
    )


async def _resume_async(
    *,
    config: Config,
    source_dsn: str,
    target_dsn: str,
    salt: str,
    audit_enabled: bool | None,
) -> PipelineSummary:
    report = await run_preflight(
        config=config,
        source_dsn=source_dsn,
        target_dsn=target_dsn,
        dry_run=False,
        for_resume=True,
    )
    identity = RunIdentity(
        config_hash=config_hash(config),
        salt_fingerprint=salt_fingerprint(salt),
        source_db_hash=source_db_hash(source_dsn),
    )
    target = await asyncpg.connect(target_dsn)
    try:
        await ensure_state_schema(target)
        # Resolve and validate (read-only) before re-opening the run, so a drift
        # abort never flips the run back to in_progress. See P2 review finding.
        run_id = await resolve_resumable_run(target, identity)
        await validate_resume_schema_snapshot(target, run_id, report.catalog)
        checkpoints = await reopen_resumable_run(target, run_id)
    finally:
        await target.close()

    return await run_masking_pipeline(
        source_dsn,
        target_dsn,
        config,
        salt,
        audit_enabled=audit_enabled,
        catalog=report.catalog,
        resume_run_id=run_id,
        checkpoints=checkpoints,
    )

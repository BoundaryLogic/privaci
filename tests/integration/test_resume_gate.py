"""Integration tests for the resume gate through the real CLI path (§1.4-1.5).

Unlike ``test_beta_gate_e2e.test_resume_after_crash``, these exercises call
``privaci run`` / ``privaci resume`` (or ``execute_resume``) so
``require_resumable_run`` is on the code path — not a direct
``resume_run_id=`` bypass.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
import pytest
import yaml
from pytest_mock import MockerFixture

from privaci.catalog.identifiers import qualify, quote_pg_identifier
from privaci.cli._errors import run_cli
from privaci.cli._resume import execute_resume
from privaci.cli._run import execute_run
from privaci.config import load_config
from privaci.config.actions import FakeAction
from privaci.config.models import Config, TableConfig
from privaci.errors import PreflightError, RunInterruptedError
from privaci.pipeline import run_masking_pipeline
from privaci.runtime.signals import request_interrupt
from privaci.state import RunIdentity, config_hash, salt_fingerprint, source_db_hash
from privaci.state.models import RunStatus
from privaci.state.resume import require_resumable_run
from privaci.stream.table import stream_table
from tests.fixtures.constants import TEST_SALT
from tests.integration.assertions import count_rows, value_present
from tests.integration.catalog_config import config_keep_only
from tests.integration.test_beta_gate_e2e import _load_sql

pytestmark = pytest.mark.integration

_RESUME_SCHEMA = "beta_resume"
_RESUME_TABLE_NAME = "records"
_RESUME_TABLE = f"{_RESUME_SCHEMA}.{_RESUME_TABLE_NAME}"
_SOURCE_COUNT = 100


def _write_resume_config(path: Path, *, batch_size: int = 10) -> None:
    """Write a mask-rules file scoped to the resume-many-rows fixture."""
    payload = {
        "version": "1.0",
        "auto_detect": False,
        "batch_size": batch_size,
        "tables": {
            _RESUME_TABLE: {
                "columns": {"email": {"action": "fake", "provider": "email"}},
            },
        },
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def _cli_env(source_dsn: str, target_dsn: str) -> dict[str, str]:
    """Environment for Typer commands that resolve DSNs and salt."""
    return {
        "SOURCE_DB_URL": source_dsn,
        "TARGET_DB_URL": target_dsn,
        "ANONYMIZATION_SALT": TEST_SALT,
    }


def _patch_fetch_after_first_batch(
    mocker: MockerFixture,
    *,
    on_first_batch: object,
) -> None:
    """Invoke ``on_first_batch`` after the first batch fetch returns."""
    import privaci.stream.fetch as stream_fetch_mod

    original = stream_fetch_mod.fetch_batch_with_retry
    calls = 0

    async def _fetch_then_act(*args: object, **kwargs: object) -> list[object]:
        nonlocal calls
        calls += 1
        rows = await original(*args, **kwargs)
        if calls == 1:
            if callable(on_first_batch):
                on_first_batch()
            else:
                raise on_first_batch
        return rows

    mocker.patch.object(
        stream_fetch_mod, "fetch_batch_with_retry", side_effect=_fetch_then_act
    )


def _patch_interrupt_after_first_batch(mocker: MockerFixture) -> None:
    """Raise interrupt after the first fetched batch (mid-table)."""
    _patch_fetch_after_first_batch(mocker, on_first_batch=request_interrupt)


async def _run_identity(source_dsn: str, config: Config) -> RunIdentity:
    return RunIdentity(
        config_hash=config_hash(config),
        salt_fingerprint=salt_fingerprint(TEST_SALT),
        source_db_hash=source_db_hash(source_dsn),
    )


async def _assert_resume_parity(target_dsn: str) -> None:
    target = await asyncpg.connect(target_dsn)
    try:
        assert await count_rows(target, _RESUME_TABLE) == _SOURCE_COUNT
        resume_table = qualify(_RESUME_SCHEMA, _RESUME_TABLE_NAME)
        # Safe identifier interpolation: resume_table is derived from fixed test
        # constants via qualify(), which applies PostgreSQL identifier quoting.
        # S608 flags f-string SQL heuristically regardless of source.
        distinct_ids = await target.fetchval(
            f"SELECT count(DISTINCT id)::int FROM {resume_table}"  # noqa: S608
        )
        assert distinct_ids == _SOURCE_COUNT
        assert not await value_present(
            target, _RESUME_TABLE, "email", "record1@example.test"
        )
    finally:
        await target.close()


async def _fetch_latest_run_row(target: asyncpg.Connection) -> asyncpg.Record | None:
    """Return the latest ``(run_id, status)`` row from ``_privaci.runs``, or None.

    Assumes the PrivaCI state schema/tables have already been initialized by the
    integration-test setup (the pipeline run creates them before this is called).
    """
    return await target.fetchrow("""
        SELECT run_id, status FROM _privaci.runs
        ORDER BY started_at DESC LIMIT 1
        """)


async def _assert_run_status(target_dsn: str, expected: RunStatus) -> None:
    target = await asyncpg.connect(target_dsn)
    try:
        row = await _fetch_latest_run_row(target)
        assert row is not None
        assert row["status"] == expected.value
    finally:
        await target.close()


def test_cli_resume_after_interrupt_has_no_loss_or_duplication(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — sync test so execute_run can install signal handlers (main thread).
    asyncio.run(_load_sql(source_dsn, "resume-many-rows.sql"))
    config_path = tmp_path / "mask-rules.yaml"
    _write_resume_config(config_path, batch_size=10)
    _patch_interrupt_after_first_batch(mocker)
    for key, value in _cli_env(source_dsn, target_dsn).items():
        monkeypatch.setenv(key, value)

    # Act 1 — interrupted run via the real CLI entrypoint (exit 130).
    exit_code = run_cli(
        lambda: execute_run(
            config_path=str(config_path),
            source=source_dsn,
            target=target_dsn,
            audit_enabled=False,
        )
    )

    # Assert — interrupted, not a generic failure.
    assert exit_code == RunInterruptedError.exit_code
    asyncio.run(_assert_run_status(target_dsn, RunStatus.INTERRUPTED))

    # Act 2 — resume through the gate (CLI entrypoint).
    resume_code = run_cli(
        lambda: execute_resume(
            config_path=str(config_path),
            source=source_dsn,
            target=target_dsn,
            no_audit_table=True,
        )
    )

    # Assert
    assert resume_code == 0
    asyncio.run(_assert_resume_parity(target_dsn))


async def _verify_failed_gate(target_dsn: str, source_dsn: str, config: Config) -> None:
    target = await asyncpg.connect(target_dsn)
    try:
        row = await _fetch_latest_run_row(target)
        assert row is not None
        assert row["status"] == RunStatus.FAILED.value
        identity = await _run_identity(source_dsn, config)
        run_id, _checkpoints = await require_resumable_run(target, identity)
        assert run_id == row["run_id"]
    finally:
        await target.close()


def test_failed_run_resumable_via_gate(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    asyncio.run(_load_sql(source_dsn, "resume-many-rows.sql"))
    for key, value in _cli_env(source_dsn, target_dsn).items():
        monkeypatch.setenv(key, value)
    config_path = tmp_path / "mask-rules.yaml"
    _write_resume_config(config_path, batch_size=10)
    config = load_config(str(config_path))

    # Capture the real stream_table; the mock below patches the name as imported
    # into privaci.pipeline.streaming, so this top-level reference stays original.
    original_stream = stream_table
    calls = 0

    async def _crash_on_first_stream(*args: object, **kwargs: object) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated crash")
        return await original_stream(*args, **kwargs)

    mocker.patch(
        "privaci.pipeline.streaming.stream_table",
        side_effect=_crash_on_first_stream,
    )

    # Act 1 — crash leaves a failed run discoverable by the gate.
    with pytest.raises(RuntimeError, match="simulated crash"):
        asyncio.run(
            run_masking_pipeline(
                source_dsn, target_dsn, config, TEST_SALT, audit_enabled=False
            )
        )

    asyncio.run(_verify_failed_gate(target_dsn, source_dsn, config))

    # Act 2 — execute_resume uses the gate (not a direct resume_run_id bypass).
    resume_code = run_cli(
        lambda: execute_resume(
            config_path=str(config_path),
            source=source_dsn,
            target=target_dsn,
            no_audit_table=True,
        )
    )
    assert resume_code == 0

    # Assert
    asyncio.run(_assert_resume_parity(target_dsn))


async def _alter_source(source_dsn: str, statement: str) -> None:
    conn = await asyncpg.connect(source_dsn)
    try:
        await conn.execute(statement)
    finally:
        await conn.close()


def test_resume_rejected_on_source_schema_drift(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — crash a fresh run so a failed run + schema snapshot are recorded.
    asyncio.run(_load_sql(source_dsn, "resume-many-rows.sql"))
    for key, value in _cli_env(source_dsn, target_dsn).items():
        monkeypatch.setenv(key, value)
    config_path = tmp_path / "mask-rules.yaml"
    _write_resume_config(config_path, batch_size=10)
    config = load_config(str(config_path))

    # Capture the real stream_table; the mock below patches the name as imported
    # into privaci.pipeline.streaming, so this top-level reference stays original.
    original_stream = stream_table
    calls = 0

    async def _crash_on_first_stream(*args: object, **kwargs: object) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated crash")
        return await original_stream(*args, **kwargs)

    mocker.patch(
        "privaci.pipeline.streaming.stream_table",
        side_effect=_crash_on_first_stream,
    )
    with pytest.raises(RuntimeError, match="simulated crash"):
        asyncio.run(
            run_masking_pipeline(
                source_dsn, target_dsn, config, TEST_SALT, audit_enabled=False
            )
        )

    # Act — drift the source schema, then attempt resume through the gate.
    drift_table = qualify(_RESUME_SCHEMA, _RESUME_TABLE_NAME)
    asyncio.run(
        _alter_source(
            source_dsn,
            f"ALTER TABLE {drift_table} ADD COLUMN drift_marker text",
        )
    )
    resume_code = run_cli(
        lambda: execute_resume(
            config_path=str(config_path),
            source=source_dsn,
            target=target_dsn,
            no_audit_table=True,
        )
    )

    # Assert — resume is refused (pre-flight exit code) and the drift abort does
    # NOT flip the failed run back to in_progress (P2 review finding).
    assert resume_code == PreflightError.exit_code
    asyncio.run(_assert_run_status(target_dsn, RunStatus.FAILED))


@pytest.mark.asyncio
async def test_hostile_identifier_streams_safely(
    source_dsn: str,
    target_dsn: str,
    postgres_available: None,
    clean_target: None,
) -> None:
    # Arrange — table name contains an embedded double-quote.
    await _load_sql(source_dsn, "hostile-identifier.sql")
    hostile_table = 'beta_hostile.evil"table'
    config = await config_keep_only(
        source_dsn,
        {
            hostile_table: TableConfig(
                columns={"email": FakeAction(action="fake", provider="email")},
            ),
        },
        auto_detect=False,
        batch_size=500,
    )

    # Act
    summary = await run_masking_pipeline(
        source_dsn, target_dsn, config, TEST_SALT, audit_enabled=False
    )

    # Assert — all rows streamed; no SQL injection or quoting failure.
    assert summary.table_row_counts[hostile_table] == 20
    target = await asyncpg.connect(target_dsn)
    try:
        # The table name is deliberately hostile (an embedded double-quote), so
        # the S608 suppressions below are NOT justified by "trusted input". They
        # are safe because every identifier is rendered through qualify() /
        # quote_pg_identifier() (the production quoting path) and the email value
        # is passed as a bind parameter, never interpolated.
        qual = qualify("beta_hostile", 'evil"table')
        email_col = quote_pg_identifier("email")
        row_count = await target.fetchval(
            f"SELECT count(*)::int FROM {qual}"  # noqa: S608
        )
        assert int(row_count or 0) == 20
        leaked = await target.fetchval(
            f"SELECT EXISTS(SELECT 1 FROM {qual} WHERE {email_col} = $1)",  # noqa: S608
            "hostile1@example.test",
        )
        assert not leaked
    finally:
        await target.close()

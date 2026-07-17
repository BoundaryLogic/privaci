"""Unit tests for UsageMeter run-id pairing on fresh runs."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from privaci.pipeline import run_lifecycle
from privaci.state.models import RunStatus


def test_notify_meter_run_start_passes_persisted_run_id(
    mocker: MockerFixture,
) -> None:
    # Arrange
    run_id = uuid.uuid4()
    meter = MagicMock()
    plugins = MagicMock(usage_meter=meter)
    mocker.patch("privaci.pipeline.run_lifecycle.load_plugins", return_value=plugins)

    # Act
    run_lifecycle.notify_meter_run_start("abc123", run_id)

    # Assert
    meter.register_run.assert_called_once_with(
        source_db_hash="abc123",
        run_id=run_id,
    )


def test_notify_meter_run_end_uses_same_run_id(mocker: MockerFixture) -> None:
    # Arrange
    run_id = uuid.uuid4()
    meter = MagicMock()
    plugins = MagicMock(usage_meter=meter)
    mocker.patch("privaci.pipeline.run_lifecycle.load_plugins", return_value=plugins)

    # Act
    run_lifecycle.notify_meter_run_end("abc123", run_id)

    # Assert
    meter.final_meter.assert_called_once_with(
        source_db_hash="abc123",
        run_id=run_id,
    )


@pytest.mark.asyncio
async def test_open_run_registers_meter_with_start_run_id(
    mocker: MockerFixture,
) -> None:
    # Arrange
    run_id = uuid.uuid4()
    target = MagicMock()
    catalog = MagicMock()
    config = MagicMock(schema_mode="replicate")
    mocker.patch(
        "privaci.pipeline.run_lifecycle.start_run",
        new=mocker.AsyncMock(return_value=run_id),
    )
    mocker.patch(
        "privaci.pipeline.run_lifecycle.initialize_fresh_run",
        new=mocker.AsyncMock(return_value=MagicMock()),
    )
    register = mocker.patch("privaci.pipeline.run_lifecycle.notify_meter_run_start")
    mocker.patch(
        "privaci.pipeline.run_lifecycle.config_hash",
        return_value="cfg",
    )
    mocker.patch(
        "privaci.pipeline.run_lifecycle.salt_fingerprint",
        return_value="saltfp",
    )
    mocker.patch(
        "privaci.pipeline.run_lifecycle.source_db_hash",
        return_value="src",
    )

    # Act
    opened_id, _audit = await run_lifecycle.open_run(
        target,
        catalog,
        config,
        source_dsn="postgresql://localhost/db",
        salt="x" * 32,
        resume_run_id=None,
        audit_enabled=False,
    )

    # Assert
    assert opened_id == run_id
    register.assert_called_once_with("src", run_id)


@pytest.mark.asyncio
async def test_open_run_resume_does_not_register_meter(
    mocker: MockerFixture,
) -> None:
    # Arrange
    resume_id = uuid.uuid4()
    mocker.patch(
        "privaci.pipeline.run_lifecycle.prepare_target_schema",
        new=mocker.AsyncMock(),
    )
    register = mocker.patch("privaci.pipeline.run_lifecycle.notify_meter_run_start")

    # Act
    opened_id, _audit = await run_lifecycle.open_run(
        MagicMock(),
        MagicMock(),
        MagicMock(schema_mode="replicate"),
        source_dsn="postgresql://localhost/db",
        salt="x" * 32,
        resume_run_id=resume_id,
        audit_enabled=False,
    )

    # Assert
    assert opened_id == resume_id
    register.assert_not_called()


@pytest.mark.asyncio
async def test_stream_and_finish_marks_succeeded(mocker: MockerFixture) -> None:
    # Arrange
    run_id = uuid.uuid4()
    mocker.patch(
        "privaci.pipeline.run_lifecycle.build_detection",
        return_value=MagicMock(),
    )
    mocker.patch(
        "privaci.pipeline.run_lifecycle.stream_all_tables",
        new=AsyncMock(return_value=(1, 10, {"public.t": 10}, 100)),
    )
    finish = mocker.patch(
        "privaci.pipeline.run_lifecycle.finish_run",
        new=AsyncMock(),
    )
    meter_end = mocker.patch("privaci.pipeline.run_lifecycle.notify_meter_run_end")
    mocker.patch("privaci.pipeline.run_lifecycle.emit_run_end")
    mocker.patch(
        "privaci.pipeline.run_lifecycle.source_db_hash",
        return_value="src",
    )

    # Act
    tables, rows, counts, nbytes = await run_lifecycle.stream_and_finish(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        "x" * 32,
        run_id,
        MagicMock(),
        0.0,
        source_dsn="postgresql://localhost/db",
        checkpoints={},
    )

    # Assert
    assert tables == 1
    assert rows == 10
    assert counts == {"public.t": 10}
    assert nbytes == 100
    finish.assert_awaited_once()
    meter_end.assert_called_once_with("src", run_id)


@pytest.mark.asyncio
async def test_close_aborted_run_finalizes_meter_on_failed(
    mocker: MockerFixture,
) -> None:
    # Arrange
    run_id = uuid.uuid4()
    finish = mocker.patch(
        "privaci.pipeline.run_lifecycle.finish_run",
        new=AsyncMock(),
    )
    meter_end = mocker.patch("privaci.pipeline.run_lifecycle.notify_meter_run_end")
    mocker.patch("privaci.pipeline.run_lifecycle.emit_run_end")
    mocker.patch(
        "privaci.pipeline.run_lifecycle.source_db_hash",
        return_value="src",
    )

    # Act
    await run_lifecycle.close_aborted_run(
        MagicMock(),
        run_id,
        0.0,
        RunStatus.FAILED,
        source_dsn="postgresql://localhost/db",
        errors=1,
    )

    # Assert
    finish.assert_awaited_once()
    meter_end.assert_called_once_with("src", run_id)


@pytest.mark.asyncio
async def test_close_aborted_run_skips_meter_on_interrupted(
    mocker: MockerFixture,
) -> None:
    # Arrange
    run_id = uuid.uuid4()
    finish = mocker.patch(
        "privaci.pipeline.run_lifecycle.finish_run",
        new=AsyncMock(),
    )
    meter_end = mocker.patch("privaci.pipeline.run_lifecycle.notify_meter_run_end")
    mocker.patch("privaci.pipeline.run_lifecycle.emit_run_end")
    mocker.patch(
        "privaci.pipeline.run_lifecycle.source_db_hash",
        return_value="src",
    )

    # Act
    await run_lifecycle.close_aborted_run(
        MagicMock(),
        run_id,
        0.0,
        RunStatus.INTERRUPTED,
        source_dsn="postgresql://localhost/db",
        errors=0,
    )

    # Assert
    finish.assert_awaited_once()
    meter_end.assert_not_called()


@pytest.mark.asyncio
async def test_close_aborted_run_noop_without_run_id(mocker: MockerFixture) -> None:
    finish = mocker.patch(
        "privaci.pipeline.run_lifecycle.finish_run",
        new=AsyncMock(),
    )

    await run_lifecycle.close_aborted_run(
        MagicMock(),
        None,
        0.0,
        RunStatus.INTERRUPTED,
    )

    finish.assert_not_awaited()

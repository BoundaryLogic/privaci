"""Pipeline lifecycle tests for assume-existing target preparation."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from privaci.autodetect.models import DetectionResult
from privaci.catalog.models import CatalogResult, LoadLayer, LoadPlan
from privaci.config.loader import SUPPORTED_VERSION
from privaci.config.models import Config
from privaci.errors import PreflightError, StateError
from privaci.observability import Event
from privaci.pipeline.lifecycle import (
    _prepare_assume_existing,
    _replicate_and_emit_start,
)
from privaci.schema.assume_existing import (
    AssumeExistingValidation,
    ColumnMismatch,
)
from privaci.state import AuditWriter, RunIdentity
from privaci.state.models import EventType


def _empty_catalog() -> CatalogResult:
    return CatalogResult(
        tables={},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=()),)),
    )


@pytest.mark.asyncio
async def test_prepare_assume_existing_validates_audits_and_truncates(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    config = Config(
        version=SUPPORTED_VERSION,
        schema_mode="assume_existing",
        on_existing_data="truncate",
    )
    validation = AssumeExistingValidation(tables_checked=2, mismatches=())
    audit = mocker.AsyncMock(spec=AuditWriter)
    mocker.patch(
        "privaci.pipeline.lifecycle.validate_assume_existing",
        new=mocker.AsyncMock(return_value=validation),
    )
    mocker.patch(
        "privaci.pipeline.lifecycle.build_detection",
        return_value=DetectionResult(findings=()),
    )
    verify_copy = mocker.patch(
        "privaci.pipeline.lifecycle.verify_passthrough_copy_policy",
        new_callable=AsyncMock,
    )
    ensure_ready = mocker.patch(
        "privaci.pipeline.lifecycle.ensure_target_ready",
        new_callable=AsyncMock,
    )
    target = mocker.AsyncMock()
    catalog = _empty_catalog()

    # Act
    await _prepare_assume_existing(target, audit, catalog, config)

    # Assert
    audit.write.assert_awaited_once()
    assert audit.write.await_args.args[1] is EventType.SCHEMA_VALIDATED
    verify_copy.assert_awaited_once()
    ensure_ready.assert_awaited_once_with(target, config, catalog)


@pytest.mark.asyncio
async def test_validation_audit_failure_does_not_hide_schema_mismatch(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    config = Config(
        version=SUPPORTED_VERSION,
        schema_mode="assume_existing",
        on_existing_data="truncate",
    )
    validation = AssumeExistingValidation(
        tables_checked=1,
        mismatches=(
            ColumnMismatch(
                table_id="public.users",
                column_name="email",
                source_type="text",
                target_type=None,
                reason="missing_column",
            ),
        ),
    )
    mocker.patch(
        "privaci.pipeline.lifecycle.validate_assume_existing",
        new=mocker.AsyncMock(return_value=validation),
    )
    ensure_ready = mocker.patch(
        "privaci.pipeline.lifecycle.ensure_target_ready",
        new_callable=AsyncMock,
    )
    audit = mocker.AsyncMock(spec=AuditWriter)
    audit.write.side_effect = StateError("audit unavailable")

    # Act & Assert
    with pytest.raises(PreflightError, match="missing column public.users.email"):
        await _prepare_assume_existing(
            mocker.AsyncMock(),
            audit,
            _empty_catalog(),
            config,
        )
    ensure_ready.assert_not_awaited()


@pytest.mark.asyncio
async def test_assume_existing_does_not_emit_schema_cloned(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    config = Config(
        version=SUPPORTED_VERSION,
        schema_mode="assume_existing",
        on_existing_data="truncate",
    )
    emit = mocker.patch("privaci.pipeline.lifecycle.emit")
    mocker.patch(
        "privaci.pipeline.lifecycle.load_latest_schema_snapshot",
        new=mocker.AsyncMock(return_value=None),
    )
    prepare = mocker.patch(
        "privaci.pipeline.lifecycle._prepare_assume_existing",
        new_callable=AsyncMock,
    )
    identity = RunIdentity(
        config_hash="config-hash",
        salt_fingerprint="salt-fingerprint",
        source_db_hash="source-hash",
    )

    # Act
    await _replicate_and_emit_start(
        mocker.AsyncMock(),
        _empty_catalog(),
        config,
        uuid.uuid4(),
        identity,
        mocker.AsyncMock(spec=AuditWriter),
    )

    # Assert
    prepare.assert_awaited_once()
    emitted_events = [call.args[0] for call in emit.call_args_list]
    assert Event.SCHEMA_CLONED not in emitted_events


@pytest.mark.asyncio
async def test_replicate_prepares_target_before_schema_replication(
    mocker: pytest.MockFixture,
) -> None:
    # Arrange
    config = Config(version=SUPPORTED_VERSION, on_existing_data="truncate")
    ensure_ready = mocker.patch(
        "privaci.pipeline.lifecycle.ensure_target_ready",
        new_callable=AsyncMock,
    )
    replicate_schema = mocker.patch(
        "privaci.pipeline.lifecycle.replicate_schema",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "privaci.pipeline.lifecycle.load_latest_schema_snapshot",
        new=mocker.AsyncMock(return_value=None),
    )
    identity = RunIdentity(
        config_hash="config-hash",
        salt_fingerprint="salt-fingerprint",
        source_db_hash="source-hash",
    )
    catalog = _empty_catalog()
    target = mocker.AsyncMock()

    # Act
    await _replicate_and_emit_start(
        target,
        catalog,
        config,
        uuid.uuid4(),
        identity,
        mocker.AsyncMock(spec=AuditWriter),
    )

    # Assert
    ensure_ready.assert_awaited_once_with(target, config, catalog)
    replicate_schema.assert_awaited_once_with(target, catalog, config)

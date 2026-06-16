"""Tests for community-mode contract fallbacks."""

from __future__ import annotations

from uuid import uuid4

import pytest

from privaci.contracts.base import ColumnContext, RunCompletionEvent
from privaci.contracts.fallbacks import (
    CommunityLicenseValidator,
    JsonReportRenderer,
    NoOpLLMConnector,
    NoOpNotifier,
    NoOpUsageMeter,
)
from privaci.contracts.plugins import load_plugins
from privaci.errors import L3NotInstalledError


def test_community_license_is_valid() -> None:
    # Arrange
    validator = CommunityLicenseValidator()

    # Act
    status = validator.validate()

    # Assert
    assert status.is_valid is True
    assert status.tier == "community"


def test_noop_usage_meter_is_silent() -> None:
    # Arrange
    meter = NoOpUsageMeter()
    run_id = uuid4()

    # Act & Assert — must not raise
    meter.register_run(source_db_hash="abc", run_id=run_id)
    meter.report_usage(source_db_hash="abc", run_id=run_id)
    meter.final_meter(source_db_hash="abc", run_id=run_id)


def test_noop_llm_raises_l3_not_installed() -> None:
    # Arrange
    connector = NoOpLLMConnector()
    context = ColumnContext(
        schema_name="public",
        table_name="tickets",
        column_name="body",
    )

    # Act & Assert
    with pytest.raises(L3NotInstalledError):
        connector.redact_entities("hello", salt="x" * 32, context=context)


def test_json_report_renderer_community_json() -> None:
    # Arrange
    renderer = JsonReportRenderer()
    run_id = uuid4()

    # Act
    payload = renderer.render(run_id, output_format="json")

    # Assert
    assert b"run_id" in payload


def test_json_report_pdf_requires_commercial() -> None:
    # Arrange
    renderer = JsonReportRenderer()

    # Act & Assert
    with pytest.raises(L3NotInstalledError):
        renderer.render(uuid4(), output_format="pdf")


def test_noop_notifier_drops_events() -> None:
    # Arrange
    notifier = NoOpNotifier()
    event = RunCompletionEvent(
        run_id=uuid4(),
        status="succeeded",
        rows_processed=100,
        duration_ms=500,
    )

    # Act & Assert
    notifier.notify(event)


def test_plugins_load_entry_point_when_registered(
    mocker: pytest.Mock,
) -> None:
    # Arrange
    from privaci.contracts.base import LicenseStatus, LicenseValidator

    class FakeValidator(LicenseValidator):
        def validate(self) -> LicenseStatus:
            return LicenseStatus(tier="enterprise", is_valid=True)

    fake_ep = mocker.Mock()
    fake_ep.name = "license_validator"
    fake_ep.load.return_value = FakeValidator
    mocker.patch(
        "privaci.contracts.plugins.importlib.metadata.entry_points",
        return_value=[fake_ep],
    )

    # Act
    bundle = load_plugins()

    # Assert
    assert bundle.license_validator.validate().tier == "enterprise"


def test_load_plugins_community_defaults() -> None:
    # Arrange & Act
    bundle = load_plugins()

    # Assert
    assert bundle.license_validator.validate().tier == "community"
    assert "noop" in bundle.llm_connectors
    assert bundle.drift_detector is None

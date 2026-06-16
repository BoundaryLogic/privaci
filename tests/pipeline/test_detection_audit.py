"""Tests for pipeline auto-detect audit wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.autodetect.models import DetectionFinding, DetectionResult
from privaci.catalog.models import TableInfo
from privaci.config.actions import FakeAction
from privaci.pipeline.streaming import _write_detection_audit
from privaci.pipeline.table_plan import table_strategy
from privaci.state.models import EventType


@pytest.mark.asyncio
async def test_write_detection_audit_emits_pii_events() -> None:
    # Arrange
    conn = AsyncMock()
    audit = AsyncMock()
    audit.write = AsyncMock()
    table = TableInfo("public", "users", ())
    finding = DetectionFinding(
        table_id="public.users",
        column_name="email",
        confidence="high",
        reasons=("name pattern",),
        action=FakeAction(action="fake", provider="email"),
        matched_pattern="email",
        provider="email",
    )
    detection = DetectionResult(findings=(finding,))

    # Act
    await _write_detection_audit(conn, table, detection, audit)

    # Assert
    audit.write.assert_awaited_once()
    call = audit.write.await_args
    assert call.args[1] is EventType.COLUMN_PII_DETECTED
    assert call.kwargs["column_name"] == "email"
    assert call.kwargs["payload"]["action"] == "fake"


def test_table_strategy_defaults_to_transform() -> None:
    # Arrange
    table = TableInfo("public", "users", ())

    # Act & Assert
    from privaci.config.models import Config

    assert table_strategy(table, Config(version="1.0")) == "transform"

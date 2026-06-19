"""Tests for preflight orchestration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from privaci.autodetect.models import DetectionResult
from privaci.catalog.models import CatalogResult, LoadPlan
from privaci.config.models import Config
from privaci.preflight.runner import _run_preflight_checks
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION


@pytest.mark.asyncio
async def test_defer_strict_skips_verify_strict_autodetect(mocker) -> None:
    source = AsyncMock()
    target = AsyncMock()
    catalog = CatalogResult(tables={}, load_plan=LoadPlan(layers=()))
    config = Config(version=SUPPORTED_CONFIG_VERSION, strict_autodetect=True)
    detection = DetectionResult(findings=())
    mocker.patch(
        "privaci.preflight.runner.verify_source_readable",
        new=AsyncMock(),
    )
    mocker.patch(
        "privaci.preflight.runner.introspect_catalog",
        new=AsyncMock(return_value=catalog),
    )
    mocker.patch("privaci.preflight.runner.build_detection", return_value=detection)
    strict = mocker.patch("privaci.preflight.runner.verify_strict_autodetect")
    mocker.patch(
        "privaci.preflight.runner.run_target_checks",
        new=AsyncMock(return_value=[]),
    )
    mocker.patch("privaci.preflight.runner.collect_dry_run_rows", return_value=[])
    mocker.patch("privaci.preflight.runner.emit")

    await _run_preflight_checks(
        source,
        target,
        config,
        dry_run=True,
        for_resume=False,
        defer_strict=True,
    )
    strict.assert_not_called()

    await _run_preflight_checks(
        source,
        target,
        config,
        dry_run=True,
        for_resume=False,
        defer_strict=False,
    )
    strict.assert_called_once_with(config, detection)

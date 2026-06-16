"""Tests for ``privaci detect-drift``."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from privaci.cli._drift import _detect_drift_async, execute_detect_drift
from privaci.cli.app import app
from privaci.contracts.base import DriftReport
from privaci.errors import DriftError
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION

runner = CliRunner()


def _write_config(tmp_path: Path) -> Path:
    config = tmp_path / "mask-rules.yaml"
    config.write_text(
        yaml.safe_dump({"version": SUPPORTED_CONFIG_VERSION, "tables": {}}),
        encoding="utf-8",
    )
    return config


def test_detect_drift_requires_commercial_layer(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    config = _write_config(tmp_path)
    bundle = mocker.patch("privaci.cli._drift.load_plugins").return_value
    bundle.drift_detector = None

    result = runner.invoke(
        app,
        [
            "detect-drift",
            "--config",
            str(config),
            "--source",
            "postgresql://u:p@localhost/src",
            "--target",
            "postgresql://u:p@localhost/tgt",
        ],
    )

    assert result.exit_code == 1
    assert "detect-drift requires the commercial layer" in result.output


def test_execute_detect_drift_passes_accept_flag(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    config = _write_config(tmp_path)
    bundle = mocker.patch("privaci.cli._drift.load_plugins").return_value
    bundle.drift_detector = MagicMock()
    mocker.patch(
        "privaci.cli._drift.resolve_db_url",
        side_effect=lambda _url, **_: "postgresql://u:p@localhost/db",
    )
    run_mock = mocker.patch("privaci.cli._drift.asyncio.run")

    execute_detect_drift(
        config_path=str(config),
        source="s",
        target="t",
        accept_drift=True,
    )

    coro = run_mock.call_args.args[0]
    assert coro.cr_code is not None
    run_mock.assert_called_once()


def test_detect_drift_async_skips_without_baseline(mocker: MockerFixture) -> None:
    detector = MagicMock()
    mocker.patch(
        "privaci.cli._drift._introspect_snapshot",
        return_value={"tables": {}},
    )
    mocker.patch("privaci.cli._drift._load_baseline_snapshot", return_value=None)

    asyncio.run(
        _detect_drift_async(
            source_dsn="postgresql://u:p@localhost/src",
            target_dsn="postgresql://u:p@localhost/tgt",
            implied_fk_ignore=frozenset(),
            drift_detector=detector,
            accept_drift=False,
        )
    )

    detector.detect.assert_not_called()


def test_detect_drift_async_raises_on_drift(mocker: MockerFixture) -> None:
    detector = MagicMock()
    detector.detect.return_value = DriftReport(
        has_drift=True,
        findings=[{"kind": "table_added", "table": "public.new_table"}],
    )
    mocker.patch(
        "privaci.cli._drift._introspect_snapshot",
        return_value={"tables": {"public.new_table": {}}},
    )
    mocker.patch(
        "privaci.cli._drift._load_baseline_snapshot",
        return_value={"tables": {}},
    )

    with pytest.raises(DriftError) as exc_info:
        asyncio.run(
            _detect_drift_async(
                source_dsn="postgresql://u:p@localhost/src",
                target_dsn="postgresql://u:p@localhost/tgt",
                implied_fk_ignore=frozenset(),
                drift_detector=detector,
                accept_drift=False,
            )
        )

    assert exc_info.value.exit_code == 6


def test_detect_drift_async_accept_drift_suppresses_error(
    mocker: MockerFixture,
) -> None:
    detector = MagicMock()
    detector.detect.return_value = DriftReport(
        has_drift=True,
        findings=[{"kind": "column_added", "table": "public.users", "column": "x"}],
    )
    mocker.patch(
        "privaci.cli._drift._introspect_snapshot",
        return_value={"tables": {}},
    )
    mocker.patch(
        "privaci.cli._drift._load_baseline_snapshot",
        return_value={"tables": {}},
    )

    asyncio.run(
        _detect_drift_async(
            source_dsn="postgresql://u:p@localhost/src",
            target_dsn="postgresql://u:p@localhost/tgt",
            implied_fk_ignore=frozenset(),
            drift_detector=detector,
            accept_drift=True,
        )
    )

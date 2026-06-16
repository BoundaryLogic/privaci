"""CLI tests for privaci resume."""

from __future__ import annotations

from pathlib import Path

import yaml
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from privaci.cli.app import app
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION

runner = CliRunner()


def test_resume_invokes_execute_resume(tmp_path: Path, mocker: MockerFixture) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text(
        yaml.safe_dump({"version": SUPPORTED_CONFIG_VERSION, "tables": {}}),
        encoding="utf-8",
    )
    execute = mocker.patch("privaci.cli.app.execute_resume")

    # Act
    result = runner.invoke(app, ["resume", "--config", str(config)])

    # Assert
    assert result.exit_code == 0
    execute.assert_called_once()


def test_report_emits_json(mocker: MockerFixture) -> None:
    # Arrange
    import uuid

    run_id = uuid.uuid4()
    bundle = mocker.patch("privaci.cli.app.load_plugins").return_value
    bundle.report_renderer.render.return_value = b'{"run_id": "x"}'

    # Act
    result = runner.invoke(app, ["report", "--run", str(run_id)])

    # Assert
    assert result.exit_code == 0
    assert "run_id" in result.output

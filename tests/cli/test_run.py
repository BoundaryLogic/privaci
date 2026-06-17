"""CLI tests for ``privaci run`` and ``privaci dry-run``."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import yaml
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from privaci.cli.app import app
from privaci.errors import CatalogError
from privaci.pipeline.runner import PipelineSummary
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION, TEST_SALT

runner = CliRunner()


def _config_file(tmp_path: Path) -> Path:
    path = tmp_path / "mask-rules.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": SUPPORTED_CONFIG_VERSION,
                "global_salt": TEST_SALT,
                "tables": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_run_delegates_to_execute_run(tmp_path: Path, mocker: MockerFixture) -> None:
    # Arrange
    config = _config_file(tmp_path)
    execute = mocker.patch("privaci.cli.app.execute_run")
    summary = PipelineSummary(run_id=uuid.uuid4(), tables_processed=1, rows_processed=5)
    mocker.patch(
        "privaci.cli._run._execute_async",
        new_callable=AsyncMock,
        return_value=summary,
    )

    # Act
    result = runner.invoke(
        app,
        [
            "run",
            "--config",
            str(config),
            "--source",
            "postgresql://x/y",
            "--target",
            "postgresql://x/z",
        ],
    )

    # Assert
    assert result.exit_code == 0
    execute.assert_called_once_with(
        config_path=str(config),
        source="postgresql://x/y",
        target="postgresql://x/z",
        dry_run=False,
        audit_enabled=None,
        report_path=None,
    )


def test_dry_run_delegates_with_dry_run_flag(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    # Arrange
    config = _config_file(tmp_path)
    execute = mocker.patch("privaci.cli.app.execute_run")

    # Act
    result = runner.invoke(
        app,
        [
            "dry-run",
            "--config",
            str(config),
            "--source",
            "postgresql://x/y",
            "--target",
            "postgresql://x/z",
        ],
    )

    # Assert
    assert result.exit_code == 0
    execute.assert_called_once_with(
        config_path=str(config),
        source="postgresql://x/y",
        target="postgresql://x/z",
        dry_run=True,
        audit_enabled=None,
        report_path=None,
    )


def test_run_missing_source_raises_catalog_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.delenv("SOURCE_DB_URL", raising=False)
    config = _config_file(tmp_path)

    # Act
    result = runner.invoke(
        app,
        ["run", "--config", str(config), "--target", "postgresql://x/z"],
    )

    # Assert
    assert isinstance(result.exception, CatalogError)
    assert result.exception.exit_code == 2
    assert "SOURCE_DB_URL" in str(result.exception)

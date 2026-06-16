"""Direct tests for :func:`privaci.cli._resume.execute_resume`.

These mock all I/O (pre-flight, state schema, pipeline) so the orchestration in
``execute_resume`` / ``_resume_async`` is covered without a live database.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml
from pytest_mock import MockerFixture

from privaci.autodetect.models import DetectionResult
from privaci.catalog.models import CatalogResult, LoadPlan, TableInfo, table_id
from privaci.cli._resume import execute_resume
from privaci.config.models import Config
from privaci.pipeline.runner import PipelineSummary
from privaci.preflight.runner import PreflightReport
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION, TEST_SALT


def _config_path(tmp_path: Path) -> Path:
    path = tmp_path / "mask-rules.yaml"
    path.write_text(
        yaml.safe_dump({"version": SUPPORTED_CONFIG_VERSION, "global_salt": TEST_SALT}),
        encoding="utf-8",
    )
    return path


def test_execute_resume_completes_with_summary(
    tmp_path: Path,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange
    config = Config(version="1.0", global_salt=TEST_SALT)
    report = PreflightReport(
        catalog=CatalogResult(
            tables={table_id("public", "users"): TableInfo("public", "users", ())},
            load_plan=LoadPlan(layers=()),
        ),
        detection=DetectionResult(findings=()),
    )
    run_id = uuid.uuid4()
    summary = PipelineSummary(run_id=run_id, tables_processed=2, rows_processed=9)
    mocker.patch("privaci.cli.context.load_config", return_value=config)
    mocker.patch("privaci.cli.context.resolve_run_salt", return_value=TEST_SALT)
    mocker.patch(
        "privaci.cli._resume.run_preflight",
        new_callable=AsyncMock,
        return_value=report,
    )
    conn = mocker.AsyncMock()
    mocker.patch(
        "privaci.cli._resume.asyncpg.connect",
        new_callable=AsyncMock,
        return_value=conn,
    )
    mocker.patch("privaci.cli._resume.ensure_state_schema", new_callable=AsyncMock)
    mocker.patch(
        "privaci.cli._resume.resolve_resumable_run",
        new_callable=AsyncMock,
        return_value=run_id,
    )
    mocker.patch(
        "privaci.cli._resume.validate_resume_schema_snapshot",
        new_callable=AsyncMock,
    )
    mocker.patch(
        "privaci.cli._resume.reopen_resumable_run",
        new_callable=AsyncMock,
        return_value=(),
    )
    pipeline = mocker.patch(
        "privaci.cli._resume.run_masking_pipeline",
        new_callable=AsyncMock,
        return_value=summary,
    )

    # Act
    execute_resume(
        config_path=str(_config_path(tmp_path)),
        source="postgresql://x/y",
        target="postgresql://x/z",
    )
    captured = capsys.readouterr()

    # Assert
    assert "resumed" in captured.out
    assert str(run_id) in captured.out
    pipeline.assert_awaited_once()
    conn.close.assert_awaited_once()


def test_execute_resume_closes_connection_on_drift(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    # Arrange — schema-drift validation raises; the target connection must still
    # be closed and the pipeline must not run.
    config = Config(version="1.0", global_salt=TEST_SALT)
    report = PreflightReport(
        catalog=CatalogResult(tables={}, load_plan=LoadPlan(layers=())),
        detection=DetectionResult(findings=()),
    )
    mocker.patch("privaci.cli.context.load_config", return_value=config)
    mocker.patch("privaci.cli.context.resolve_run_salt", return_value=TEST_SALT)
    mocker.patch(
        "privaci.cli._resume.run_preflight",
        new_callable=AsyncMock,
        return_value=report,
    )
    conn = mocker.AsyncMock()
    mocker.patch(
        "privaci.cli._resume.asyncpg.connect",
        new_callable=AsyncMock,
        return_value=conn,
    )
    mocker.patch("privaci.cli._resume.ensure_state_schema", new_callable=AsyncMock)
    mocker.patch(
        "privaci.cli._resume.resolve_resumable_run",
        new_callable=AsyncMock,
        return_value=uuid.uuid4(),
    )
    mocker.patch(
        "privaci.cli._resume.validate_resume_schema_snapshot",
        new_callable=AsyncMock,
        side_effect=RuntimeError("schema drift"),
    )
    pipeline = mocker.patch(
        "privaci.cli._resume.run_masking_pipeline", new_callable=AsyncMock
    )

    # Act / Assert
    with pytest.raises(RuntimeError, match="schema drift"):
        execute_resume(
            config_path=str(_config_path(tmp_path)),
            source="postgresql://x/y",
            target="postgresql://x/z",
        )
    conn.close.assert_awaited_once()
    pipeline.assert_not_awaited()

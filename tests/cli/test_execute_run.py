"""Direct tests for :func:`privaci.cli._run.execute_run`."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import typer
import yaml
from pytest_mock import MockerFixture

from privaci.autodetect.models import DetectionFinding, DetectionResult
from privaci.catalog.models import (
    CatalogResult,
    CatalogWarning,
    ColumnInfo,
    LoadPlan,
    TableInfo,
    table_id,
)
from privaci.cli._run import execute_run, execute_verify
from privaci.config.actions import FakeAction, HashAction
from privaci.config.models import Config
from privaci.contracts.base import LicenseStatus
from privaci.errors import ConfigError
from privaci.pipeline.runner import PipelineSummary
from privaci.preflight.runner import PreflightReport
from privaci.verify.models import CheckResult, Verdict, VerifyReport
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION, TEST_SALT


def _config_path(tmp_path: Path) -> Path:
    path = tmp_path / "mask-rules.yaml"
    path.write_text(
        yaml.safe_dump({"version": SUPPORTED_CONFIG_VERSION, "global_salt": TEST_SALT}),
        encoding="utf-8",
    )
    return path


def test_execute_run_completes_with_summary(
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
    summary = PipelineSummary(run_id=uuid.uuid4(), tables_processed=1, rows_processed=2)
    mocker.patch("privaci.cli.context.load_config", return_value=config)
    mocker.patch("privaci.cli.context.resolve_run_salt", return_value=TEST_SALT)
    mocker.patch(
        "privaci.cli._run.run_preflight",
        new_callable=AsyncMock,
        return_value=report,
    )
    mocker.patch(
        "privaci.cli._run.run_masking_pipeline",
        new_callable=AsyncMock,
        return_value=summary,
    )

    # Act
    execute_run(
        config_path=str(_config_path(tmp_path)),
        source="postgresql://x/y",
        target="postgresql://x/z",
    )
    captured = capsys.readouterr()

    # Assert
    assert "succeeded" in captured.out
    assert str(summary.run_id) in captured.out


def test_execute_run_dry_run_prints_table_summary(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    # Arrange
    config = Config(version="1.0", global_salt=TEST_SALT)
    report = PreflightReport(
        catalog=CatalogResult(
            tables={table_id("public", "users"): TableInfo("public", "users", ())},
            load_plan=LoadPlan(layers=()),
        ),
        detection=DetectionResult(findings=()),
        dry_run_rows=(("public.users", "transform", 12),),
    )
    mocker.patch("privaci.cli.context.load_config", return_value=config)
    mocker.patch("privaci.cli.context.resolve_run_salt", return_value=TEST_SALT)
    mocker.patch(
        "privaci.cli._run.run_preflight",
        new_callable=AsyncMock,
        return_value=report,
    )
    pipeline = mocker.patch(
        "privaci.cli._run.run_masking_pipeline",
        new_callable=AsyncMock,
    )

    # Act
    execute_run(
        config_path=str(_config_path(tmp_path)),
        source="postgresql://x/y",
        target="postgresql://x/z",
        dry_run=True,
    )
    captured = capsys.readouterr()

    # Assert
    assert "Dry run complete" in captured.out
    assert "public.users" in captured.out
    pipeline.assert_not_called()


def test_execute_run_echoes_preflight_warnings(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    # Arrange
    config = Config(version="1.0", global_salt=TEST_SALT)
    report = PreflightReport(
        catalog=CatalogResult(tables={}, load_plan=LoadPlan(layers=())),
        detection=DetectionResult(findings=()),
        warnings=("disk space may be tight",),
        dry_run_rows=(),
    )
    mocker.patch("privaci.cli.context.load_config", return_value=config)
    mocker.patch("privaci.cli.context.resolve_run_salt", return_value=TEST_SALT)
    mocker.patch(
        "privaci.cli._run.run_preflight",
        new_callable=AsyncMock,
        return_value=report,
    )

    # Act
    execute_run(
        config_path=str(_config_path(tmp_path)),
        source="postgresql://x/y",
        target="postgresql://x/z",
        dry_run=True,
    )
    captured = capsys.readouterr()

    # Assert
    assert "disk space may be tight" in captured.err


def test_execute_run_dry_run_writes_report_and_renders_findings(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    # Arrange — a catalog warning, a masked column, and an uncertain column.
    config = Config(version="1.0", global_salt=TEST_SALT)
    findings = (
        DetectionFinding(
            table_id="public.users",
            column_name="email",
            confidence="high",
            reasons=("matched email pattern",),
            action=FakeAction(action="fake", provider="email"),
            provider="email",
            source="autodetect",
        ),
        DetectionFinding(
            table_id="public.users",
            column_name="note",
            confidence="medium",
            reasons=("weak signal",),
            matched_pattern="freeform_text",
        ),
        DetectionFinding(
            table_id="public.users",
            column_name="ssn",
            confidence="high",
            reasons=("ssn rule",),
            action=HashAction(action="hash"),
        ),
        DetectionFinding(
            table_id="public.users",
            column_name="age",
            confidence="low",
            reasons=("no signal",),
        ),
    )
    report = PreflightReport(
        catalog=CatalogResult(
            tables={table_id("public", "users"): TableInfo("public", "users", ())},
            load_plan=LoadPlan(layers=()),
            warnings=(CatalogWarning(code="POLY_FK", message="polymorphic fk"),),
        ),
        detection=DetectionResult(findings=findings),
        dry_run_rows=(("public.users", "transform", 12),),
    )
    mocker.patch("privaci.cli.context.load_config", return_value=config)
    mocker.patch("privaci.cli.context.resolve_run_salt", return_value=TEST_SALT)
    mocker.patch(
        "privaci.cli._run.run_preflight", new_callable=AsyncMock, return_value=report
    )
    write_report = mocker.patch("privaci.cli._run.write_detection_report")
    report_path = tmp_path / "detection.json"

    # Act
    execute_run(
        config_path=str(_config_path(tmp_path)),
        source="postgresql://x/y",
        target="postgresql://x/z",
        dry_run=True,
        report_path=str(report_path),
    )
    captured = capsys.readouterr()

    # Assert
    write_report.assert_called_once()
    assert "Wrote detection report" in captured.out
    assert "mask: email -> fake/email" in captured.out
    assert "mask: ssn -> hash" in captured.out
    assert "review: note" in captured.out
    assert "POLY_FK" in captured.err


def test_dry_run_report_writes_before_strict_failure(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    # Arrange
    config = Config(version=SUPPORTED_CONFIG_VERSION, strict_autodetect=True)
    users = TableInfo("public", "users", (ColumnInfo("email", "text", True),))
    findings = (
        DetectionFinding(
            table_id="public.users",
            column_name="email",
            confidence="high",
            reasons=("pattern:email",),
            action=FakeAction(action="fake", provider="email"),
            matched_pattern="email",
        ),
    )
    report = PreflightReport(
        catalog=CatalogResult(
            tables={table_id("public", "users"): users},
            load_plan=LoadPlan(layers=()),
        ),
        detection=DetectionResult(findings=findings),
    )
    mocker.patch("privaci.cli.context.load_config", return_value=config)
    mocker.patch("privaci.cli.context.resolve_run_salt", return_value=TEST_SALT)
    plugins = mocker.MagicMock()
    plugins.license_validator.validate.return_value = LicenseStatus(
        tier="commercial",
        is_valid=True,
        message="ok",
    )
    mocker.patch("privaci.cli.context.load_plugins", return_value=plugins)
    mocker.patch(
        "privaci.cli._run.run_preflight", new_callable=AsyncMock, return_value=report
    )
    report_path = tmp_path / "detection.md"

    # Act / Assert
    with pytest.raises(ConfigError) as exc_info:
        execute_run(
            config_path=str(_config_path(tmp_path)),
            source="postgresql://x/y",
            target="postgresql://x/z",
            dry_run=True,
            report_path=str(report_path),
        )
    assert exc_info.value.exit_code == 3
    assert report_path.is_file()
    assert "Strict mode: on" in report_path.read_text(encoding="utf-8")


def test_execute_verify_passes(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    # Arrange
    mocker.patch("privaci.cli._run.load_config", return_value=Config(version="1.0"))
    report = VerifyReport(
        results=(
            CheckResult(
                check="row.parity",
                verdict=Verdict.PASS,
                target="public.users",
                detail="ok",
            ),
            CheckResult(
                check="column.change_rate",
                verdict=Verdict.WARN,
                target="public.users.bio",
                detail="low change rate",
            ),
        )
    )
    mocker.patch("privaci.cli._run.run_verification", return_value=report)

    # Act
    execute_verify(
        config_path=str(_config_path(tmp_path)),
        source="postgresql://x/y",
        target="postgresql://x/z",
        sample_size=100,
    )
    captured = capsys.readouterr()

    # Assert
    assert "1 passed" in captured.out
    assert "1 warning(s)" in captured.out
    assert "WARN  public.users.bio" in captured.err


def test_execute_verify_fails_exits_one(
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    # Arrange
    mocker.patch("privaci.cli._run.load_config", return_value=Config(version="1.0"))
    report = VerifyReport(
        results=(
            CheckResult(
                check="row.parity",
                verdict=Verdict.FAIL,
                target="public.users",
                detail="row count mismatch",
            ),
        )
    )
    mocker.patch("privaci.cli._run.run_verification", return_value=report)

    # Act / Assert
    with pytest.raises(typer.Exit) as exc_info:
        execute_verify(
            config_path=str(_config_path(tmp_path)),
            source="postgresql://x/y",
            target="postgresql://x/z",
            sample_size=100,
        )
    captured = capsys.readouterr()
    assert exc_info.value.exit_code == 1
    assert "FAIL  public.users" in captured.err


def test_execute_run_rejects_invalid_license(
    mocker: MockerFixture,
    tmp_path: Path,
) -> None:
    # Arrange
    plugins = mocker.MagicMock()
    plugins.license_validator.validate.return_value = LicenseStatus(
        tier="commercial",
        is_valid=False,
        message="expired",
    )
    mocker.patch("privaci.cli.context.load_config", return_value=Config(version="1.0"))
    mocker.patch("privaci.cli.context.load_plugins", return_value=plugins)

    # Act / Assert
    from privaci.errors import LicenseError

    with pytest.raises(LicenseError) as exc_info:
        execute_run(
            config_path=str(_config_path(tmp_path)),
            source="postgresql://x/y",
            target="postgresql://x/z",
        )
    assert exc_info.value.exit_code == 5

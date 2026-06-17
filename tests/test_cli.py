"""CLI smoke tests."""

from __future__ import annotations

from pathlib import Path

import yaml
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from privaci.cli.app import app
from privaci.errors import CatalogError, ConfigError
from tests.fixtures.constants import (
    SUPPORTED_CONFIG_VERSION,
    UNSUPPORTED_CONFIG_VERSION,
)

runner = CliRunner()


def test_gen_salt_emits_64_hex_chars() -> None:
    # Arrange & Act
    result = runner.invoke(app, ["gen-salt"])

    # Assert
    assert result.exit_code == 0
    salt = result.stdout.strip()
    assert len(salt) == 64
    assert all(c in "0123456789abcdef" for c in salt)


def test_help_exits_zero() -> None:
    # Act
    result = runner.invoke(app, ["--help"])

    # Assert
    assert result.exit_code == 0


def test_contract_version_prints_abi_version() -> None:
    # Act
    result = runner.invoke(app, ["--contract-version"])

    # Assert
    assert result.exit_code == 0
    assert result.stdout.strip() == "1.0"


def test_unknown_command_exits_nonzero() -> None:
    # Act
    result = runner.invoke(app, ["not-a-command"])

    # Assert
    assert result.exit_code != 0


def test_run_missing_config_exits_three(tmp_path: Path) -> None:
    # Act
    result = runner.invoke(app, ["run", "--config", str(tmp_path / "missing.yaml")])

    # Assert
    assert isinstance(result.exception, ConfigError)
    assert result.exception.exit_code == 3


def test_dry_run_report_flag_passes_path_to_execute_run(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    report_path = tmp_path / "out.md"
    config.write_text(
        yaml.safe_dump({"version": SUPPORTED_CONFIG_VERSION, "tables": {}}),
        encoding="utf-8",
    )
    execute = mocker.patch("privaci.cli.app.execute_run")

    # Act
    result = runner.invoke(
        app,
        ["dry-run", "--config", str(config), "--report", str(report_path)],
    )

    # Assert
    assert result.exit_code == 0
    execute.assert_called_once()
    assert execute.call_args.kwargs["report_path"] == str(report_path)


def test_validate_accepts_valid_config(tmp_path: Path) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text(
        yaml.safe_dump({"version": SUPPORTED_CONFIG_VERSION, "tables": {}}),
        encoding="utf-8",
    )

    # Act
    result = runner.invoke(app, ["validate", "--config", str(config)])

    # Assert
    assert result.exit_code == 0
    assert "is valid" in result.output


def test_validate_raises_config_error_on_invalid(tmp_path: Path) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text("tables: {}\n", encoding="utf-8")

    # Act
    result = runner.invoke(app, ["validate", "--config", str(config)])

    # Assert
    assert isinstance(result.exception, ConfigError)
    assert result.exception.exit_code == 3


def test_schema_config_emits_json_schema() -> None:
    # Act
    result = runner.invoke(app, ["schema", "config"])

    # Assert
    assert result.exit_code == 0
    assert "properties" in result.output


def test_catalog_inspect_missing_source_raises_catalog_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOURCE_DB_URL", raising=False)
    # Act
    result = runner.invoke(app, ["catalog", "inspect"])

    # Assert
    assert isinstance(result.exception, CatalogError)
    assert result.exception.exit_code == 2
    assert "SOURCE_DB_URL" in str(result.exception)


def test_catalog_inspect_renders_summary(mocker: MockerFixture) -> None:
    # Arrange
    from privaci.catalog.models import (
        CatalogResult,
        LoadLayer,
        LoadPlan,
        TableInfo,
        table_id,
    )

    catalog = CatalogResult(
        tables={
            table_id("public", "users"): TableInfo(
                "public", "users", (), estimated_rows=120.0
            ),
            table_id("public", "events"): TableInfo("public", "events", ()),
        },
        load_plan=LoadPlan(
            layers=(LoadLayer(table_ids=("public.events", "public.users")),)
        ),
    )
    mocker.patch(
        "privaci.cli._catalog.resolve_db_url",
        return_value="postgres://x/y",
    )

    def _run(coro: object) -> CatalogResult:
        coro.close()  # type: ignore[attr-defined]
        return catalog

    mocker.patch("privaci.cli._catalog.asyncio.run", side_effect=_run)

    # Act
    result = runner.invoke(app, ["catalog", "inspect", "--source", "postgres://x/y"])

    # Assert
    assert result.exit_code == 0
    assert "public.users" in result.output
    assert "~120 rows" in result.output
    assert "public.events" in result.output
    assert "~unknown rows" in result.output
    assert "~-1 rows" not in result.output
    assert "Load plan" in result.output


def test_migrate_config_noop_when_versions_match(tmp_path: Path) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text("version: '1.0'\n", encoding="utf-8")

    # Act
    result = runner.invoke(
        app,
        [
            "migrate-config",
            str(config),
            "--from",
            SUPPORTED_CONFIG_VERSION,
            "--to",
            SUPPORTED_CONFIG_VERSION,
        ],
    )

    # Assert
    assert result.exit_code == 0
    assert "No migration needed" in result.output


def test_migrate_config_rejects_distinct_versions(tmp_path: Path) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text("version: '1.0'\n", encoding="utf-8")

    # Act
    result = runner.invoke(
        app,
        [
            "migrate-config",
            str(config),
            "--from",
            SUPPORTED_CONFIG_VERSION,
            "--to",
            UNSUPPORTED_CONFIG_VERSION,
        ],
    )

    # Assert
    assert isinstance(result.exception, ConfigError)
    assert result.exception.exit_code == 3


def test_generate_ci_writes_workflow(tmp_path: Path) -> None:
    # Act
    result = runner.invoke(
        app,
        ["generate-ci", "--platform", "github-actions", "--output-dir", str(tmp_path)],
    )

    # Assert
    assert result.exit_code == 0
    assert (tmp_path / ".github" / "workflows" / "privaci-refresh.yml").is_file()


def test_default_invocation_runs_run_subcommand(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text(
        yaml.safe_dump({"version": SUPPORTED_CONFIG_VERSION, "tables": {}}),
        encoding="utf-8",
    )
    execute = mocker.patch("privaci.cli.app.execute_run")

    # Act
    result = runner.invoke(app, ["--config", str(config)])

    # Assert
    assert result.exit_code == 0
    execute.assert_called_once()

"""CLI tests for ``privaci init`` and ``privaci plan``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pytest_mock import MockerFixture
from typer.testing import CliRunner

from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.cli.app import app
from privaci.config import load_config
from privaci.errors import CatalogError
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION, TEST_SALT

runner = CliRunner()


def _catalog() -> CatalogResult:
    users = TableInfo(
        schema_name="public",
        table_name="users",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="email", data_type="text", not_null=True),
        ),
        primary_key=("id",),
    )
    return CatalogResult(
        tables={users.identifier: users},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=(users.identifier,)),)),
    )


def test_init_writes_config(tmp_path: Path, mocker: MockerFixture) -> None:
    # Arrange
    output = tmp_path / "mask-rules.yaml"
    mocker.patch(
        "privaci.cli._init.introspect_source_catalog",
        return_value=_catalog(),
    )

    # Act
    result = runner.invoke(
        app,
        [
            "init",
            "--source",
            "postgresql://x/y",
            "--output",
            str(output),
        ],
    )

    # Assert
    assert result.exit_code == 0, result.output
    loaded = load_config(output)
    assert loaded.tables["public.users"].columns["email"].action == "fake"


def test_init_refuses_overwrite_without_force(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    # Arrange
    output = tmp_path / "mask-rules.yaml"
    output.write_text("existing: true\n", encoding="utf-8")
    mocker.patch(
        "privaci.cli._init.introspect_source_catalog",
        return_value=_catalog(),
    )

    # Act
    result = runner.invoke(
        app,
        [
            "init",
            "--source",
            "postgresql://x/y",
            "--output",
            str(output),
        ],
    )

    # Assert
    assert isinstance(result.exception, CatalogError)
    assert result.exception.exit_code == 2
    assert "already exists" in str(result.exception)


def test_plan_runs_without_target(tmp_path: Path, mocker: MockerFixture) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "version": SUPPORTED_CONFIG_VERSION,
                "global_salt": TEST_SALT,
                "tables": {
                    "public.users": {
                        "strategy": "transform",
                        "columns": {
                            "email": {"action": "fake", "provider": "email"},
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    mocker.patch(
        "privaci.cli._plan.introspect_source_catalog",
        return_value=_catalog(),
    )

    # Act
    result = runner.invoke(
        app,
        [
            "plan",
            "--config",
            str(config),
            "--source",
            "postgresql://x/y",
            "--format",
            "json",
        ],
    )

    # Assert
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["tables"][0]["table"] == "public.users"
    assert payload["summary"]["mask"] >= 1


def test_init_missing_source_raises_catalog_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("SOURCE_DB_URL", raising=False)
    output = tmp_path / "mask-rules.yaml"

    # Act
    result = runner.invoke(
        app,
        ["init", "--output", str(output)],
    )

    # Assert
    assert isinstance(result.exception, CatalogError)
    assert result.exception.exit_code == 2
    assert "SOURCE_DB_URL" in str(result.exception)


def test_init_force_overwrites_existing_file(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    # Arrange
    output = tmp_path / "mask-rules.yaml"
    output.write_text("existing: true\n", encoding="utf-8")
    mocker.patch(
        "privaci.cli._init.introspect_source_catalog",
        return_value=_catalog(),
    )

    # Act
    result = runner.invoke(
        app,
        [
            "init",
            "--source",
            "postgresql://x/y",
            "--output",
            str(output),
            "--force",
        ],
    )

    # Assert
    assert result.exit_code == 0, result.output
    loaded = load_config(output)
    assert "public.users" in loaded.tables


def test_plan_text_format(tmp_path: Path, mocker: MockerFixture) -> None:
    # Arrange
    config = tmp_path / "mask-rules.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "version": SUPPORTED_CONFIG_VERSION,
                "global_salt": TEST_SALT,
                "tables": {
                    "public.users": {
                        "strategy": "transform",
                        "columns": {
                            "email": {"action": "fake", "provider": "email"},
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    mocker.patch(
        "privaci.cli._plan.introspect_source_catalog",
        return_value=_catalog(),
    )

    # Act
    result = runner.invoke(
        app,
        [
            "plan",
            "--config",
            str(config),
            "--source",
            "postgresql://x/y",
        ],
    )

    # Assert
    assert result.exit_code == 0, result.output
    assert "Plan (" in result.output
    assert "public.users" in result.output

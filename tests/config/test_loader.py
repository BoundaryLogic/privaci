"""Tests for config loading, version checks, and validation errors."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from privaci.config.loader import (
    _error_path,
    _yaml_location,
    check_null_actions,
    export_json_schema,
    is_commercial_installed,
    load_config,
    migrate_config,
)
from privaci.errors import ConfigError
from tests.fixtures.constants import (
    SUPPORTED_CONFIG_VERSION,
    UNSUPPORTED_CONFIG_VERSION,
)

ConfigWriter = Callable[[dict[str, Any] | str], Path]


def test_load_valid_config(
    valid_config_dict: dict[str, Any], write_config: ConfigWriter
) -> None:
    # Arrange
    path = write_config(valid_config_dict)

    # Act
    config = load_config(path, commercial_installed=False)

    # Assert
    assert config.version == SUPPORTED_CONFIG_VERSION
    assert "users" in config.tables


def test_unknown_fake_provider_raises_config_error(
    write_config: ConfigWriter,
) -> None:
    # Arrange
    path = write_config(
        {
            "version": SUPPORTED_CONFIG_VERSION,
            "tables": {
                "users": {
                    "columns": {
                        "email": {
                            "action": "fake",
                            "provider": "unknown_provider_xyz",
                        }
                    }
                }
            },
        }
    )

    # Act & Assert
    with pytest.raises(ConfigError, match="Unknown provider"):
        load_config(path, commercial_installed=False)


def test_missing_file_raises_config_error(tmp_path: Path) -> None:
    # Act & Assert
    with pytest.raises(ConfigError, match="does not exist") as exc:
        load_config(tmp_path / "absent.yaml")
    assert exc.value.exit_code == 3


def test_unreadable_path_raises_config_error(tmp_path: Path) -> None:
    # Arrange — reading a directory raises an OSError subclass.
    # Act & Assert
    with pytest.raises(ConfigError, match="could not be read"):
        load_config(tmp_path)


def test_malformed_yaml_reports_location(write_config: ConfigWriter) -> None:
    # Arrange
    path = write_config("version: '1.0'\n  bad: : :\n")

    # Act & Assert
    with pytest.raises(ConfigError, match="Invalid YAML syntax") as exc:
        load_config(path)
    assert exc.value.exit_code == 3


def test_non_mapping_top_level_rejected(write_config: ConfigWriter) -> None:
    # Arrange
    path = write_config("- just\n- a\n- list\n")

    # Act & Assert
    with pytest.raises(ConfigError, match="must be a mapping"):
        load_config(path)


def test_missing_version_directs_user(write_config: ConfigWriter) -> None:
    # Arrange
    path = write_config({"tables": {}})

    # Act & Assert
    with pytest.raises(ConfigError, match="Missing required field 'version'"):
        load_config(path)


def test_unsupported_version_rejected(write_config: ConfigWriter) -> None:
    # Arrange
    path = write_config({"version": UNSUPPORTED_CONFIG_VERSION})

    # Act & Assert
    with pytest.raises(ConfigError, match="is not supported by engine") as exc:
        load_config(path)
    assert UNSUPPORTED_CONFIG_VERSION in str(exc.value)


def test_unknown_key_names_offending_field(write_config: ConfigWriter) -> None:
    # Arrange
    path = write_config({"version": SUPPORTED_CONFIG_VERSION, "unknown_field": 1})

    # Act & Assert
    with pytest.raises(ConfigError, match="unknown_field"):
        load_config(path)


def test_missing_provider_lists_column_path(write_config: ConfigWriter) -> None:
    # Arrange
    data = {
        "version": SUPPORTED_CONFIG_VERSION,
        "tables": {"users": {"columns": {"first_name": {"action": "fake"}}}},
    }
    path = write_config(data)

    # Act & Assert
    with pytest.raises(ConfigError, match="tables.users.columns.first_name.provider"):
        load_config(path)


def test_ai_refine_rejected_without_commercial(
    write_config: ConfigWriter,
) -> None:
    # Arrange
    data = {
        "version": SUPPORTED_CONFIG_VERSION,
        "tables": {
            "tickets": {
                "columns": {
                    "notes": {
                        "action": "ai_refine",
                        "provider": "aws_bedrock",
                        "model": "claude",
                    }
                }
            }
        },
    }
    path = write_config(data)

    # Act & Assert
    with pytest.raises(ConfigError, match="requires the commercial layer") as exc:
        load_config(path, commercial_installed=False)
    assert "tables.tickets.columns.notes" in str(exc.value)


def test_ai_refine_allowed_with_commercial(write_config: ConfigWriter) -> None:
    # Arrange
    data = {
        "version": SUPPORTED_CONFIG_VERSION,
        "tables": {
            "tickets": {
                "columns": {
                    "notes": {
                        "action": "ai_refine",
                        "provider": "aws_bedrock",
                        "model": "claude",
                    }
                }
            }
        },
    }
    path = write_config(data)

    # Act
    config = load_config(path, commercial_installed=True)

    # Assert
    assert "tickets" in config.tables


def test_load_config_auto_detects_commercial(
    valid_config_dict: dict[str, Any],
    write_config: ConfigWriter,
    mocker: Any,
) -> None:
    # Arrange
    spy = mocker.patch(
        "privaci.config.loader.is_commercial_installed", return_value=False
    )
    path = write_config(valid_config_dict)

    # Act
    load_config(path)

    # Assert
    spy.assert_called_once()


def test_check_null_actions_rejects_not_null_column(
    valid_config_dict: dict[str, Any],
) -> None:
    # Arrange
    valid_config_dict["tables"]["users"]["columns"]["password"] = {"action": "null"}
    from privaci.config.models import Config

    config = Config.model_validate(valid_config_dict)

    # Act & Assert
    with pytest.raises(ConfigError, match="NOT NULL columns") as exc:
        check_null_actions(config, {"users": {"password"}})
    assert "tables.users.columns.password" in str(exc.value)


def test_check_null_actions_passes_for_nullable_column(
    valid_config_dict: dict[str, Any],
) -> None:
    # Arrange
    valid_config_dict["tables"]["users"]["columns"]["password"] = {"action": "null"}
    from privaci.config.models import Config

    config = Config.model_validate(valid_config_dict)

    # Act — password is not in the NOT NULL set; should not raise.
    check_null_actions(config, {"users": set()})


def test_is_commercial_installed_false_in_community() -> None:
    # Act & Assert — no commercial entry points registered in tests.
    assert is_commercial_installed() is False


def test_export_json_schema_includes_properties() -> None:
    # Act
    schema = export_json_schema()

    # Assert
    assert '"version"' in schema
    assert "properties" in schema


def test_migrate_config_noop_when_versions_match() -> None:
    # Act
    message = migrate_config(SUPPORTED_CONFIG_VERSION, SUPPORTED_CONFIG_VERSION)

    # Assert
    assert "No migration needed" in message


def test_migrate_config_rejects_distinct_versions() -> None:
    # Act & Assert
    with pytest.raises(ConfigError, match="No migration path") as exc:
        migrate_config(SUPPORTED_CONFIG_VERSION, UNSUPPORTED_CONFIG_VERSION)
    assert exc.value.exit_code == 3


def test_yaml_location_without_marker_is_empty() -> None:
    # Act & Assert — a bare YAMLError carries no problem_mark.
    assert _yaml_location(yaml.YAMLError("boom")) == ""


def test_error_path_for_empty_loc_returns_root() -> None:
    # Act & Assert
    assert _error_path(()) == "<root>"

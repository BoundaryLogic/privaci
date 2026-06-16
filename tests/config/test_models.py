"""Tests for top-level Config and TableConfig models."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from privaci.config.models import DEFAULT_BATCH_SIZE, Config, TableConfig
from privaci.secrets.types import SecretStr
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION, TEST_SALT


def test_config_applies_documented_defaults(valid_config_dict: dict[str, Any]) -> None:
    # Act
    config = Config.model_validate(valid_config_dict)

    # Assert
    assert config.on_existing_data == "fail"
    assert config.batch_size == DEFAULT_BATCH_SIZE
    assert config.audit_log is True
    assert config.auto_detect is True
    assert config.strict_autodetect is False
    assert config.replicate_all_indexes is False
    assert config.implied_fk_ignore == []


def test_implied_fk_ignore_accepts_column_paths() -> None:
    # Act
    config = Config.model_validate(
        {
            "version": SUPPORTED_CONFIG_VERSION,
            "implied_fk_ignore": [
                "clinical.patient_documents.referring_provider_email"
            ],
        }
    )

    # Assert
    assert config.implied_fk_ignore == [
        "clinical.patient_documents.referring_provider_email"
    ]


def test_table_defaults_to_transform_strategy() -> None:
    # Act
    table = TableConfig()

    # Assert
    assert table.strategy == "transform"
    assert table.columns == {}
    assert table.null_orphan_fks is False


def test_unknown_top_level_key_is_forbidden() -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="Extra inputs"):
        Config.model_validate({"version": SUPPORTED_CONFIG_VERSION, "nope": 1})


def test_append_strategy_is_rejected_in_mvp() -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="append strategy is not supported"):
        Config.model_validate(
            {"version": SUPPORTED_CONFIG_VERSION, "on_existing_data": "append"}
        )


@pytest.mark.parametrize("value", [0, -1])
def test_global_batch_size_must_be_positive(value: int) -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="batch_size must be >= 1"):
        Config.model_validate(
            {"version": SUPPORTED_CONFIG_VERSION, "batch_size": value}
        )


@pytest.mark.parametrize("value", [0, -5])
def test_table_batch_size_must_be_positive(value: int) -> None:
    # Act & Assert
    with pytest.raises(ValidationError, match="batch_size must be >= 1"):
        TableConfig(batch_size=value)


def test_table_batch_size_override_accepted() -> None:
    # Act
    table = TableConfig(batch_size=500)

    # Assert
    assert table.batch_size == 500


def test_global_salt_wraps_plaintext_and_preserves_secretstr() -> None:
    # Act
    from_plain = Config.model_validate(
        {"version": SUPPORTED_CONFIG_VERSION, "global_salt": TEST_SALT}
    )
    from_secret = Config.model_validate(
        {
            "version": SUPPORTED_CONFIG_VERSION,
            "global_salt": SecretStr(TEST_SALT),
        }
    )
    from_none = Config.model_validate(
        {"version": SUPPORTED_CONFIG_VERSION, "global_salt": None}
    )
    from_blank = Config.model_validate(
        {"version": SUPPORTED_CONFIG_VERSION, "global_salt": "   "}
    )

    # Assert
    assert from_plain.global_salt is not None
    assert from_plain.global_salt.get_secret_value() == TEST_SALT
    assert from_secret.global_salt is not None
    assert from_secret.global_salt.get_secret_value() == TEST_SALT
    assert from_none.global_salt is None
    assert from_blank.global_salt is None


def test_explicit_global_batch_size_accepted() -> None:
    # Act
    config = Config.model_validate(
        {"version": SUPPORTED_CONFIG_VERSION, "batch_size": 5000}
    )

    # Assert
    assert config.batch_size == 5000

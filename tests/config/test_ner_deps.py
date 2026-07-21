"""Tests for SpaCy prerequisite gates on explicit ner_mask (config load)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from privaci.config.actions import FakeAction, NerMaskAction
from privaci.config.loader import load_config
from privaci.config.models import Config, TableConfig
from privaci.config.ner_deps import validate_ner_mask_actions
from privaci.errors import ConfigError
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION

ConfigWriter = Callable[[dict[str, Any] | str], Path]


def _config_with_ner() -> Config:
    return Config(
        version=SUPPORTED_CONFIG_VERSION,
        tables={
            "public.notes": TableConfig(
                columns={"body": NerMaskAction(action="ner_mask")}
            )
        },
    )


def test_validate_ner_mask_actions_ok_when_spacy_available(mocker: object) -> None:
    # Arrange
    mocker.patch("privaci.config.ner_deps.spacy_available", return_value=True)

    # Act / Assert — no raise
    validate_ner_mask_actions(_config_with_ner())


def test_validate_ner_mask_actions_fails_without_spacy(mocker: object) -> None:
    # Arrange
    mocker.patch("privaci.config.ner_deps.spacy_available", return_value=False)

    # Act / Assert
    with pytest.raises(ConfigError, match="ner_mask requires SpaCy"):
        validate_ner_mask_actions(_config_with_ner())


def test_validate_ner_mask_skips_when_no_ner_columns(mocker: object) -> None:
    # Arrange
    spy = mocker.patch("privaci.config.ner_deps.spacy_available")
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        tables={
            "public.users": TableConfig(
                columns={"email": FakeAction(action="fake", provider="email")}
            )
        },
    )

    # Act
    validate_ner_mask_actions(config)

    # Assert
    spy.assert_not_called()


def test_load_config_fails_when_ner_mask_without_spacy(
    write_config: ConfigWriter, mocker: object
) -> None:
    # Arrange — wiring through load_config (not only validate_ner_mask_actions)
    mocker.patch("privaci.config.ner_deps.spacy_available", return_value=False)
    path = write_config(
        {
            "version": SUPPORTED_CONFIG_VERSION,
            "tables": {
                "public.notes": {
                    "columns": {"body": {"action": "ner_mask"}},
                }
            },
        }
    )

    # Act / Assert
    with pytest.raises(ConfigError, match="ner_mask requires SpaCy"):
        load_config(path, commercial_installed=False)

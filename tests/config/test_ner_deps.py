"""Tests for SpaCy prerequisite gates on ner_mask."""

from __future__ import annotations

import pytest

from privaci.autodetect.models import DetectionFinding, DetectionResult
from privaci.catalog.models import (
    CatalogResult,
    ColumnInfo,
    LoadLayer,
    LoadPlan,
    TableInfo,
)
from privaci.config.actions import FakeAction, NerMaskAction
from privaci.config.models import Config, TableConfig
from privaci.config.ner_deps import validate_ner_mask_actions
from privaci.errors import ConfigError, PreflightError
from privaci.preflight.ner_spacy import verify_ner_mask_spacy
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION


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


def test_verify_ner_mask_spacy_fails_for_autodetect(mocker: object) -> None:
    # Arrange
    mocker.patch("privaci.preflight.ner_spacy.spacy_available", return_value=False)
    config = Config(version=SUPPORTED_CONFIG_VERSION, auto_detect=True, tables={})
    notes = TableInfo(
        schema_name="public",
        table_name="notes",
        columns=(ColumnInfo(name="body", data_type="text", not_null=False),),
    )
    catalog = CatalogResult(
        tables={notes.identifier: notes},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=(notes.identifier,)),)),
    )
    detection = DetectionResult(
        findings=(
            DetectionFinding(
                table_id="public.notes",
                column_name="body",
                confidence="high",
                reasons=("matched notes pattern",),
                action=NerMaskAction(action="ner_mask"),
                matched_pattern="notes",
            ),
        )
    )

    # Act / Assert
    with pytest.raises(PreflightError, match="ner_mask requires SpaCy"):
        verify_ner_mask_spacy(config, catalog, detection)

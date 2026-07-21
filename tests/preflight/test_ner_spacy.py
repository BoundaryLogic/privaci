"""Tests for preflight SpaCy gate on effective ner_mask."""

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
from privaci.errors import PreflightError
from privaci.preflight.ner_spacy import (
    iter_effective_ner_columns,
    verify_ner_mask_spacy,
)
from tests.fixtures.constants import SUPPORTED_CONFIG_VERSION


def _notes_catalog() -> tuple[CatalogResult, TableInfo]:
    notes = TableInfo(
        schema_name="public",
        table_name="notes",
        columns=(ColumnInfo(name="body", data_type="text", not_null=False),),
    )
    catalog = CatalogResult(
        tables={notes.identifier: notes},
        load_plan=LoadPlan(layers=(LoadLayer(table_ids=(notes.identifier,)),)),
    )
    return catalog, notes


def test_verify_ner_mask_spacy_fails_for_autodetect(mocker: object) -> None:
    # Arrange
    mocker.patch("privaci.preflight.ner_spacy.spacy_available", return_value=False)
    config = Config(version=SUPPORTED_CONFIG_VERSION, auto_detect=True, tables={})
    catalog, _notes = _notes_catalog()
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


def test_verify_ner_mask_spacy_fails_for_explicit_yaml(mocker: object) -> None:
    # Arrange
    mocker.patch("privaci.preflight.ner_spacy.spacy_available", return_value=False)
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        tables={
            "public.notes": TableConfig(
                columns={"body": NerMaskAction(action="ner_mask")}
            )
        },
    )
    catalog, _notes = _notes_catalog()

    # Act / Assert
    with pytest.raises(PreflightError, match="ner_mask requires SpaCy"):
        verify_ner_mask_spacy(config, catalog, DetectionResult(findings=()))


def test_verify_ner_mask_spacy_ok_when_available(mocker: object) -> None:
    # Arrange
    mocker.patch("privaci.preflight.ner_spacy.spacy_available", return_value=True)
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        tables={
            "public.notes": TableConfig(
                columns={"body": NerMaskAction(action="ner_mask")}
            )
        },
    )
    catalog, _notes = _notes_catalog()

    # Act / Assert — no raise
    verify_ner_mask_spacy(config, catalog, DetectionResult(findings=()))


def test_verify_ner_mask_spacy_noop_without_ner(mocker: object) -> None:
    # Arrange
    spy = mocker.patch("privaci.preflight.ner_spacy.spacy_available")
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        tables={
            "public.notes": TableConfig(
                columns={"body": FakeAction(action="fake", provider="sentence")}
            )
        },
    )
    catalog, _notes = _notes_catalog()

    # Act
    verify_ner_mask_spacy(config, catalog, DetectionResult(findings=()))

    # Assert
    spy.assert_not_called()


def test_iter_effective_ner_uses_parent_for_partition_child() -> None:
    # Arrange — child inherits parent YAML; path uses parent id (streaming parity)
    parent = TableInfo(
        schema_name="public",
        table_name="events",
        columns=(ColumnInfo(name="notes", data_type="text", not_null=False),),
        is_partitioned=True,
        partition_children=("public.events_2024",),
    )
    child = TableInfo(
        schema_name="public",
        table_name="events_2024",
        columns=(ColumnInfo(name="notes", data_type="text", not_null=False),),
        parent_partition="public.events",
    )
    catalog = CatalogResult(
        tables={parent.identifier: parent, child.identifier: child},
        load_plan=LoadPlan(
            layers=(LoadLayer(table_ids=(parent.identifier, child.identifier)),)
        ),
    )
    config = Config(
        version=SUPPORTED_CONFIG_VERSION,
        tables={
            "public.events": TableConfig(
                columns={"notes": NerMaskAction(action="ner_mask")}
            )
        },
    )

    # Act
    paths = list(
        iter_effective_ner_columns(config, catalog, DetectionResult(findings=()))
    )

    # Assert — one path on the parent config table, not a duplicate child path
    assert paths == ["public.events.notes"]

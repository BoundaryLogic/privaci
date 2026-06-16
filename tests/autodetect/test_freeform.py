"""Tests for freeform confidence scoring."""

from __future__ import annotations

from privaci.autodetect.freeform import (
    is_freeform_eligible_type,
    score_freeform_confidence,
)
from privaci.catalog.models import ColumnInfo


def test_long_notes_on_sensitive_table_is_high() -> None:
    # Arrange
    column = ColumnInfo(
        name="visit_notes",
        data_type="text",
        not_null=False,
        avg_width=800.0,
    )

    # Act
    confidence, reasons = score_freeform_confidence(
        table_name="patient_visits",
        column=column,
    )

    # Assert
    assert confidence == "high"
    assert any("sensitive" in reason for reason in reasons)


def test_long_description_on_products_is_medium() -> None:
    # Arrange
    column = ColumnInfo(
        name="description",
        data_type="text",
        not_null=False,
        avg_width=350.0,
    )

    # Act
    confidence, _reasons = score_freeform_confidence(
        table_name="products",
        column=column,
    )

    # Assert
    assert confidence == "medium"


def test_short_varchar_is_low() -> None:
    # Arrange
    column = ColumnInfo(
        name="description",
        data_type="character varying(100)",
        not_null=False,
        avg_width=40.0,
    )

    # Act
    confidence, _reasons = score_freeform_confidence(
        table_name="products",
        column=column,
    )

    # Assert
    assert confidence == "low"
    assert not is_freeform_eligible_type(column)

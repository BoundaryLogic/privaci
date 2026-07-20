"""Unit tests for MaskingEngine ``when:`` guards."""

from __future__ import annotations

from privaci.catalog.models import ColumnInfo, TableInfo
from privaci.config.actions import FakeAction, StaticAction
from privaci.config.models import TableConfig
from privaci.mask.engine import MaskingEngine


def _table() -> TableInfo:
    return TableInfo(
        schema_name="public",
        table_name="tickets",
        columns=(
            ColumnInfo(name="id", data_type="integer", not_null=True),
            ColumnInfo(name="status", data_type="text", not_null=True),
            ColumnInfo(name="notes", data_type="text", not_null=False),
        ),
        primary_key=("id",),
    )


def test_when_false_passthrough_preserves_value() -> None:
    # Arrange
    engine = MaskingEngine(
        "test-salt-value-at-least-32-chars!!",
        "public.tickets",
        _table(),
        TableConfig(
            columns={
                "notes": StaticAction(
                    action="static",
                    value="REDACTED",
                    when="status == 'closed'",
                )
            }
        ),
    )

    # Act
    open_row = engine.mask_row({"id": 1, "status": "open", "notes": "keep-me"})
    closed_row = engine.mask_row({"id": 2, "status": "closed", "notes": "secret"})

    # Assert
    assert open_row["notes"] == "keep-me"
    assert closed_row["notes"] == "REDACTED"
    audits = engine.drain_conditional_skip_audits()
    assert len(audits) == 1
    assert audits[0].skipped_rows == 1
    assert audits[0].evaluated_rows == 2


def test_requires_row_mutation_when_guard_present() -> None:
    # Arrange
    engine = MaskingEngine(
        "test-salt-value-at-least-32-chars!!",
        "public.tickets",
        _table(),
        TableConfig(
            columns={
                "notes": FakeAction(
                    action="fake",
                    provider="company",
                    when="status == 'closed'",
                )
            }
        ),
    )

    # Act / Assert
    assert engine.requires_row_mutation is True
